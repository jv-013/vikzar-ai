"""Unit tests for default_validation_rules()."""

from __future__ import annotations

from app.etl.feature_validation.defaults import default_validation_rules
from app.etl.feature_validation.rules.domain_cooccurrence_rule import DomainCoOccurrenceRule
from app.etl.feature_validation.rules.expected_domain_presence_rule import ExpectedDomainPresenceRule
from app.etl.feature_validation.rules.finite_value_rule import FiniteValueRule
from app.etl.feature_validation.rules.internal_consistency_rule import InternalConsistencyRule
from app.etl.feature_validation.rules.non_negativity_rule import NonNegativityRule
from app.etl.feature_validation.rules.sufficiency_rule import SufficiencyRule
from app.etl.synchronization import SynchronizationGroupConfig

GROUP = SynchronizationGroupConfig(
    group_id="left_lower_limb", primary_motion_device_id="left_smart_pod", emg_device_id="left_emg_band"
)


def test_returns_the_six_v1_rules() -> None:
    rules = default_validation_rules(group_configs=[GROUP])

    rule_types = {type(rule) for rule in rules}
    assert rule_types == {
        FiniteValueRule,
        NonNegativityRule,
        InternalConsistencyRule,
        DomainCoOccurrenceRule,
        ExpectedDomainPresenceRule,
        SufficiencyRule,
    }


def test_returns_a_fresh_list_on_each_call() -> None:
    first = default_validation_rules(group_configs=[GROUP])
    second = default_validation_rules(group_configs=[GROUP])

    assert first is not second
