# Architecture

The Python package under `src/lrdbench/` implements the benchmark loop: manifest load → record materialisation → estimation → evaluation → leaderboard → result store and reports.

Modes (`ground_truth`, `stress_test`, `observational`) share the same orchestration entry point (`runner.BenchmarkRunner`) with mode-specific record sources and evaluators.

**Key modules**

- `cli.main` — argparse commands (`run`, `validate`, `list-metrics`, `list-estimators`, `list-plugins`, `list-suites`, `validate-output`).
- `plugin_loader` — environment-driven discovery and safe loading of third-party estimator plugins.
- `runner` — `BenchmarkRunner` orchestrates the full loop; records `plugin_provenance` in output.

For a target package decomposition (`core/`, `benchmark/`, `evaluation/`, …), see `lrdbench_repo_schema.txt`; migrating the codebase to that layout is a separate refactor.
