"""Tests for Phase 3 immutable dataset contracts."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.dataset_builder.contracts import DatasetBuildSpec, DatasetSplitPolicy, NumericValue


def test_build_spec_rejects_emg_as_a_training_feature_domain() -> None:
    """Measured EMG is a target and cannot enter model features."""

    with pytest.raises(ValidationError, match="Smart Pod"):
        DatasetBuildSpec(
            dataset_name="training",
            target_metric_names=("quadriceps_rms",),
            included_feature_domains=("motion", "muscle"),
        )


def test_split_policy_requires_exact_coverage() -> None:
    """A split policy cannot omit or duplicate examples through invalid fractions."""

    with pytest.raises(ValidationError, match="sum to 1.0"):
        DatasetSplitPolicy(train_fraction=0.7, validation_fraction=0.2, test_fraction=0.2)


def test_numeric_value_rejects_non_finite_values() -> None:
    """Dataset construction never fills or accepts NaN values."""

    with pytest.raises(ValidationError, match="finite"):
        NumericValue(name="feature__motion__peak", value=float("nan"))
