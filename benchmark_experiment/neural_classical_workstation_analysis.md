# Neural Classical Workstation Benchmark Analysis

## Summary

This document records the first workstation-scale analysis of the neural classical estimator
benchmark campaign. The comparison is between a clean synthetic ground-truth calibration run and a
controlled stress-test run using the same classical estimator set and scale/window variants.

Ground-truth run:

- run ID: `2800af31-ae35-4d12-af1d-dd5f4ed17223`
- records: `160` clean fGn records
- report: `reports/neural_classical_workstation/2800af31-ae35-4d12-af1d-dd5f4ed17223/html/report.html`
- output contract: valid, version `1.0.0`

Stress-test run:

- run ID: `5357f529-6c14-40e8-b3ad-027cd06539a8`
- records: `3,200` total records (`160` clean + `3,040` contaminated)
- fit jobs: `48,000`
- report: `reports/neural_classical_workstation/5357f529-6c14-40e8-b3ad-027cd06539a8/html/report.html`
- output contract: valid, version `1.0.0`

The main result is that the classical estimators did not generally fail by crashing. Instead, they
failed in the way most relevant to neural-data interpretation: they continued to return valid
numeric estimates while becoming biased, contaminated, miscalibrated, saturated, or
tuning-sensitive.

## Main Findings

### Accuracy Degraded Under Stress

The best clean estimators remained comparatively strong under stress, but their errors increased.
DMA and aggregation-style estimators degraded more sharply.

| Estimator | Ground-truth MAE | Stress MAE | Change |
| --- | ---: | ---: | ---: |
| `DFA::short_scales` | 0.0295 | 0.0417 | +0.0122 |
| `DFA::balanced_scales` | 0.0364 | 0.0511 | +0.0147 |
| `VarianceResidual` | 0.0358 | 0.0561 | +0.0203 |
| `DFA::long_scales` | 0.0468 | 0.0605 | +0.0137 |
| `RS` | 0.0436 | 0.0617 | +0.0181 |
| `DMA::short_windows` | 0.0533 | 0.1119 | +0.0586 |
| `DMA::balanced_windows` | 0.0633 | 0.1205 | +0.0572 |
| `DMA::long_windows` | 0.0804 | 0.1314 | +0.0510 |
| `Variance` | 0.0966 | 0.1506 | +0.0540 |
| `AbsoluteMoment` | 0.1042 | 0.1546 | +0.0504 |

Committee interpretation:

- DFA variants were comparatively robust in this run.
- DMA and aggregation methods were much more sensitive to contamination.
- The stress result supports the claim that estimator performance under clean synthetic conditions
  does not transfer automatically to contaminated neural-like conditions.

### Polynomial Trend Was the Most Damaging Contamination for Drift

Mean estimate drift by contamination operator:

| Operator | Mean estimate drift |
| --- | ---: |
| `polynomial_trend` | 0.1122 |
| `outliers` | 0.0438 |
| `heavy_tail_noise` | 0.0426 |
| `level_shift` | 0.0000 |

Largest estimator/operator drift combinations:

| Operator | Estimator | Mean drift |
| --- | --- | ---: |
| `polynomial_trend` | `AbsoluteMoment` | 0.3151 |
| `polynomial_trend` | `Variance` | 0.3099 |
| `polynomial_trend` | `DMA::long_windows` | 0.2747 |
| `polynomial_trend` | `DMA::balanced_windows` | 0.2648 |
| `polynomial_trend` | `DMA::short_windows` | 0.2479 |

Committee interpretation:

- Smooth nonstationarity is a major threat to classical scaling estimates.
- This is directly relevant to neural time series, where slow drifts, state changes, impedance
  changes, and preprocessing residuals can mimic scale structure.
- Level shifts were not damaging in this specific design, which is useful: not all artefacts have
  the same effect on these estimators.

### Confidence-Interval Behavior Degraded

Stress reduced empirical coverage for several estimators that looked strong in the clean
calibration run.

| Estimator | Ground coverage | Stress coverage | Change |
| --- | ---: | ---: | ---: |
| `DFA::short_scales` | 0.9438 | 0.7063 | -0.2375 |
| `DFA::balanced_scales` | 0.9375 | 0.7159 | -0.2216 |
| `DFA::long_scales` | 0.9188 | 0.7116 | -0.2072 |
| `VarianceResidual` | 0.9063 | 0.6519 | -0.2544 |
| `RS` | 0.6188 | 0.4984 | -0.1203 |
| `DMA::short_windows` | 0.8250 | 0.6478 | -0.1772 |
| `DMA::balanced_windows` | 0.7688 | 0.6356 | -0.1331 |
| `DMA::long_windows` | 0.7062 | 0.6234 | -0.0828 |

Coverage collapse was strongest under polynomial trend:

| Operator | Mean coverage collapse |
| --- | ---: |
| `polynomial_trend` | 0.3308 |
| `heavy_tail_noise` | 0.1190 |
| `outliers` | 0.1180 |
| `level_shift` | 0.0217 |

Worst coverage-collapse combinations:

| Operator | Estimator | Mean coverage collapse |
| --- | --- | ---: |
| `polynomial_trend` | `DMA::short_windows` | 0.6448 |
| `polynomial_trend` | `DFA::long_scales` | 0.5479 |
| `polynomial_trend` | `RS` | 0.5250 |
| `polynomial_trend` | `DFA::balanced_scales` | 0.4948 |
| `polynomial_trend` | `DMA::balanced_windows` | 0.4865 |
| `polynomial_trend` | `DFA::short_scales` | 0.4781 |

Committee interpretation:

