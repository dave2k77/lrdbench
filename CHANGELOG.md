# Changelog

## Unreleased

### Interval candidate development comparison
- Speed up Higuchi's lag/offset sums while preserving the original equation;
  bump its version to 0.3.0 for the changed floating-point summation order.
- Add research-only block-basic, fitted-zero-mean-fGn percentile/basic and
  untapered GPH normal interval candidates, with independent equation checks.
- Compare candidates on 448 shared records, retaining model-boundary diagnostics,
  all bootstrap-statistic draws, failures and paired coverage/width differences.
  Persistent fGn coverage improves with model-based basic intervals, but the
  short-memory controls still fail. No package default interval is changed.

### Resumable calibration development
- Add a dedicated research runner with stable shared inputs, separate input and
  resampling streams, per-fit checkpoints, single-writer locking and strict resume
  checks against configuration, source, environment and input/result hashes.
- Export complete failure/interval denominators and stream raw research exports by
  process/length cell. Keep the public output contract and historical bundles unchanged.
- Add a Windows x64 / Python 3.14.5 dependency lock with distribution hashes and
  verify a separate installation. Profile all 36 development cells with two records
  each; retain the full 399 draws per candidate interval for cost measurement only.

### Remaining classical-method and generator audit
- Remove silent H clipping from temporal estimators and wavelet slope conversion.
  Temporal and primary wavelet regressions expose out-of-range points and resamples.
  Undefined constant/nonfinite inputs no longer produce valid Whittle/wavelet fits.
- Record bounded spectral optimizer hits and identify the legacy
  ModifiedLocalWhittle implementation as ordinary local Whittle. Make Whittle's
  scale normalization internally consistent (the old discrepancy was constant in d).
- Correct the profiled scale of the experimental WaveletWhittle likelihood;
  verify against joint numerical optimization of H and scale. This method is
  outside the paper's retained roster and remains an experimental approximation.
- Add `ARFIMA` parameter `method: cholesky` for its exact stationary Gaussian
  covariance; preserve the default `truncated_ma` for historical reproduction.
  Record algorithm, truncation and scale interpretation; declare existing fGn/fBm
  covariance jitter and reject invalid H/sigma inputs. Separate simulation methods
  in metric strata.
- Add independent projection, moving-window, spectral-integral and covariance-map
  checks, plus a shared-input development pilot across all 19 paper configurations.
- Resolve the four baseline typing findings and the new diagnostics annotation;
  type checking passes with the installed Python 3.14 target.

### Estimator equations and explicit stress metrics
- Correct the GPH slope-to-d conversion for the squared-sine regressor. This also
  changes Periodogram, PeriodogramBeta and the GPH-based threshold discriminator.
  Regression outputs are unclipped; constant/nonfinite spectral inputs are invalid.
- Restore Higuchi's missing lag normalization. GHE now fits absolute q-th moments
  (default q = 2, q = 1 available); remove the forced H = 0.5 fallback and clipping.
  Both geometric estimators expose path/increment input choice and resample
  increments for candidate bootstrap intervals. Nonzero `flat_slope_tol` is rejected.
- Add explicit absolute/signed drift, absolute-error inflation, paired aggregate
  MAE ratio, coverage-loss rate, net coverage loss and persistence-exceedance names.
  Preserve legacy calculations; count available/missing pairs and strata. Reject
  scalar-bootstrap uncertainty requests for the paired ratio and signed-drift rankings.
- Add analytical equation checks and a reproducible diagnostic pilot. These repairs
  do not certify interval calibration or validate all methods. Research reruns and
  manuscript reconciliation remain pending; historical outputs are unchanged.

### Benchmark foundation repairs
- Equal component values receive average ranks; missing and nonfinite values rank
  last in both directions. Composite ties apply the declared primary/named metric,
  and unresolved ties share competition ranks. Estimator names affect display only.
- Preserve legacy `level_shift` as a constant offset; add explicit `constant_offset`
  and `step_change` operators. Zero outlier rate now leaves the signal unchanged.
- Bootstrap diagnostics record attempted, retained, invalid and failed draws, with
  failure categories. Replicate failures preserve valid point estimates; zero
  replicates disables resampling. Add `ci_availability` at each requested level.
- Default CI endpoints now represent 95% only; other levels remain explicitly
  labelled. Evaluation rejects unavailable, invalid, reversed and nonfinite CIs.
- Seed derivation now includes `global_seed`, previously ignored. Estimate cache
  keys include the record seed and a shared-fitting version to avoid stale results.
- Stress figures separate drift and error-ratio panels and estimator values.
  Global benchmark uncertainty figures separate metrics and levels, retain the full
  method roster and draw the actual interval endpoints.
- These changes require new research outputs. Historical exports are preserved;
  mathematical estimator validation and uncertainty calibration remain pending.

