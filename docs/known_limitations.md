# Known Limitations

This alpha release is designed for reproducible benchmarking experiments, not definitive estimator
rankings.

## Estimators

- No estimator is currently labelled reference-grade.
- Hurst-scaling proxies and ARFIMA long-memory parameter estimates are related only under specific
  model assumptions; they should not be merged into a single public ranking without an explicit
  protocol decision.
- Scale-window, bandwidth, wavelet-band, and bootstrap settings can materially change results.
- Experimental wavelet estimators are included for comparison, but should not anchor public claims.

## Synthetic Data

- Generator checks cover ordering and sanity properties, not full distributional conformance.
- Finite-sample behaviour can differ substantially from asymptotic expectations.
- Contamination suites are controlled stress tests, not exhaustive models of real measurement
  artefacts.

## Observational Data

- Observational mode has no ground truth, so accuracy, coverage, and false-positive LRD claims are
  not available.
- Truth-free metrics describe estimator agreement, stability, runtime, and missingness. They do not
  prove long-range dependence in the source data.
- CSV and inline observational loaders currently support simple single-column series ingestion only.

## Reports

- Leaderboards are summaries of declared component metrics and weights. They are not universal
  estimator rankings.
- Failure maps and uncertainty summaries are diagnostic artefacts. They should be read alongside raw
  metric exports and manifest settings.
