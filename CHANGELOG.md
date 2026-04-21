# Changelog

## Unreleased

- Paper workflow (local only): publication-oriented benchmark manifests, optional
  `python -m paper_support.run_paper_suites`, staged LaTeX/figures, and `run_index.csv` are
  **not** tracked on the remote repository—see `.gitignore` and `docs/development_handoff.md`.
  Core reporting (LaTeX, figures, metrics) remains in the library for any manifest you run.
- Report polish/completeness: estimator metadata, failures, environment snapshot, artefact index,
  raw artefact metadata exports, richer HTML sections, and publication-oriented LaTeX tables for
  disagreement, sensitivity, benchmark uncertainty, and failures.
- Report figures: core `matplotlib`/`seaborn` plotting support for opt-in
  disagreement/sensitivity heatmaps, benchmark uncertainty interval plots, and false-positive LRD
  plots.
- Benchmark-level uncertainty: optional manifest `uncertainty` block, aggregate bootstrap CIs,
  paired bootstrap estimator differences, raw uncertainty metric scope, and
  `benchmark_uncertainty.csv`.
- Scale/window sensitivity: estimator manifest variants, `parameter_variant_sensitivity`,
  `max_variant_drift`, and `scale_window_sensitivity.csv`.
- Estimator disagreement metrics: added cross-estimator dispersion, pairwise estimator
  disagreement, family-level disagreement summaries, and `estimator_disagreement.csv`.
- Stress-test reporting: contamination severity metadata, `failure_map.csv`, and
  `false_positive_lrd_rate` with manifest-configurable threshold/null handling.
- Synthetic generators: added MRW and fOU generator support.
- Phase 6 documentation: MkDocs + Material (`mkdocs.yml`), Read the Docs config (`.readthedocs.yaml`), expanded `docs/` pages, pymdownx snippets for root markdown, GitHub Action `docs.yml` for `mkdocs build --strict`, and `Documentation` URL in `pyproject.toml`.
- Phase 5 execution: optional `execution.max_workers` for threaded parallel fits, optional `execution.estimate_cache_dir` (+ `cache_read` / `cache_write`) for on-disk pickled `EstimateResult` reuse; manifest validation for `execution` keys.
- Repository layout: benchmark YAML suites under `configs/suites/`; scaffold
  `configs/{estimators,generators,contaminations,reports}/`, `docs/`, `examples/`, and
  `tests/{unit,integration,…}` per `lrdbench_repo_schema.txt`. Optional local-only
  `paper_support/` and `configs/suites/paper/` (ignored by Git) may mirror that layout for drafts.

## 0.1.0

- Initial public alpha: ground-truth, stress-test, and observational modes; baseline estimators and generators; CSV/HTML reporting.