- The uncertainty story is central. The estimators often continued to return values, but interval
  behavior became much less trustworthy.
- Clean-regime coverage did not guarantee stress-regime coverage.
- The most damaging uncertainty failure was again tied to smooth nonstationarity.

### Validity Did Not Reveal the Main Problem

All enrolled estimator variants had validity rate `1.0` in both the ground-truth and stress runs.

This is important because it shows that failure-rate summaries alone would miss the main issue.
The estimators returned valid outputs, but those outputs were often degraded, miscalibrated, or
uninformative.

Committee interpretation:

- "Valid estimate" is not equivalent to "reliable estimate."
- Neural-data analyses should not stop at whether an estimator returned a number.
- Validity must be reported beside drift, coverage, false-positive behavior, disagreement, and
  tuning sensitivity.

### Saturation and Heuristic Behavior Are Not Robustness

Two estimators showed especially important interpretive patterns:

- `Higuchi` stayed near `1.0` almost everywhere.
- `GHE` stayed heavily around `0.5`.

Selected point-estimate ranges:

| Estimator | Ground min | Ground median | Ground max | Stress min | Stress median | Stress max |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `Higuchi` | 0.988 | 1.000 | 1.000 | 0.988 | 1.000 | 1.000 |
| `GHE` | 0.041 | 0.500 | 0.500 | 0.040 | 0.500 | 0.500 |

Committee interpretation:

- Apparent stability can be misleading.
- `Higuchi` had almost no drift because it was saturated near the upper bound, not because it was
  accurately robust.
- `GHE` can appear stable because of its flat-slope heuristic.
- These are failure modes of interpretation rather than runtime failures.

### False-Positive Behavior Appeared at the Short-Memory Boundary

For clean `H = 0.5` records, false-positive LRD rates were:

| Estimator family/variant | False-positive LRD rate |
| --- | ---: |
| `DFA` variants | 0.000 |
| `VarianceResidual` | 0.000 |
| `DMA::short_windows`, `DMA::balanced_windows` | 0.025 |
| `DMA::long_windows` | 0.050 |
| `AbsoluteMoment` | 0.050 |
| `Variance` | 0.050 |
| `RS` | 0.075 |
| `Higuchi` | 1.000 |
| `WaveletOLS` variants | 1.000 |

Committee interpretation:

- Some estimator configurations can report apparent persistence even at the short-memory boundary.
- This is directly relevant to neural-data claims, where elevated Hurst-style estimates are often
  interpreted as evidence of long memory.

### Scale and Window Sensitivity Was Present

Variant sensitivity was not the largest stress effect, but it remained visible and scientifically
important.

| Base estimator | Ground variant sensitivity | Stress variant sensitivity | Change |
| --- | ---: | ---: | ---: |
| `DFA` | 0.0192 | 0.0210 | +0.0018 |
| `DMA` | 0.0250 | 0.0219 | -0.0031 |
| `WaveletOLS` | 0.0331 | 0.0367 | +0.0036 |

| Base estimator | Ground max variant drift | Stress max variant drift | Change |
| --- | ---: | ---: | ---: |
| `DFA` | 0.0452 | 0.0496 | +0.0044 |
| `DMA` | 0.0604 | 0.0529 | -0.0075 |
| `WaveletOLS` | 0.0771 | 0.0853 | +0.0082 |

Committee interpretation:

- WaveletOLS was the most variant-sensitive family in this run.
- Scale/window selection remains a required diagnostic for neural analysis.
- A single estimator result without tuning sensitivity checks is not sufficient evidence.

## Leaderboard Context

The leaderboard is useful as a compact summary, but it must not be treated as a universal ranking.

Ground-truth top five:

1. `DFA::short_scales`
2. `DFA::balanced_scales`
3. `VarianceResidual`
4. `DFA::long_scales`
5. `RS`

Stress-test top five:

1. `DFA::short_scales`
2. `DFA::balanced_scales`
3. `DFA::long_scales`
4. `VarianceResidual`
5. `RS`

Interpretation:

- DFA variants performed best under this specific metric weighting.
- This should not be reported as "DFA is universally best."
- The stronger result is that rankings and estimator behavior depend on contamination, metric
  choice, uncertainty behavior, and scale/window settings.

## Committee-Facing Interpretation

The strongest conclusion from this workstation campaign is:

> Classical estimators can remain operational under contamination while their scientific
> interpretability degrades. The key risks are not only invalid fits, but biased point estimates,
> coverage collapse, false-positive persistence, saturated outputs, and sensitivity to scale/window
> choices.

For neural-data use, the implication is:

- do not rely on a single Hurst-style point estimate;
- always report estimator assumptions and target estimands;
- include contamination stress tests alongside observational neural results;
- report interval behavior and missing-uncertainty diagnostics;
- include estimator disagreement and scale/window sensitivity;
- treat smooth nonstationarity as a major confound for apparent LRD.

## Recommended Next Steps

1. Produce committee figures from the CSV outputs:
   - clean accuracy by estimator;
   - stress drift by contamination operator;
   - coverage and coverage-collapse panels;
   - false-positive LRD at `H = 0.5`;
   - estimator disagreement heatmap;
   - scale/window sensitivity heatmap.
2. Add the observational neural CSV manifest once neural segments are available.
3. Run the observational suite with the same classical estimator set and report only truth-free
   metrics: validity, runtime, CI width, instability, preprocessing sensitivity, estimator
   disagreement, and variant sensitivity.
4. Prepare a committee summary that explicitly separates:
   - synthetic truth-based claims;
   - stress-test degradation claims;
   - observational neural stability and failure-pattern claims.
