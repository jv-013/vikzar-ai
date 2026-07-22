# Repo Hygiene Report

**Status: report only. No files have been deleted or modified.** This document lists every duplicate and dead-stub file found, the evidence gathered for each, and a recommendation — awaiting an explicit decision before anything is removed, per instruction.

Methodology: every claim below was verified directly against this repository's working tree (not inferred), using `diff`, `diff -w`, `grep`, `find -size 0`, `git status`, and an actual `pytest --collect-only` run in a Python 3.12 virtualenv. Nothing here is a guess.

---

## 1. Duplicate `<name> 2.py` files (105 files)

### What they are

Every file matching `* 2.py` across `app/etl/` and `tests/etl/` has an exact-named counterpart without the `" 2"` suffix (e.g. `app/etl/calibration/calibrator.py` and `app/etl/calibration/calibrator 2.py`).

### Evidence

- **Content**: `diff -w` (whitespace/line-ending-insensitive) across **all 105 pairs** reports **zero differences** in every single case. A raw `diff` (whitespace-sensitive) shows 96 of the 105 pairs as "fully different" line-by-line — but this is misleading: `file` confirms the canonical files use LF line endings and every `" 2.py"` duplicate uses CRLF line endings. Once that's normalized, the content is byte-for-byte identical. The other 9 pairs are literally byte-identical with no normalization needed. **Conclusion: all 105 are the same file, saved twice with different line-ending conventions** — almost certainly an artifact of a Windows-originated copy/extraction/checkout, not an intentional variant.
- **Imports**: a repo-wide grep for any reference to a `" 2.py"` filename, or any import statement naming a module with a space in it, returns zero matches in `app/`, `tests/`, or `main.py`. Python cannot `import` a module whose filename contains a space via a normal `import` statement, so the `app/etl/*` duplicates are structurally unreachable as library code regardless.
- **Git status**: all 105 are tracked (`git status` shows each as `M`, modified relative to the last commit) — not stray untracked files.

### A finding the file-level check alone would miss: pytest actually runs the test-file duplicates

The 55 duplicates under `tests/etl/` (test modules + `__init__ 2.py`/`helpers 2.py` fixtures) **are** collected and executed by `pytest`, unlike the `app/etl/` duplicates — pytest's own file-discovery/import machinery tolerates the space in the filename even though a plain `import` statement can't. Verified directly: `pytest --collect-only -q` inside `tests/etl/calibration/` collects **both** `test_calibrator.py::test_calibrates_a_matched_frame` **and** `test_calibrator 2.py::test_calibrates_a_matched_frame` as two separate, fully executed test items running the identical assertion. Repo-wide, **267 of the reported 775 "passing tests" are exact re-executions of a test that already exists under its canonical name** — meaning the true unique test count is closer to **508**, and every affected suite's runtime is roughly doubled for no additional coverage. This is silent, measurable waste, not just clutter — worth knowing before citing "775 tests passing" as a coverage figure anywhere (this report supersedes that figure with the corrected ~508 unique count).

### Recommendation

**Safe to delete, all 105.** No import ever breaks (nothing imports them by their spaced filename; nothing else could). No test coverage is lost (every duplicated test has an identical, already-passing twin under the canonical name). The only observable effect of deleting them is that `pytest` will report a smaller, *more accurate* number — that's a correction, not a regression, and should be expected/explained when it happens, not mistaken for missing tests.

Full file list: `app/etl/{aggregation,calibration,feature_extraction,feature_validation,filtering,publisher,synchronization}/*` and `tests/etl/{aggregation,calibration,feature_extraction,feature_validation,filtering,publisher,synchronization,windowing}/*` — every `* 2.py` under those trees (105 files total; run `find . -name "* 2.py" -not -path "./.git/*"` to reproduce the exact list).

---

## 2. Zero-byte / dead-stub files

Excludes `__init__.py` files, which are conventionally allowed to be empty. Every file below was checked with a repo-wide grep for any import of its module path; none were found for any of them.

### 2a. Abandoned model-framework stubs (`app/models/`)

