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

## Read the manifest

The central stress-test block is:

```yaml
mode: stress_test
contamination:
  operators:
    - name: level_shift
      params:
        shift: [0.25]
metrics:
  - estimate_drift
  - relative_degradation_ratio
  - validity_rate
```

`estimate_drift` describes how much the estimate moves under contamination. Degradation metrics
compare contaminated behaviour with the clean synthetic baseline. Validity-rate metrics expose
cases where an estimator returns invalid results or cannot complete.

## Interpret the output

Use the HTML report for a first pass, then inspect:

- `tables/stress_metrics.csv` for stress-specific summaries;
- `tables/per_stratum_metrics.csv` for estimator metrics by contamination stratum;
- `tables/failure_map.csv` for failure concentration by source or transformation;
- `raw/records.csv` and `raw/estimates.csv` for row-level audit trails.

Stress-test results should be described as robustness evidence for the declared contamination
design. They are not proof that an estimator will be robust to every empirical artefact.
