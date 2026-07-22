"""Phase 4-authoritative production comparison against permanent benchmarks."""

from __future__ import annotations

import hashlib
import json

from app.config import benchmark_config, production_model_config
from app.experiments.comparison import ExperimentComparator
from app.experiments.contracts import ExperimentResult

from .contracts import ProductionModelSelection
from .exceptions import ProductionSelectionError


class ProductionModelSelector:
    """Delegate ranking to Phase 5 using only completed Phase 4 reports."""

    _REQUIRED_BENCHMARKS = frozenset(
        {
            benchmark_config.DUMMY_MEAN_ALGORITHM,
            benchmark_config.LINEAR_REGRESSION_ALGORITHM,
            benchmark_config.RIDGE_REGRESSION_ALGORITHM,
            benchmark_config.RANDOM_FOREST_ALGORITHM,
        }
    )

    def select(
        self,
        production: ExperimentResult,
        benchmarks: tuple[ExperimentResult, ...],
    ) -> ProductionModelSelection:
        """Compare one production result with all permanent benchmark families."""

        if production.spec.algorithm_identifier != (
            production_model_config.PRODUCTION_MODEL_ALGORITHM
        ):
            raise ProductionSelectionError("Selection requires a production model result.")
        algorithms = {result.spec.algorithm_identifier for result in benchmarks}
        if algorithms != self._REQUIRED_BENCHMARKS or len(benchmarks) != len(
            self._REQUIRED_BENCHMARKS
        ):
            raise ProductionSelectionError(
                "Selection requires exactly one result from every Phase 6 benchmark."
            )
        for result in benchmarks:
            if (
                result.spec.dataset_checksum.lower()
                != production.spec.dataset_checksum.lower()
                or result.spec.evaluation_split is not production.spec.evaluation_split
                or result.evaluation_report.gate_policy
                != production.evaluation_report.gate_policy
                or result.model_candidate.feature_schema
                != production.model_candidate.feature_schema
                or result.model_candidate.target_schema
                != production.model_candidate.target_schema
            ):
                raise ProductionSelectionError(
                    "Production and benchmark evidence must share dataset, schemas, "
                    "split, and release policy."
                )
        comparison = ExperimentComparator().compare((production, *benchmarks))
        recommended = (
            comparison.recommended_experiment_id == production.spec.experiment_id
        )
        rationale = (
            "Phase 5 comparison recommends the production candidate using Phase 4 metrics."
            if recommended
            else "Phase 5 comparison does not recommend the production candidate."
        )
        payload = {
            "benchmark_experiment_ids": sorted(
                result.spec.experiment_id for result in benchmarks
            ),
            "comparison_checksum": comparison.checksum,
            "production_experiment_id": production.spec.experiment_id,
            "production_recommended": recommended,
            "rationale": rationale,
        }
        checksum = hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        return ProductionModelSelection(
            selection_id=f"production-selection-{checksum[:24]}",
            production_experiment_id=production.spec.experiment_id,
            benchmark_experiment_ids=tuple(payload["benchmark_experiment_ids"]),
            comparison=comparison,
            production_recommended=recommended,
            rationale=rationale,
            checksum=checksum,
        )
