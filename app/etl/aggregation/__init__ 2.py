"""
Aggregation package.

An ETL composition layer between Feature Validation and Publisher — see
docs/development/AGGREGATION_DESIGN.md.

AggregatedFeatureCycle is exported for use elsewhere within app/etl
(e.g. Publisher). It must never be imported outside app/etl.
"""

from .aggregated_feature_cycle import AggregatedFeatureCycle
from .feature_set_aggregator import AggregatedFeatureCycleConsumer, FeatureSetAggregator

__all__ = [
    "FeatureSetAggregator",
    "AggregatedFeatureCycleConsumer",
    "AggregatedFeatureCycle",
]
