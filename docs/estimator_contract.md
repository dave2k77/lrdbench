# Estimator contract

Estimators implement `lrdbench.interfaces.BaseEstimator`:

- `spec` → `EstimatorSpec` (name, target estimand, bootstrap/CI parameters, …).
- `fit(record: SeriesRecord) -> EstimateResult` with `point`, optional CIs (`bootstrap_cis` / `ci_low`/`ci_high`), `valid`, `runtime_seconds`, and `diagnostics`.

Registry callables live in `lrdbench.defaults.build_default_estimator_registry()` (e.g. `RS`, `GPH`).
