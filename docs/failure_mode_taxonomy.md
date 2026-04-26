# Failure Mode Taxonomy

Failure exports use a small taxonomy so invalid estimates can be compared across estimators and
suites without over-interpreting estimator-specific error strings.

| Code | Meaning | Typical source | Public interpretation |
| --- | --- | --- | --- |
| `insufficient_signal` | The estimator did not have enough usable data or scale support. | `insufficient_signal_for_*` failure reasons. | Treat as a validity failure, not as evidence against LRD in the record. |
| `estimator_exception` | The estimator raised an exception that was captured as an invalid estimate. | `exception:<type>:<message>` failure reasons. | Treat as implementation or numerical fragility that needs inspection. |
| `missing_uncertainty` | A point estimate exists, but requested intervals were unavailable. | Failure-summary exports when coverage or CI metrics are requested. | Accuracy metrics may still be usable; coverage and CI-width metrics are incomplete. |
| `invalid_fit` | The estimator returned no admissible point estimate for another reason. | Unknown or uncategorised failure reason. | Treat as an invalid estimate and inspect raw diagnostics before drawing conclusions. |

The taxonomy is intentionally coarse. Estimator-specific `failure_reason` values remain available in
raw estimate exports for debugging, while summary tables should use these categories when grouping
failure rates.

## Reporting Rules

- Do not convert an invalid estimate into a numeric score by imputation.
- Report validity or invalid-rate metrics beside accuracy and robustness metrics.
- Separate missing uncertainty from invalid point estimates whenever coverage metrics are included.
- For observational suites, failure rates describe estimator behaviour only; they do not validate or
  falsify the underlying data source.
