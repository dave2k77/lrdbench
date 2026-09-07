# Paired parent summaries for contamination comparisons

The sixth package adds a research summary helper for R06/R07/R12. It resamples
independent clean parents jointly across methods and contamination descendants,
and recomputes ratios of aggregate MAEs inside each draw. It is implemented in
[paired_summary.py](paired_summary.py), with 13 focused tests. The [seventh package](shared-stress.md) integrates it with verified stored
stress descendants across the complete classical point roster. The public evaluator
and output contract are unchanged.

## Statistical target and declared support

Input rows identify a stratum, clean parent, method and contamination condition,
and contain clean/stressed absolute errors against the **same latent clean H**.
The helper requires the complete parent index, method/condition roster and fixed
positive stratum weights summing to one. Parents with no output rows therefore
remain in the accounting. A parent cannot occur as an independent unit in two
strata, and a method's clean error must agree across that parent's descendants.

The current policy uses common complete parents across every declared
method-condition combination within each stratum. Reported error performance is
conditional on this support. Per-method available/missing pairs and common-parent
exclusions are exported separately; the policy does not make estimator failures
ignorable. Changing the roster can change common support and hence the conditional
target. Declare a small scientifically intended contrast before analysis rather
than silently conditioning on whichever methods happened to run.

For weights w_s, the clean and stressed errors are
A = sum_s w_s mean_i |H_clean,si - H_target,s| and
B = sum_s w_s mean_i |H_stress,si - H_target,s|, using the same retained parents.
The primary inflation is B - A; the supplementary ratio is B/A. This is neither
the mean of individual error ratios nor the weighted mean of stratum ratios.
Their identifiers reuse `absolute_error_inflation` and `paired_mae_ratio` from
the existing metric dictionary.
For example, clean/stressed MAEs (2, 2.5) and (4, 8), with stratum weights
(0.2, 0.8), give A = 3.6, B = 6.9, inflation = 3.3 and ratio = 6.9/3.6.
The weighted average of the two stratum ratios is a different quantity, 1.85.

Within each bootstrap draw, independently resample the retained clean parents
inside each fixed stratum. Carry each selected parent's entire vector of methods
and descendants together. Recompute A and B with the unchanged weights, then
compute B-A and B/A. Keyed random streams preserve results when display order
changes, and increasing the draw count preserves the earlier draw prefix. Small
draw batches bound intermediate memory use. The sample standard deviation of
finite summary draws is exported as `bootstrap_se`, an estimate of uncertainty
in the performance summary, not the numerical error of a bootstrap quantile.

The ratio is unavailable when A is at or below an explicitly declared denominator
floor (default 1e-12 in H-error units). Such draws are counted, and the exported
distribution retains their missing values. Percentile summary intervals require
at least five finite draws and at least two common parents in every positively
weighted stratum. Empty strata are not removed or reweighted. One-parent strata
can yield a point summary, but do not yield a bootstrap uncertainty interval.
These checks address accounting and resampling structure; they do not establish
coverage of the summary interval for every error distribution.

These are intervals for **benchmark performance summaries** across independent
records, distinct from a within-record interval for H. The design and Monte Carlo
reporting distinction follows the simulation-study framework in
[Morris, White and Crowther (2019)](https://discovery.ucl.ac.uk/10066118/1/2019%20-%20Morris%20-%20simulation%20studies%20tutorial%20-%20stat%20med.pdf).
The present helper assumes independently simulated clean parents. It does not
implement subject/channel/window hierarchy for observational EEG.

## Paired offset diagnostic

[summarize_offset_probe.py](summarize_offset_probe.py) applies the helper to the
mean-comparison screen's fixed +1 constant-offset descendants. This secondary
descriptive diagnostic was specified during execution, before inspecting the
coverage results. It does not choose a winning interval or introduce a significance
test. It keeps fGn, ARFIMA and AR(1) summaries separate, with equal fixed cell
weights **within** each model domain. It compares six declared point pipelines:
raw and sample-centered GPH, Higuchi and GHE. Each domain uses 999 joint parent
resamples, seed 20260912, and percentile 95% summary intervals.

```console
python benchmark_experiment/remediation/summarize_offset_probe.py --output reports/mean-comparison
```

The outputs retain the summary, per-cell parent accounting, all joint bootstrap
draws and the exact source/input hashes and design. A centered estimator's exact
offset invariance implies zero error inflation and a ratio of one whenever its
clean MAE is nonzero; narrow intervals here reflect that identity. This does not
establish robustness to steps, drift, trends or other nonstationarity.

The seventh package now materializes verified contamination descendants
from immutable clean inputs and feeds their canonical point results into this
helper. Coverage gains/losses and signed H drift need their own joint summaries;
they are not implemented by this absolute-error helper. The original historical
stress records must not be retroactively described as paired clean parents.

## Observed offset diagnostic

The completed diagnostic uses all 1,344 parents with complete common support.
All 36 summary rows retain 999 finite bootstrap draws. Under equal fixed weights
across the twelve fGn cells, the raw Higuchi and GHE pipelines' aggregate absolute
errors increase by 0.3363 and 0.3351 H units after the +1 offset. Their percentile
summary intervals are [0.3333, 0.3392] and [0.3323, 0.3377]. All centered pipelines
have zero inflation and ratio one to numerical precision. These aggregate values
are descriptive and depend on the explicitly declared equal-cell weighting.

The [summary table](mean-pilot/paired_offset_summary.csv),
[parent accounting](mean-pilot/paired_offset_parent_accounting.csv) and
[design/source record](mean-pilot/paired_offset_run.json) preserve the calculation.
The full joint draws are retained in the complete local verification bundle.
This is an end-to-end exercise of the summary helper using actual paired
simulation outputs, not only a hand-constructed test. No constant-offset result
is reinterpreted as robustness to a step change.


## Shared-parent stress integration

The [completed stress screen](shared-stress.md) uses 448 imported n=512 parents,
seven contamination conditions and 21 point pipelines. All 64 parents per cell
remain in common support. The 882 summary rows and all 881,118 draw rows are
independently recomputed; each condition retains its own error inflation and
ratio. Cell-level drift is descriptive only. Pooled drift uncertainty and
coverage gains/losses remain outside this helper's implemented scope.