`catboost_model.py`, `lightgbm_model.py`, `neural_network.py`, `xgboost_model.py`, `model_manager.py` — all 0 bytes. `requirements.txt` still lists `xgboost`, `lightgbm`, `catboost`, `scikit-learn` as dependencies, but a repo-wide grep found **zero** `import sklearn`/`xgboost`/`lightgbm`/`catboost` anywhere in `app/`. The real model implementations (`dummy_baseline.py`, `linear_regression.py`, `ridge_regression.py`, `random_forest.py`, `production/model.py`) are all hand-rolled NumPy, deliberately avoiding these frameworks (per `docs/ai/06_BENCHMARK_MODELS.md`'s no-pickle rationale). These 5 files are remnants of an earlier, abandoned direction.
**Recommendation:** safe to delete the 5 files. Separately worth a decision: also drop `xgboost`/`lightgbm`/`catboost`/`scikit-learn` from `requirements.txt` (unused dependencies, real install-size/CI-time cost) — not part of this report's file list, flagging for awareness.

### 2b. Abandoned AWS cloud direction (`app/cloud/`)

`app/cloud/aws/{__init__,s3,dynamodb,rds}.py` are all 0 bytes. But the check went further: **the entire `app/cloud/` package is dead**, not just the AWS subfolder — `queue.py` (13 lines), `uploader.py` (13 lines), `storage.py` (13 lines), `repository.py` (27 lines), and `__init__.py` (8 lines) are small-but-real `NotImplementedError`-stub abstract classes, and a repo-wide grep for `app.cloud` or `from app.cloud` anywhere in `app/`, `tests/`, or `main.py` returns **zero matches**. Nothing in the codebase references this package at all. `docs/architecture/07_CLOUD_ARCHITECTURE.md` describes the AWS-based design this package was scaffolded for; the actually-implemented Firebase-based design lives entirely in `app/api/firebase.py` instead (see the platform-lock architecture review for more on this).
**Recommendation:** this is a broader finding than "just the empty AWS files" — the whole `app/cloud/` directory (9 files) is unreferenced and safe to delete as a unit, if you agree with retiring the AWS direction rather than keeping the shell for a possible future S3/DynamoDB path.

### 2c. Abandoned data-source abstraction (`app/data_source/`)

`__init__.py`, `etl.py`, `synthetic.py` are 0 bytes; `base.py` (36 lines, a real `DataSource` abstract base class) is not. All four have zero references anywhere in the repo — the whole package, not just the empty files within it, is dead.
**Recommendation:** safe to delete the whole `app/data_source/` directory (4 files) as a unit.

### 2d. Dead service-layer stubs (`app/services/`)

`ai_service.py`, `api_service.py`, `cloud_service.py`, `etl_service.py` are all 0 bytes; only `__init__.py` (3 lines) has content. Zero references anywhere.
**Recommendation:** safe to delete the whole `app/services/` directory (5 files) as a unit — the real service logic lives directly in `app/api/`, `app/inference/`, etc.

### 2e. Dead config stubs (`app/config/`)

Unlike 2a–2d, `app/config/` is very much alive (17 files, most real and actively imported per-phase config) — but 5 of its files are 0-byte remnants of an earlier, coarser naming scheme, superseded by the current one-config-per-phase convention: `app_config.py`, `api_config.py`, `cloud_config.py`, `constants.py`, `ml_config.py`. Zero references to any of them.
**Recommendation:** safe to delete these 5 specific files; leave the rest of `app/config/` untouched.

### 2f. Dead file inside an otherwise-live package (`app/inference/`)

`app/inference/postprocessing.py` is 0 bytes, isolated inside an otherwise fully real, heavily-used package (`inference_engine.py`, `contracts.py`, `model_loader.py`, `validation.py`, etc., all real and imported). Zero references.
**Recommendation:** safe to delete this one file; leave the rest of `app/inference/` untouched.

### 2g. Dead benchmarking stubs (`app/benchmarking/`)

`benchmark.py`, `datasets.py`, `evaluator.py`, `feature_importance.py` are 0 bytes, alongside the real `trainer.py` (84 lines, `BenchmarkTrainer`, genuinely used by `tests/`). Zero references to any of the 4 empty files.
**Recommendation:** safe to delete these 4 files; leave `trainer.py` and `__init__.py` untouched.

---

## Summary table

| Group | Files | Safe to delete? | Scope |
|---|---|---|---|
| `* 2.py` duplicates | 105 | Yes | Individually, across `app/etl/`, `tests/etl/` |
| `app/models/{catboost,lightgbm,neural_network,xgboost}_model.py` + `model_manager.py` | 5 | Yes | Individually |
| `app/cloud/**` | 9 | Yes | Whole directory |
| `app/data_source/**` | 4 | Yes | Whole directory |
| `app/services/**` | 5 | Yes | Whole directory |
| `app/config/{app,api,cloud}_config.py`, `constants.py`, `ml_config.py` | 5 | Yes | Individually, `app/config/` otherwise untouched |
| `app/inference/postprocessing.py` | 1 | Yes | Individually, `app/inference/` otherwise untouched |
| `app/benchmarking/{benchmark,datasets,evaluator,feature_importance}.py` | 4 | Yes | Individually, `app/benchmarking/` otherwise untouched |
| **Total** | **138** | | |

Not included here (deliberately, per scope): the unwired `knowledge_base`/`lookup_engine`/`feature_enhancement`/`muscle_activity_estimation` subsystem (~2,232 lines, real and tested, just not called by the live orchestrator) is a *design* question, not a hygiene one — covered separately in the architecture review, not this cleanup list, since deleting real working code is a different kind of decision than deleting confirmed-dead stubs.

No deletions have been made. This report is the input to that decision.
