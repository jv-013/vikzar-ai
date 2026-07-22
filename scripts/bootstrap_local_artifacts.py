"""Runs the existing, already-tested Phase 3-7 offline pipeline for real —
against synthetic data, since no real captured training sessions exist —
to produce the artifact files `main.py` needs to boot at all:
`registry/` (the experiment artifact store), a model-references JSON, a
risk-policy JSON, and a baselines JSON.

**What this is, honestly**: this trains the *real* production model
(`app.models.production.ProductionTrainer`, the deterministic MLP) using
*real* training code, evaluated through the *real* Phase 4 evaluation
gates, registered through the *real* Phase 5 experiment/Phase 7
registries — nothing here is faked or invented. The synthetic dataset it
trains on (via `tests.production_models.helpers.make_phase_seven_context`,
the same fixture the test suite itself uses) is exactly what
`app/etl/receiver/fake_transport.py`'s own docstring describes as the
intended use of this pipeline "before real hardware is available" — this
script is that same idea, extended past the test suite to produce a
persistent, bootable artifact set.

**What this is not**: a claim that the resulting model is clinically
valid or ready for real players. It is trained and evaluated on synthetic
data with a known, fixed, artificial feature-target relationship — not a
substitute for training on real captured sessions once those exist. Its
sole purpose is to make `main.py` bootable and the API pipeline
exercisable end-to-end (including a real Firebase sync call, once
credentials exist) before real training data does.

Usage:
    python scripts/bootstrap_local_artifacts.py [--output-dir var/artifacts]

Then export the paths it prints as `VIKZAR_*` environment variables
before running `python main.py` (see `app/api/configuration.py`).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT))

from app.evaluation import ReleaseGatePolicy  # noqa: E402
from app.experiments.artifact_store import ExperimentArtifactStore  # noqa: E402
from app.inference.contracts import ApprovedModelReferences  # noqa: E402
from app.models.production import ProductionModelConfig  # noqa: E402
from tests.production_models.helpers import make_phase_seven_context  # noqa: E402
from tests.risk_engine.helpers import make_baseline, make_config  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=_REPO_ROOT / "var" / "artifacts",
        help="Root directory for the experiment artifact store and generated config files.",
    )
    args = parser.parse_args()
    output_dir: Path = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Building synthetic Phase 3 dataset and Phase 6 benchmarks in {output_dir} ...")
    dataset, benchmarks, gate_policy, trainer, store = make_phase_seven_context(output_dir)
    assert isinstance(store, ExperimentArtifactStore)  # constructed inside output_dir

    print("Training the real production model (deterministic MLP) against it ...")
    outcome = trainer.run(
        experiment_id="production-bootstrap-001",
        dataset=dataset,
        config=ProductionModelConfig(
            hidden_layer_sizes=(16, 8),
            learning_rate=0.02,
            epochs=200,
            random_seed=307,
        ),
        benchmark_results=benchmarks,
        created_by="scripts/bootstrap_local_artifacts.py",
        gate_policy=gate_policy,
    )

    if not outcome.selection.production_recommended:
        print(
            "WARNING: the production model was NOT recommended over the permanent "
            "benchmarks on this synthetic dataset (Phase 5 comparison decision). "
            "Writing its evidence anyway so it's inspectable, but "
            "ApprovedProductionModelLoader will refuse to load it as-is — see "
            f"{outcome.selection.rationale!r}.",
            file=sys.stderr,
        )

    references = ApprovedModelReferences(
        registration=outcome.registration_artifact,
        selection=outcome.selection_artifact,
    )
    references_path = output_dir / "model_references.json"
    references_path.write_text(references.model_dump_json(indent=2), encoding="utf-8")

    risk_policy_path = output_dir / "risk_policy.json"
    risk_policy_path.write_text(make_config().model_dump_json(indent=2), encoding="utf-8")

    baselines_path = output_dir / "baselines.json"
    baselines_path.write_text(
        json.dumps([json.loads(make_baseline().model_dump_json())], indent=2),
        encoding="utf-8",
    )

    print()
    print("Done. Set these before running `python main.py`:")
    print(f'  export VIKZAR_ARTIFACT_ROOT="{output_dir}"')
    print(f'  export VIKZAR_MODEL_REFERENCES_FILE="{references_path}"')
    print(f'  export VIKZAR_RISK_POLICY_FILE="{risk_policy_path}"')
    print(f'  export VIKZAR_BASELINES_FILE="{baselines_path}"')
    print()
    print(
        "The baselines file has one entry, for synthetic player_id "
        '"player-001" — add a real PlayerRiskBaseline per real player '
        "before their data can be processed (PipelineOrchestrator "
        "rejects any player with no baseline)."
    )
    return 0 if outcome.selection.production_recommended else 1


if __name__ == "__main__":
    raise SystemExit(main())
