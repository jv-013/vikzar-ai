"""Atomic checksum-verifiable local persistence for evaluation reports."""

from __future__ import annotations

import hashlib
import json
import shutil
import uuid
from pathlib import Path

from .contracts import EvaluationReport
from .exceptions import EvaluationStorageError


class EvaluationReportStorage:
    """Store immutable reports locally; cloud replication remains optional and external."""

    _REPORT_FILE = "evaluation_report.json"
    _CHECKSUM_FILE = "checksums.json"

    def write(self, report: EvaluationReport, destination: Path) -> None:
        """Atomically persist a new report directory without overwriting evidence."""

        destination = destination.resolve()
        if destination.exists():
            raise EvaluationStorageError(f"Evaluation report destination already exists: {destination}")
        if report.report_checksum != self._embedded_checksum(report):
            raise EvaluationStorageError("Evaluation report embedded checksum is invalid.")
        staging = destination.with_name(f".{destination.name}.staging-{uuid.uuid4().hex}")
        try:
            staging.mkdir(parents=True)
            report_path = staging / self._REPORT_FILE
            self._write_json(report_path, report.model_dump(mode="json"))
            self._write_json(
                staging / self._CHECKSUM_FILE,
                {"algorithm": "sha256", "artifacts": {self._REPORT_FILE: self._sha256(report_path)}},
            )
            staging.rename(destination)
        except EvaluationStorageError:
            shutil.rmtree(staging, ignore_errors=True)
            raise
        except (OSError, ValueError, TypeError) as exc:
            shutil.rmtree(staging, ignore_errors=True)
            raise EvaluationStorageError(f"Unable to persist evaluation report: {destination}") from exc

    def verify(self, destination: Path) -> EvaluationReport:
        """Verify file and embedded report checksums before returning a report."""

        destination = destination.resolve()
        try:
            manifest = json.loads((destination / self._CHECKSUM_FILE).read_text(encoding="utf-8"))
            artifacts = manifest["artifacts"]
            expected_hash = artifacts[self._REPORT_FILE]
            report_path = destination / self._REPORT_FILE
            if (
                manifest.get("algorithm") != "sha256"
                or set(artifacts) != {self._REPORT_FILE}
                or self._sha256(report_path) != expected_hash
            ):
                raise EvaluationStorageError("Evaluation report artifact checksum verification failed.")
            report = EvaluationReport.model_validate_json(report_path.read_text(encoding="utf-8"))
        except EvaluationStorageError:
            raise
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, KeyError, ValueError, TypeError) as exc:
            raise EvaluationStorageError("Evaluation report storage is invalid.") from exc
        if report.report_checksum != self._embedded_checksum(report):
            raise EvaluationStorageError("Evaluation report embedded checksum verification failed.")
        return report

    @staticmethod
    def _embedded_checksum(report: EvaluationReport) -> str:
        return hashlib.sha256(
            json.dumps(
                report.model_dump(mode="json", exclude={"report_id", "report_checksum"}),
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()

    @staticmethod
    def _write_json(path: Path, payload: object) -> None:
        path.write_text(
            json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n",
            encoding="utf-8",
        )

    @staticmethod
    def _sha256(path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()
