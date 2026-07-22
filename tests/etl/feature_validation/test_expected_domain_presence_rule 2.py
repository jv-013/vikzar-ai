"""Unit tests for ExpectedDomainPresenceRule."""

from __future__ import annotations

from app.etl.feature_validation.quality import QualityFlag
from app.etl.feature_validation.rules.expected_domain_presence_rule import ExpectedDomainPresenceRule
from app.etl.synchronization import SynchronizationGroupConfig

from .helpers import make_extracted_feature_set

TRAINING_MODE_GROUP = SynchronizationGroupConfig(
    group_id="left_lower_limb", primary_motion_device_id="left_smart_pod", emg_device_id="left_emg_band"
)
MATCH_MODE_GROUP = SynchronizationGroupConfig(
    group_id="right_lower_limb", primary_motion_device_id="right_smart_pod", emg_device_id=None
)


def test_flags_muscle_absent_when_emg_configured() -> None:
    rule = ExpectedDomainPresenceRule(group_configs=[TRAINING_MODE_GROUP])
    extracted = make_extracted_feature_set(
        group_id="left_lower_limb", domains={"motion": {"peak_resultant_acceleration": 5.0}}
    )

    result = rule.evaluate(extracted)

    assert len(result.set_observations) == 1
    assert result.set_observations[0].flag == QualityFlag.EXPECTED_DOMAIN_ABSENT
    assert result.set_observations[0].domain == "muscle"


def test_does_not_flag_muscle_present_when_emg_configured() -> None:
    rule = ExpectedDomainPresenceRule(group_configs=[TRAINING_MODE_GROUP])
    extracted = make_extracted_feature_set(
        group_id="left_lower_limb", domains={"muscle": {"quadriceps_rms": 1.0}}
    )

    result = rule.evaluate(extracted)

    assert result.set_observations == ()


def test_does_not_flag_muscle_absent_when_emg_not_configured() -> None:
    rule = ExpectedDomainPresenceRule(group_configs=[MATCH_MODE_GROUP])
    extracted = make_extracted_feature_set(
        group_id="right_lower_limb", domains={"motion": {"peak_resultant_acceleration": 5.0}}
    )

    result = rule.evaluate(extracted)

    assert result.set_observations == ()


def test_flags_muscle_present_when_emg_not_configured() -> None:
    rule = ExpectedDomainPresenceRule(group_configs=[MATCH_MODE_GROUP])
    extracted = make_extracted_feature_set(
        group_id="right_lower_limb", domains={"muscle": {"quadriceps_rms": 1.0}}
    )

    result = rule.evaluate(extracted)

    assert len(result.set_observations) == 1
    assert result.set_observations[0].flag == QualityFlag.UNEXPECTED_DOMAIN_PRESENT


def test_stays_silent_for_an_unconfigured_group_id() -> None:
    rule = ExpectedDomainPresenceRule(group_configs=[TRAINING_MODE_GROUP])
    extracted = make_extracted_feature_set(
        group_id="unknown_group", domains={"motion": {"peak_resultant_acceleration": 5.0}}
    )

    result = rule.evaluate(extracted)

    assert result.set_observations == ()
