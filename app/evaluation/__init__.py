"""Offline, algorithm-independent scientific evaluation for Phase 3 datasets."""

from .contracts import (
    EvaluationReport,
    EvaluationSlice,
    GroundTruthRow,
    MetricResult,
    PredictionProvenance,
    PredictionRow,
    PredictionSet,
    ReleaseGatePolicy,
)
from .evaluator import EvaluationFramework
from .report_storage import EvaluationReportStorage

__all__ = [
    "EvaluationFramework",
    "EvaluationReport",
    "EvaluationReportStorage",
    "EvaluationSlice",
    "GroundTruthRow",
    "MetricResult",
    "PredictionProvenance",
    "PredictionRow",
    "PredictionSet",
    "ReleaseGatePolicy",
]