### Estimand triangle: spectral exponent and timescale
- Estimands: added `spectral_exponent_beta` (`β = 2H − 1`, `H = (β + 1) / 2`) and `timescale_tau`
  (autocorrelation-decay time constant, in samples).
- Estimators: added `PeriodogramBeta` (low-frequency spectral slope, targets
  `spectral_exponent_beta`) and `ACFDecay` (new `timescale` family, exponential ACF-decay fit,
  targets `timescale_tau`).
- Records: added `SeriesRecord.additional_truths` so one realisation can carry ground truth for
  several estimands. fGn declares `(H, β = 2H − 1, τ = None)`; fOU declares `(H, τ = 1/(θ·dt))`.
- Evaluator: each estimator is scored only against the truth for its own `target_estimand` via the
  new `truth_for` resolver.
- Suites: `neural_timescale_triangle_ground_truth` and `smoke_neural_timescale`.

### True-vs-apparent LRD discrimination
- Generators: added the `multi_timescale` generator — a finite superposition of AR(1) timescales
  that is genuinely short-memory (truth `H = 0.5`) but mimics power-law scaling over finite samples,
  a controlled null for the LRD illusion. Severity is graded by `tau_max`.
- Suites: `neural_lrd_discrimination_ground_truth` and `smoke_lrd_discrimination` score
  `false_positive_lrd_rate` on the apparent-LRD nulls.

### Per-series LRD model selection
- Estimand: added the decision estimand `lrd_class` (binary `is_lrd` labels on fGn, ARFIMA and
  `multi_timescale`).
- Metrics: added the classification family `roc_auc`, `balanced_accuracy`, `true_positive_rate`,
  `false_positive_rate`, computed over the score/label population. `MetricSpec.kind`
  (`regression` | `classification` | `neutral`) routes metrics by estimand so error metrics never
  apply to a decision estimand.
- Estimators: added four discriminators targeting `lrd_class` — `ThresholdHurstDiscriminator`
  (baseline), `LowFreqSpectralDiscriminator`, `ScaleCrossoverDiscriminator`, and
  `ICModelSelectDiscriminator` (Whittle-BIC ARFIMA vs AR).
- Suites: `neural_lrd_model_selection_ground_truth` and `smoke_lrd_model_selection`
  (`discrimination_power` leaderboard ranked by ROC-AUC).

### Output contract
- Contract version `1.0.0` → `1.1.0`: added the conditional `raw/truths.csv` long-format ledger of
  all declared truths (primary + companion). Additive — existing files keep their columns.

## 1.2.1

> Note: versions 1.1.0, 1.1.1, and 1.2.0 were skipped. Their PyPI filenames are permanently
> reserved from prior deleted uploads (PyPI does not allow filename reuse), so 1.2.1 is the first
> published release of the changes below. This release is single-sourced, archived on Zenodo
> (concept DOI `10.5281/zenodo.20937726`), and published to PyPI.

### Nonstationary LRD benchmarking
- Generators: added `nonstationary_lrd` generator family producing LRD series with controlled
  nonstationarity mechanisms (e.g. trend, variance, and regime modulation).
- Preprocessing: added `preprocessing` package with nonstationarity-correction utilities and shared
  helpers for correction-aware benchmarking.
- Suites: added nonstationary LRD benchmark suites, including correction-aware,
  ML-vs-classical, and out-of-distribution (OOD) protocols.
- Evaluation/reporting: extended the evaluator and reporter to support correction-aware
  nonstationary benchmarking and the associated metrics.

### Estimator correctness fixes
- Wavelet: fixed inverted log-scale Hurst convention across the OLS and wavelet family estimators.
- Spectral: fixed the spectral estimand convention and sped up ARFIMA convolution.
- Execution: fixed estimate-cache invalidation so cached estimates are not reused across
  incompatible configurations.
- Data-driven: fixed data-driven estimator correctness bugs and hardened resampling.

### Tooling & CI
- Tests: skip torch-dependent tests when the `nn` extra is absent.
- CI: install the `dev` extra so `ruff` is available in the tests workflow.

## 1.0.3

### Design & CLI
- CLI: added `--dry-run` flag to `lrdbench run` to preview the record-estimator grid without
  fitting estimators or writing outputs.
- Core: added `BenchmarkRunner.preview()` method for dry-run record materialisation and grid-size
  reporting.
- Contracts: added machine-readable manifest JSON Schema at
  `configs/contracts/manifest_schema.json`.

### Documentation & Onboarding
- Docs: promoted dry-run workflow guidance into README, quickstart, benchmark protocol, and
  contributor smoke-test instructions.
- Docs: expanded API reference coverage for `BenchmarkRunner.preview()`, schema dataclasses,
  validation/output-contract helpers, bootstrap utilities, plugin discovery, public assets, and
  testing helpers.
- Packaging/docs: clarified that the `all` optional extra includes data-driven dependencies and
  documented lighter development-install alternatives.
