# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

`lrdbench` is a reproducible benchmark framework for evaluating long-range dependence (LRD) /
Hurst-exponent estimators. It evaluates estimators in three **modes**, each with its own metrics
and evaluator:

- **ground-truth** — canonical synthetic series with a declared target estimand (bias, MAE, RMSE, coverage, interval width, validity rate).
- **stress-test** — synthetic series under controlled contamination (drift, degradation ratios, validity/coverage collapse).
- **observational** — biomedical / user-provided series with no truth (instability, preprocessing & resampling sensitivity).

The package lives under `src/lrdbench/` (src-layout). Python ≥ 3.11.

## Commands

The repo uses Hatch environments, but every command also works with a plain editable install.

```bash
pip install -e ".[test,dev,docs,reports]"   # standard dev install
pip install -e ".[all]"                       # add ml (scikit-learn) + nn (torch) extras
```

| Task | Command |
|------|---------|
| Run tests | `python -m pytest` (coverage is on by default via addopts) |
| Run one test | `python -m pytest tests/unit/test_foo.py::test_bar` |
| Tests without coverage | `python -m pytest -q -o addopts=''` |
| Skip slow tests | `python -m pytest -m "not slow"` |
| Lint | `python -m ruff check .` |
| Format | `python -m ruff format .` |
| Type check | `python -m mypy src` (strict: `disallow_untyped_defs`) |
| All checks (Hatch) | `hatch run check` → ruff + mypy + pytest |
| Build docs | `python -m mkdocs build --strict` |
| Build package | `python -m build` |

Test markers (registered in `pyproject.toml`, `--strict-markers` is on): `slow`, `statistical`,
`integration`. Tests are organised under `tests/{unit,integration,regression,statistical}`.

### Running benchmarks (the `lrdbench` CLI)

The `run` argument accepts **either a packaged suite name or a path to a manifest YAML**:

```bash
lrdbench run smoke_ground_truth                     # packaged suite by name
lrdbench run smoke_ground_truth --dry-run           # preview the record×estimator grid first
lrdbench run configs/suites/smoke_data_driven.yaml  # local manifest path
lrdbench validate-output reports/<run_id>           # check output contract compliance
```

Other subcommands: `validate` (manifest), `list-metrics`, `list-estimators`, `list-plugins`,
`list-suites`. Always run `--dry-run` before a large suite — it prints mode, record count,
estimator count, total fit jobs, clean/contaminated split, and the global seed.

Data-driven (ML/NN) suites require optional extras: `pip install -e ".[ml,reports]"` for RF/SVR,
`".[nn]"` for CNN/LSTM (torch).

## Architecture

`BenchmarkRunner.run()` in `runner.py` is the single entry point that wires the whole loop:

```
Manifest (YAML) → record materialisation (generators | observational sources)
  → optional ML training (data-driven estimators only)
  → estimation (estimator registry + optional third-party plugins)
  → mode-specific evaluation → leaderboards → CSV result store → reports (HTML/CSV/LaTeX/figures)
```

Each stage is a dedicated module so it can be tested/replaced in isolation. Key modules in
`src/lrdbench/`:

- `manifest.py` — parse YAML into `BenchmarkManifest` dataclasses.
- `execution.py` — `collect_fit_jobs` + `run_fit_jobs`; manages the `(record × estimator)` grid, thread pools, and on-disk estimate caches.
- `evaluator.py` — `GroundTruthEvaluator`, `StressTestEvaluator` (shares GT logic), `ObservationalEvaluator`.
- `leaderboard.py` — `WeightedRankLeaderboardBuilder`.
- `reporter.py` / `result_store.py` — `SimpleHtmlCsvReporter`, `CsvResultStore` (writes `reports/<run_id>/`).
- `registries.py` + `defaults.py` — `EstimatorRegistry`, `GeneratorRegistry`, `ContaminationRegistry` and their `build_default_*` populators.
- `schema.py` — immutable dataclasses (`SeriesRecord`, `EstimateResult`, `MetricSpec`, `ProvenanceRecord`, …) forming the public data contract.
- `interfaces.py` — ABCs (`BaseEstimator`, `BaseGenerator`, `BaseContamination`) that define the extension points.
- `plugin_loader.py` — failure-transparent loading of third-party estimator plugins via env vars.
- `output_contract.py` — enforces `configs/contracts/public_output_contract.json`.

Estimator families live under `estimators/` (`temporal`, `spectral`, `geometric`, `wavelet`,
`data_driven`); generators under `generators/` (fGn, fBm, ARFIMA, MRW, fOU); contaminations under
`contaminations/`.

### Extension points

- **New estimator**: subclass `BaseEstimator`, implement `spec` and `fit()`, register in `defaults.build_default_estimator_registry()` (or use the third-party plugin workflow), declare in a manifest `estimators` block with `name`, `family`, `target_estimand`. See `docs/adding_estimators.md`.
- **New generator**: subclass `BaseGenerator` (`family`, `version`, `generate()`), register in `defaults.build_default_generator_registry()`.
- **New contamination**: subclass `BaseContamination` (`name`, `family`, `version`, `apply()`), register in `defaults.build_default_contamination_registry()`.

## Project-specific conventions

These are non-obvious and enforced by the design — respect them when changing code:

- **Explicit estimands**: every estimator declares the quantity it estimates. Truth-based metrics are *only* used in modes where truth exists — never compute bias/MAE in observational mode.
- **Failure transparency**: invalid outputs, crashes, and missing uncertainty must be recorded explicitly (see `failure_modes.py`), never silently dropped.
- **Provenance**: every record carries a `ProvenanceRecord` with a deterministic `record_id` (SHA-1 of manifest id + family + params + replicate) and a seed derived from the manifest `global_seed`. Runs are meant to be bitwise reproducible from manifest + package version + sources.
- **Output contract**: any change that adds/removes/renames an output CSV column **must** update `configs/contracts/public_output_contract.json` and bump its contract version, or `validate-output` will fail.
- **Packaged suites**: suite YAMLs in `configs/suites/*.yaml` are force-included into the wheel via `[tool.hatch.build.targets.wheel.force-include]` in `pyproject.toml`. When adding a packaged suite, add it there too or it won't ship.
- **Version** is single-sourced from `src/lrdbench/__init__.py` (`hatch.version.path`).

## Scope

This is a research benchmark framework, **not** a clinical/diagnostic tool or a universal "true LRD"
oracle. See `RESEARCH_USAGE.md` for the interpretation policy and `docs/` for the full spec
(`docs/architecture.md`, `docs/estimator_contract.md`, `docs/output_contract.md`).
