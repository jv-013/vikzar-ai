"""
Publisher.

Stage 9 of the ETL pipeline, and the formal ETL -> AI boundary (see
docs/architecture/04_ETL_ARCHITECTURE.md and
docs/development/PUBLISHER_DESIGN.md).

Performs lossless structural translation from one AggregatedFeatureCycle
into one RawFeatureVector — the official ETL -> AI contract. Never
computes a biomarker, alters a value, drops a value, merges or compares
groups, or re-evaluates a quality judgment. Every scientific decision
happened in an earlier stage; Publisher only carries it forward.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Callable, Dict, Optional

from app.etl.aggregation import AggregatedFeatureCycle
from app.etl.feature_validation import (
    BiomarkerQuality,
    SetQualityObservation,
    ValidatedFeatureSet,
)
from app.schemas.domain_biomarkers import DomainBiomarkers
from app.schemas.group_feature_set import GroupFeatureSet
from app.schemas.hardware_provenance import HardwareProvenance
from app.schemas.quality_info import (
    BiomarkerQualityInfo,
    QualityFlagInfo,
    QualityStatusInfo,
    SetQualityObservationInfo,
)
from app.schemas.raw_feature_vector import RawFeatureVector

from .player_session_context import PlayerSessionContext

logger = logging.getLogger(__name__)

RawFeatureVectorConsumer = Callable[[RawFeatureVector], None]
"""Invoked with each RawFeatureVector as it is published."""

_KNOWN_DOMAIN_NAMES = ("motion", "pressure", "muscle")


class Publisher:
    """
    Converts AggregatedFeatureCycles into RawFeatureVectors — the ETL ->
    AI boundary crossing.

    Purpose
        Translate already-validated, already-quality-assessed ETL
        output into the AI-facing schema, structurally. Publisher
        introduces zero scientific assumptions: every biomarker value,
        every quality status, and every quality flag is copied
        verbatim from what Feature Validation already produced.

    Statelessness
        Receives one complete AggregatedFeatureCycle per call and
        publishes immediately — no buffering, no waiting for another
        group, no cross-cycle state. FeatureSetAggregator (upstream)
        exists specifically so Publisher never needs to be stateful.

    Lossless, or loud failure
        If an AggregatedFeatureCycle's ValidatedFeatureSet contains a
        domain name Publisher does not recognize (GroupFeatureSet has
        no corresponding field for it), Publisher raises rather than
        silently dropping that domain's data — silently dropping would
        violate the lossless-transformation guarantee just as much as
        fabricating data would. This is treated as a data/version
        mismatch (this cycle is dropped, logged, the pipeline
        continues), not a wiring bug like a wrong handle() argument
        type (which raises outside the try/except and propagates).
    """

    def __init__(
        self,
        context: PlayerSessionContext,
        on_published: RawFeatureVectorConsumer,
        id_factory: Callable[[], str] = lambda: str(uuid.uuid4()),
        clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ) -> None:
        """
        Initialize the publisher.

        Args:
            context: Static player/session/hardware identity for this
                session. Never varies per call.
            on_published: Callback invoked with each published
                RawFeatureVector.
            id_factory: Produces a fresh feature_vector_id per publish.
                Overridable for deterministic tests.
            clock: Produces the publish-time timestamp. Overridable for
                deterministic tests.
        """
        self._context = context
        self._on_published = on_published
        self._id_factory = id_factory
        self._clock = clock

    def handle(self, cycle: AggregatedFeatureCycle) -> None:
        """
        Publish a single AggregatedFeatureCycle as one RawFeatureVector.

        This is the entry point wired as FeatureSetAggregator's
        on_aggregated callback. Raises immediately for a wrong input
        type; every other failure (including an unrecognized domain
        name) is logged and this cycle is dropped.

        Args:
            cycle: The complete, one-per-group feature cycle to publish.

        Raises:
            TypeError: If cycle is not an AggregatedFeatureCycle.
        """
        if not isinstance(cycle, AggregatedFeatureCycle):
            raise TypeError(
                f"Publisher.handle() only accepts AggregatedFeatureCycle; "
                f"received {type(cycle).__name__}."
            )
        try:
            self._handle(cycle)
        except Exception:
            logger.exception("publisher.unexpected_error")

    def _handle(self, cycle: AggregatedFeatureCycle) -> None:
        groups = {
            group_id: self._build_group_feature_set(validated)
            for group_id, validated in cycle.groups.items()
        }

        raw_feature_vector = RawFeatureVector(
            feature_vector_id=self._id_factory(),
            timestamp=self._clock(),
            schema_version=self._context.schema_version,
            source=self._context.source,
            player=self._context.player,
            session=self._context.session,
            hardware=HardwareProvenance(
                firmware_revision=self._context.firmware_revision,
                hardware_revision=self._context.hardware_revision,
                protocol_version=self._context.protocol_version,
            ),
            groups=groups,
        )
        self._on_published(raw_feature_vector)

    def _build_group_feature_set(self, validated: ValidatedFeatureSet) -> GroupFeatureSet:
        domain_fields: Dict[str, Optional[DomainBiomarkers]] = {name: None for name in _KNOWN_DOMAIN_NAMES}

        for domain_name, biomarkers in validated.raw.domains.items():
            if domain_name not in domain_fields:
                raise ValueError(
                    f"Publisher does not recognize domain {domain_name!r} — "
                    f"GroupFeatureSet has no corresponding field for it. This "
                    f"indicates a version mismatch between Feature Extraction "
                    f"and Publisher; dropping this domain's data would violate "
                    f"the lossless-transformation guarantee, so this cycle is "
                    f"rejected instead."
                )
            quality = validated.biomarker_quality[domain_name]
            domain_fields[domain_name] = DomainBiomarkers(
                biomarkers=dict(biomarkers),
                quality={
                    feature_name: self._translate_quality(feature_quality)
                    for feature_name, feature_quality in quality.items()
                },
            )

        return GroupFeatureSet(
            window_start=validated.raw.window_start,
            window_end=validated.raw.window_end,
            motion=domain_fields["motion"],
            pressure=domain_fields["pressure"],
            muscle=domain_fields["muscle"],
            set_observations=[
                self._translate_observation(observation) for observation in validated.set_observations
            ],
        )

    @staticmethod
    def _translate_quality(quality: BiomarkerQuality) -> BiomarkerQualityInfo:
        return BiomarkerQualityInfo(
            status=QualityStatusInfo(quality.status.value),
            flags=[QualityFlagInfo(flag.value) for flag in quality.flags],
            rationale=quality.rationale,
        )

    @staticmethod
    def _translate_observation(observation: SetQualityObservation) -> SetQualityObservationInfo:
        return SetQualityObservationInfo(
            flag=QualityFlagInfo(observation.flag.value),
            domain=observation.domain,
            rationale=observation.rationale,
        )
