# Remediation metric contract, version 1

This contract records the interpretation of the existing outputs and the explicit
metrics proposed for the repairs. Historical result files are kept
unchanged. Existing ambiguous names remain legacy aliases with their historical
meaning; new names do not silently change old calculations.

First-package implementation status: `ci_availability`, ranking rules, bootstrap
failure accounting, and the new contamination names are implemented. All other
new metric identifiers below remain planned and are not yet available in manifests.
Existing legacy metrics keep their original calculations. The paired-ratio bootstrap
rule below is a requirement for that metric's future implementation.

| Metric | Meaning and denominator |
| --- | --- |
| `estimate_drift` / `absolute_estimate_drift` | Mean absolute difference on valid clean/contaminated pairs. |
| `signed_estimate_drift` | Mean stressed-minus-clean estimate on valid pairs. Diagnostic, not a directional robustness score. |
| `absolute_error_inflation` | Mean paired stressed absolute error minus clean absolute error against the declared latent clean target. |
| `relative_degradation_ratio` | Legacy mean of per-record error ratios, omitting near-zero clean errors; not a ratio of aggregate MAEs. |
| `paired_mae_ratio` | Ratio of mean stressed to mean clean absolute error on the same valid pairs, separately per stratum. Balanced global ratio uses equal stratum weights on numerator and denominator before division. Zero/near-zero denominator is explicitly missing. |
| `coverage_collapse` / `coverage_loss_rate` | Fraction of pairs with clean coverage and lost stressed coverage; recovered coverage does not offset losses. |
| `net_coverage_loss` | Mean clean coverage indicator minus stressed indicator on pairs with both intervals available. Can be negative. |
| `coverage_error` | Absolute stratum coverage-minus-nominal deviation, averaged across strata; not signed undercoverage or the absolute error of pooled coverage. |
| `false_positive_lrd_rate` / `persistence_exceedance_rate` | Fraction of valid null-record point estimates at or above a specified cutoff; defaults H >= 0.6 with null H <= 0.5, or d >= 0.1 with null d <= 0. This is not a calibrated CI-based significance test. |
| `instability` | Within-record bootstrap standard deviation, then aggregation; not variation between subjects. |
| `ci_availability` | Fraction of attempted fits with a valid finite point and an available finite interval at the requested nominal level. |

Pairwise target-based metrics require the target for that estimator, even if the
record carries other companion truths. Missing pairs and intervals are counted in
metadata rather than treated as zero errors. Coverage is conditional on interval
availability and must be read alongside `ci_availability` and validity.

The new paired MAE ratio is an aggregate statistic; its per-series rows carry
numerator and denominator components, not individual ratios. Bootstrap intervals
for this new ratio are not provided by the existing scalar bootstrap engine.
Requesting them must fail explicitly until paired ratio resampling is implemented.

Ranking uses equal average component ranks for exactly equal finite values.
Missing/nonfinite values have worst rank N+1 in either optimisation direction.
Composite ties use the declared primary/named component; unresolved scientific
ties share competition ranks. Names affect display order only. Signed drift and
bias are descriptive rather than suitable raw minimisation objectives.

There are three distinct counts: independent generated records, within-record
bootstrap attempts, and resamples of benchmark summaries. Bootstrap failures,
retained draws and interval availability are recorded separately from point-fit
validity. A valid point does not certify a calibrated or available interval.

Constant offsets remain `level_shift` for historical compatibility, with an
explicit `constant_offset` name available. The new `step_change` modifies samples
from `floor(position*n)` onward, default position 0.5. Both use clean-record
population standard deviation as the amplitude unit. Their registry names and
provenance distinguish the two transformations.

The confirmatory protocol and method-specific uncertainty validation remain
pending. This contract does not certify any bootstrap procedure under LRD.
