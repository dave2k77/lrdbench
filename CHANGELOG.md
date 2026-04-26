# Changelog

## Unreleased

## 1.0.2

- Packaging: republished as `1.0.2` after PyPI also rejected reuse of previously attempted
  `1.0.1` distribution filenames.
- Public contract: unchanged at `1.0.0`; no schema, metric, manifest, or output-column changes.

## 1.0.1

- Packaging: republished the stable research release as `1.0.1` because PyPI does not allow
  previously uploaded `1.0.0` distribution filenames to be reused, even after deletion.
- Public contract: unchanged at `1.0.0`; no schema, metric, manifest, or output-column changes.

- CI: updated GitHub-hosted workflow actions to Node 24-compatible major versions.
- Release: configured the tag release workflow to publish built distributions to PyPI through
  Trusted Publishing using the `pypi` GitHub environment.
- Docs: updated Read the Docs references now that the hosted documentation project exists.

## 1.0.0

- Release: promoted the public research framework from `v0.9.0-rc1` to stable `v1.0.0`.
- Public contract: advanced the output contract to `1.0.0` without changing required files or
  required columns from the release candidate.
- Docs: added governance and maintenance policy, clarified DOI-free citation status, and updated
  migration notes for the stable public release.

- Release candidate: advanced package metadata to `0.9.0rc1` and public output contract to
  `0.9.0-rc1` for schema-freeze review.
- Docs: added release-candidate freeze notes, migration notes, and citation guidance for
  independent public use.
- Release: replaced placeholder release workflow with a build/check/upload-artifact workflow for
  tagged release-candidate artefacts.
- Docs: started external contributor beta with estimator onboarding guide, expanded estimator
  contract, contributor checklist, and issue templates.
- Docs: added third-party estimator workflow and leaderboard submission policy.
- Examples: added a minimal custom estimator, a programmatic custom-estimator benchmark, and test
  utilities for estimator-author smoke tests.
- CLI: added `lrdbench list-metrics` and `lrdbench list-estimators` discovery commands.
- CLI: added `lrdbench list-suites` and public suite-name resolution for `run` and `validate`.
- CLI: added `lrdbench validate-output <run_root>` to check generated reports against the public
  output contract.
- Public contract: added machine-readable output contract for required report/result-store files
  and columns.
- Docs: added output-contract and reproducibility guides for public benchmark beta users.
- Docs: added public-medium reference output counts for contract-valid local runs.
- Packaging: added CI packaging workflow and verified local sdist/wheel build plus installed
  console-script and smoke-report contract checks.
- Packaging: included tracked public suite manifests and output contract assets in built wheels.
- Validation: added statistical generator checks for fGn/fBm scaling, ARFIMA memory behavior,
  MRW intermittency, and fOU mean reversion.
- Validation: added statistical estimator checks for baseline Hurst-proxy and spectral
  long-memory estimators on known fGn/ARFIMA regimes.
- Test coverage: added behavior checks for contamination operators and broader wavelet estimator
  validity/failure paths.
- Test coverage: added observational-source loader checks for inline and CSV-backed series.
- Docs: added public failure-mode taxonomy and known-limitations pages, and expanded estimator
  status metadata with assumptions, expected regimes, and failure risks.
- CLI: added `lrdbench validate <manifest>` for manifest-only checks without running benchmarks.
- Public suites: added tracked `public_small_*` benchmark manifests for canonical ground-truth,
  stress contamination, null false-positive, and sensitivity/disagreement public-alpha checks.
- Public suites: added first-pass tracked `public_medium_*` manifests for more serious local
  benchmark campaigns.
- Documentation: added tracked design specification and estimator status pages for public-alpha
  interpretation.
- Documentation: added explicit interpretation semantics for aggregation, uncertainty,
  leaderboards, and failure outputs.
- Documentation: recorded public-small expected output artefacts and local reference run counts.
- Reporting: default plotting configuration now uses a writable local matplotlib cache when
  `MPLCONFIGDIR` is unset, avoiding read-only home-directory warnings in sandboxed runs.
- Leaderboards: balanced-global diagnostic rows whose names are not declared estimator specs (for
  example `__all_estimators__`) are no longer ranked as estimators.
- Documentation/handoff: added tracked clean-clone paper workflow documentation, fixed the MkDocs
  nav entry for strict builds, and clarified that the frozen design PDF is local-only unless
  explicitly restored.
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
