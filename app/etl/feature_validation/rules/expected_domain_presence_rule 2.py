"""
ExpectedDomainPresenceRule: judges whether the "muscle" domain's
presence/absence is consistent with whether its synchronization group
has an EMG device configured this session.

See docs/development/FEATURE_VALIDATION_DESIGN.md, Scientific
Rationale.
"""

from __future__ import annotations

from typing import Dict, Sequence

from app.etl.feature_extraction import ExtractedFeatureSet
from app.etl.synchronization import SynchronizationGroupConfig

from ..quality import QualityFlag, SetQualityObservation
from ..validation_rule import RuleResult

_MUSCLE_DOMAIN = "muscle"


class ExpectedDomainPresenceRule:
    """
    Distinguishes "muscle domain absent because this group has no EMG
    configured" (expected, silent) from "muscle domain absent despite
    the group having EMG configured" (a real data-quality concern) —
    and the reverse (present when not configured), a structurally
    impossible defensive check.

    Rationale: Feature Validation cannot judge domain-presence
    correctness from a single window's ExtractedFeatureSet alone — it
    needs the static, session-level fact of which groups have EMG
    configured, exactly the fact SynchronizationGroupConfig.emg_device_id
    already carries. Reuses that existing, frozen, exported type — no
    new type, no modification to any frozen module — passed at
    construction, the same pattern Calibrator/Filterer/Extractor use
    for their own domain config. This is the closest honest proxy for
    "synchronization quality is acceptable" achievable without the
    per-frame sync_status information that does not survive into
    ExtractedFeatureSet (see FEATURE_VALIDATION_DESIGN.md's documented
    gap). Soft concern when absent-but-expected (QUESTIONABLE-tier, a
    genuine possible dropout); the reverse case can only indicate a
    configuration-wiring bug between Synchronizer and FeatureValidator,
    since a Match Mode group's pipeline never produces "emg" readings
    structurally.
    """

    def __init__(self, group_configs: Sequence[SynchronizationGroupConfig]) -> None:
        self._emg_configured_by_group: Dict[str, bool] = {
            config.group_id: config.emg_device_id is not None for config in group_configs
        }

    def evaluate(self, extracted: ExtractedFeatureSet) -> RuleResult:
        emg_expected = self._emg_configured_by_group.get(extracted.group_id)
        if emg_expected is None:
            # This group_id wasn't in the configured set at all — never
            # guess; stay silent rather than assume either way.
            return RuleResult(biomarker_flags={})

        muscle_present = _MUSCLE_DOMAIN in extracted.domains
        observations = []

        if emg_expected and not muscle_present:
            observations.append(
                SetQualityObservation(
                    flag=QualityFlag.EXPECTED_DOMAIN_ABSENT,
                    domain=_MUSCLE_DOMAIN,
                    rationale=(
                        f"Group '{extracted.group_id}' has an EMG device "
                        f"configured this session, but the 'muscle' domain is "
                        f"entirely absent from this window — possible EMG "
                        f"dropout or synchronization issue."
                    ),
                )
            )
        elif not emg_expected and muscle_present:
            observations.append(
                SetQualityObservation(
                    flag=QualityFlag.UNEXPECTED_DOMAIN_PRESENT,
                    domain=_MUSCLE_DOMAIN,
                    rationale=(
                        f"Group '{extracted.group_id}' has no EMG device "
                        f"configured this session, but the 'muscle' domain is "
                        f"present — structurally unexpected given today's "
                        f"pipeline; suggests a configuration mismatch between "
                        f"Synchronizer and FeatureValidator."
                    ),
                )
            )

        return RuleResult(biomarker_flags={}, set_observations=tuple(observations))
