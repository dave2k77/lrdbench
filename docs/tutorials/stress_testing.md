# Stress Testing

Stress-test mode measures how estimators behave when a clean synthetic series is transformed by a
controlled contamination. Use it to study robustness rather than raw accuracy alone.

## Run the tutorial suite

```bash
lrdbench validate configs/suites/smoke_stress_test.yaml
lrdbench run configs/suites/smoke_stress_test.yaml
```

Or use the example script:

```bash
python examples/quickstart_contaminated.py
```

The smoke stress suite generates a clean `fGn` series, applies a `level_shift` contamination, and
runs the `RS` estimator on the resulting records.

## Compare with data-driven baselines

The packaged data-driven smoke suite trains feature-based ML baselines on a separate synthetic
training grid, then evaluates them under the same clean/contaminated stress-test loop:

```bash
pip install -e ".[ml,reports]"
lrdbench validate configs/suites/smoke_data_driven.yaml
lrdbench run configs/suites/smoke_data_driven.yaml
```

This suite includes:

- `RS`, a classical temporal estimator;
- `MLRandomForest`, a scikit-learn random forest regressor;
- `MLSVR`, a scikit-learn support vector regressor.

The RF/SVR models are trained once per run from the manifest `ml_training` block. Their model files
and `training_summary.json` are written under `reports/<run_id>/ml_models/`.

## Read the manifest

This fragment shows the central stress-test fields; retain IDs, source and estimators from
the full smoke manifest. `relative_degradation_ratio` also requires `mae`:

```yaml
mode: stress_test
contamination:
  operators:
    - name: level_shift
      params:
        shift: [0.25]
metrics:
  - mae
  - estimate_drift
  - relative_degradation_ratio
  - validity_rate
  - runtime
```

`estimate_drift` describes how much the estimate moves under contamination. Degradation metrics
compare contaminated behaviour with the clean synthetic baseline. Validity-rate metrics expose
cases where an estimator returns invalid results or cannot complete.

For new experiments use explicit metric names:

| Metric | Calculation on available clean/stressed pairs |
| --- | --- |
| `absolute_estimate_drift` | Mean absolute stressed-minus-clean estimate; equivalent to legacy `estimate_drift`. |
| `signed_estimate_drift` | Mean stressed-minus-clean estimate; diagnostic only, disallowed in rankings. |
| `absolute_error_inflation` | Mean stressed absolute error minus clean absolute error against the retained clean-process target; negative means reduced error. |
| `paired_mae_ratio` | Mean stressed absolute error divided by mean clean absolute error on the same pairs. |
| `coverage_loss_rate` | Fraction with clean coverage and lost stressed coverage, among pairs with both intervals; equivalent to legacy `coverage_collapse`. |
| `net_coverage_loss` | Mean clean coverage indicator minus stressed indicator; recoveries offset losses. |

`relative_degradation_ratio` retains its legacy mean of individual error ratios,
excluding near-zero clean errors. It differs from `paired_mae_ratio`. The latter
first computes paired MAEs within each stratum; its balanced global value averages
the numerator and denominator equally across available strata before dividing.
Zero/near-zero denominators yield an explicitly missing ratio (default threshold
`denominator_epsilon: 1e-12`). Zero-error strata still contribute to the global
numerator and denominator. Missing pairs and intervals are excluded and counted
in metric metadata; all-missing strata remain visible. Other balanced summaries
average the available stratum values, with their counts recorded.

The ratio's per-record rows have no scalar value: their components are in
`raw/metrics.csv` metadata. Read ratio values from aggregate exports. The existing
benchmark bootstrap cannot resample these components jointly; manifests must
disable summary uncertainty or explicitly exclude `paired_mae_ratio` from its
`metrics` and `paired_metrics` filters. Unsupported requests raise an error.

Use `ci_availability` and `validity_rate` alongside conditional coverage. The
`persistence_exceedance_rate` name clarifies legacy `false_positive_lrd_rate`:
it counts valid null estimates crossing a point cutoff (default H >= 0.6),
not rejection by a calibrated confidence-interval test.

The historical `level_shift` operator adds a constant offset to the full record.
Use `step_change` for an internal jump and `constant_offset` for an explicit offset
control. Neither implies that the contaminated process retains the clean process's
H; accuracy metrics measure recovery of the declared latent clean target.

## Interpret the output

Use the HTML report for a first pass, then inspect:

- `tables/stress_metrics.csv` for stress-specific summaries;
- `tables/per_stratum_metrics.csv` for estimator metrics by contamination stratum;
- `tables/failure_map.csv` for failure concentration by source or transformation;
- `raw/records.csv` and `raw/estimates.csv` for row-level audit trails.

Stress-test results should be described as robustness evidence for the declared contamination
design. They are not proof that an estimator will be robust to every empirical artefact.

For data-driven baselines, also report the training distribution. A robust-looking result may reflect
that the contamination was represented in `ml_training`, and may not transfer to other artefacts or
sample-size regimes.