- Docs: rewrote `docs/architecture.md` into a full contributor guide covering the benchmark loop,
  module responsibilities, extension points, provenance, and output contract.
- Docs: expanded `CONTRIBUTING.md` with architecture pointers, validation commands, and smoke-test
  verification steps.
- Docs: added `docs/faq.md` covering installation errors, manifest validation, estimator invalidity,
  bootstrap intervals, reproducibility checks, caching, plugins, and observational CSV workflows.
- Docs: added `docs/parameter_glossary.md` with tables explaining common parameters across all
  estimator families and execution blocks.
- Docs: added bootstrap methodology section to `docs/benchmark_protocol.md` documenting the default
  block-length choice and override mechanism.
- Notebooks: fleshed out all four tutorial notebooks with explanatory markdown, intermediate
  printouts, and additional code cells (estimates-vs-truth plots, failure-map inspection, stability
  metrics, and custom-estimator walkthroughs).
- Terminology: aligned all canonical suite manifests to use `family: temporal` consistently
  (previously `time_domain` in YAMLs vs `temporal` in docs).

### API Documentation
- Core: added comprehensive docstrings to `BaseEstimator`, `BaseGenerator`, `BaseContamination`,
  `BaseEvaluator`, `BaseReporter`, `BaseResultStore`, `BenchmarkRunner.run()`,
  `run_manifest_path()`, `run_manifest_mapping()`, and key schema dataclasses
  (`SeriesRecord`, `EstimateResult`, `EstimatorSpec`, `MetricSpec`, `TruthSpec`).
- Core: expanded docstrings for `bootstrap_statistic_distribution`,
  `symmetric_percentile_cis`, and `circular_block_resample`.

### Mathematical Implementation Hardening
- Estimators: deduplicated GPH and Periodogram regression cores into a shared
  `_log_periodogram_regression_d()` with optional `taper` support.
- Estimators: fixed GPH to honour the manifest `m` bandwidth parameter when using the shared
  regression core.
- Estimators: added cosine-bell (`taper: cosine`) spectral tapering to GPH and Periodogram
  to reduce periodogram bias from spectral leakage.
- Estimators: added Anis-Lloyd finite-sample correction to RS as an opt-in parameter
  `use_anis_lloyd_correction`. Uses the exact 1976 formula computed via `scipy.special.gammaln`
  for numerical stability.
- Estimators: corrected RS estimation to fit the R/S log-log slope across subseries scales rather
  than deriving the Hurst proxy from a single full-record R/S value.
- Estimators: documented the GHE `flat_slope_tol` heuristic explicitly in docstrings and
  `docs/estimator_status.md`. Users can disable it by setting `flat_slope_tol: 0.0`.
- Estimators: documented the known finite-sample bias of the classical RS estimator in
  `docs/estimator_status.md`.
- Generators: updated `simulate_fou` docstring to state clearly that it uses a first-order
  Euler–Maruyama-style discretisation and is not an exact simulation of the continuous fOU
  process.

### Plugin discovery (prior)
- Plugin discovery: added automatic third-party estimator loading via `LRD_BENCH_ESTIMATOR_PLUGIN`
  (import-style) and `LRD_BENCH_ESTIMATOR_PLUGIN_PATH` (file-path) environment variables.
- CLI: added `--no-plugins` flag to `lrdbench run` and `lrdbench list-estimators` to skip automatic
  plugin discovery.
- CLI: added `lrdbench list-plugins` command to inspect discovered third-party plugins.
- Core: added `lrdbench.plugin_loader` module with safe, failure-transparent plugin loading.
- Core: `BenchmarkRunOutput` now carries `plugin_provenance` to track loaded plugins, versions,
  source hashes, and load failures.
- Docs: updated estimator contract and third-party estimator workflow for plugin discovery.
- Estimators: added aggregation-based temporal Hurst-proxy estimators `AbsoluteMoment`,
  `Variance`, and `VarianceResidual`.
- Docs: added bundled-estimator documentation covering registry names, targets, parameters, and
  aggregation-method interpretation notes.
- Estimators: added experimental data-driven baselines `MLRandomForest`, `MLSVR`, `MLCNN`, and
  `MLLSTM` targeting `hurst_scaling_proxy`.
- Manifests: added optional `ml_training` for run-local supervised training before benchmark
  estimation.
- Suites/examples: added `smoke_data_driven.yaml` and
  `examples/data_driven_baseline_benchmark.py` for RF/SVR stress-test comparison.
- Docs: added data-driven estimator installation, manifest, interpretation, and artefact guidance.

## 1.0.2

- Packaging: first PyPI-published stable package release.
- Public contract: unchanged at `1.0.0`; no schema, metric, manifest, or output-column changes.

## 1.0.1

- Packaging: internal packaging-only release candidate for PyPI publication.
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
