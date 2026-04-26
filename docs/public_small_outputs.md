# Public Small Outputs

This page records the expected output shape for the tracked `public_small_*` suites. Generated
reports are intentionally ignored by Git; these notes provide a clean-clone verification target.

## Expected Artefacts

Each suite should produce:

- `html/report.html`;
- `tables/run_summary.csv`;
- `tables/per_stratum_metrics.csv`;
- `tables/leaderboard.csv`;
- `tables/estimator_metadata.csv`;
- `tables/failures.csv`;
- `tables/failure_map.csv`;
- `tables/benchmark_uncertainty.csv` when the manifest enables benchmark uncertainty;
- `tables/estimator_disagreement.csv` when disagreement metrics are requested;
- `tables/scale_window_sensitivity.csv` when variant-sensitivity metrics are requested;
- `tables/stress_metrics.csv` for stress-test suites;
- `manifest/environment.json`;
- `artefacts/artefact_index.csv`;
- raw result-store tables under `raw/`.

Some optional CSVs may be present but empty when their metric family is not requested. For example,
canonical public-small runs create an empty `scale_window_sensitivity.csv`.

## Local Reference Runs

The following runs were produced locally on 2026-04-26 with `PYTHONPATH=src python -m
lrdbench.cli.main run <manifest>`.

| Suite | Run ID | Per-stratum rows | Benchmark uncertainty rows | Disagreement rows | Failure rows | Leaderboard rows | Suite-specific rows |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `public_small_canonical_ground_truth` | `2fa8e0ca-6153-48e1-af31-418fcc8fdd80` | 112 | 24 | 40 | 21 | 3 | 0 sensitivity |
| `public_small_stress_contamination` | `460126b8-a619-4e76-ad78-c7b24c4bd195` | 424 | 144 | 148 | 84 | 3 | 180 stress |
| `public_small_null_false_positive` | `e6b97def-bfdb-4496-8d11-fc4bf9e2aac8` | 75 | 15 | 52 | 14 | 3 | 0 sensitivity |
| `public_small_sensitivity_disagreement` | `ac062328-1caf-4075-919e-144342ea89c8` | 156 | 36 | 112 | 50 | 6 | 42 sensitivity |

The row counts above exclude CSV headers. Different package versions may change numeric values or
row counts; such changes should be intentional and reflected in the changelog.

## Verification Commands

```bash
lrdbench validate configs/suites/public_small_canonical_ground_truth.yaml
lrdbench validate configs/suites/public_small_stress_contamination.yaml
lrdbench validate configs/suites/public_small_null_false_positive.yaml
lrdbench validate configs/suites/public_small_sensitivity_disagreement.yaml
```

Run suites one at a time when checking generated reports:

```bash
lrdbench run configs/suites/public_small_canonical_ground_truth.yaml
```
