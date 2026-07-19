"""
Default ValidationRule registry, assembled from app.config.etl_config.

See docs/development/FEATURE_VALIDATION_DESIGN.md.
"""

from __future__ import annotations

from typing import List, Sequence

from app.config import etl_config
from app.etl.synchronization import SynchronizationGroupConfig

from .rules.domain_cooccurrence_rule import DomainCoOccurrenceRule
from .rules.expected_domain_presence_rule import ExpectedDomainPresenceRule
from .rules.finite_value_rule import FiniteValueRule
from .rules.internal_consistency_rule import InternalConsistencyRule
from .rules.non_negativity_rule import NonNegativityRule
from .rules.sufficiency_rule import SufficiencyRule
from .validation_rule import ValidationRule


def default_validation_rules(
    group_configs: Sequence[SynchronizationGroupConfig],
) -> List[ValidationRule]:
    """
    Build the default V1 ValidationRule list.

    Args:
        group_configs: This session's synchronization groups — the
            same configuration passed to Synchronizer. Required by
            ExpectedDomainPresenceRule to distinguish an expected
            absence (no EMG configured) from a concerning one.

    Returns:
        A new list of rule instances. A fresh list is returned on every
        call; callers that construct a FeatureValidator own their own
        copy.
    """
    return [
        FiniteValueRule(),
        NonNegativityRule(),
        InternalConsistencyRule(),
        DomainCoOccurrenceRule(),
        ExpectedDomainPresenceRule(group_configs=group_configs),
        SufficiencyRule(
            minimum_fraction=etl_config.MINIMUM_SAMPLE_COUNT_FRACTION,
            nominal_sample_interval_ms=etl_config.NOMINAL_SAMPLE_INTERVAL_MS,
        ),
    ]
