"""Immutable evaluation-report storage integration tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.evaluation import EvaluationFramework, EvaluationReportStorage
from app.evaluation.exceptions import EvaluationStorageError

from .helpers import make_dataset_result, make_prediction_set


def test_writes_and_verifies_immutable_evaluation_report(tmp_path: Path) -> None:
    """Stored report includes verified artifact and embedded deterministic checksums."""

    report = EvaluationFramework().evaluate(make_prediction_set(make_dataset_result()))
    destination = tmp_path / report.report_id
    storage = EvaluationReportStorage()

    storage.write(report, destination)
    loaded = storage.verify(destination)

    assert loaded.model_dump(mode="json") == report.model_dump(mode="json")
    assert set(path.name for path in destination.iterdir()) == {"evaluation_report.json", "checksums.json"}


def test_rejects_tampered_evaluation_report(tmp_path: Path) -> None:
    """Consumers cannot accept a changed persisted report."""

    report = EvaluationFramework().evaluate(make_prediction_set(make_dataset_result()))
    destination = tmp_path / report.report_id
    storage = EvaluationReportStorage()
    storage.write(report, destination)
    (destination / "evaluation_report.json").write_text("{}", encoding="utf-8")

    with pytest.raises(EvaluationStorageError, match="checksum"):
        storage.verify(destination)


def test_same_report_writes_byte_identically(tmp_path: Path) -> None:
    """Reproducible reports retain identical artifact and manifest bytes."""

    report = EvaluationFramework().evaluate(make_prediction_set(make_dataset_result()))
    storage = EvaluationReportStorage()
    first = tmp_path / "first"
    second = tmp_path / "second"
    storage.write(report, first)
    storage.write(report, second)

    for filename in ("evaluation_report.json", "checksums.json"):
        assert (first / filename).read_bytes() == (second / filename).read_bytes()
