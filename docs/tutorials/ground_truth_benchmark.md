# Ground-truth Benchmark

Ground-truth mode evaluates estimators on synthetic series with declared target values. Use it when
you need accuracy, calibration, and validity metrics against known benchmark truth.

## Run the tutorial suite

```bash
lrdbench validate configs/suites/smoke_ground_truth.yaml
lrdbench run configs/suites/smoke_ground_truth.yaml
```

The manifest uses:

- `mode: ground_truth`;
- `source.type: generator_grid`;
- the `fGn` generator with `H: 0.5`;
- the bundled `RS` estimator;
- truth-aware metrics including `bias`, `mae`, `rmse`, `coverage`, `ci_width`, and
  `coverage_error`.

The Python equivalent is:

```python
from pathlib import Path

from lrdbench.runner import run_manifest_path

out = run_manifest_path(Path("configs/suites/smoke_ground_truth.yaml"))
print(out.run_id)
print(out.result_store_path)
```

## Read the manifest

The key parts of a ground-truth manifest are:

```yaml
mode: ground_truth
source:
  type: generator_grid
  generators:
    - family: fGn
      params:
        H: [0.5]
        n: [128]
      replicates: 1
estimators:
  - name: RS
    target_estimand: hurst_scaling_proxy
metrics:
  - bias
  - mae
  - rmse
  - validity_rate
```

The generator declares the target truth. The estimator declares the estimand it attempts to recover.
Those two declarations must be interpreted together; a low error is meaningful only for the stated
estimand and validity domain.

## Interpret the output

Start with `tables/run_summary.csv` to confirm the manifest, mode, and run identifier. Then inspect:

- `tables/per_stratum_metrics.csv` for metric values by estimator and benchmark stratum;
- `tables/leaderboard.csv` for the configured weighted ranking;
- `tables/uncertainty_calibration.csv` for interval coverage and width when confidence intervals
  are available;
- `tables/failures.csv` and `tables/failure_map.csv` for invalid estimates or estimator failures.

Ground-truth metrics should be reported together with the manifest and software version. Do not
compare scores across runs unless the manifests, estimands, metrics, and leaderboard rules are
compatible.
