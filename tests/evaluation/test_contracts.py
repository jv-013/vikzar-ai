"""Evaluation contract validation tests."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.evaluation import PredictionRow

from .helpers import make_dataset_result, make_prediction_set


def test_prediction_set_rejects_prediction_without_phase_three_truth() -> None:
    """Evaluation accepts only predictions aligned to submitted direct targets."""

    prediction_set = make_prediction_set(make_dataset_result())
    with pytest.raises(ValidationError, match="reference submitted ground-truth"):
        prediction_set.model_validate(
            prediction_set.model_dump(mode="python")
            | {
                "prediction_rows": prediction_set.prediction_rows
                + (PredictionRow(example_id="unknown", target_name="target__quadriceps_rms", value=0.2),)
            }
        )
