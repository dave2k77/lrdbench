# Neural Classical Estimator Benchmark

This directory documents the neural-data-oriented benchmark of classical
long-range dependence estimators in `lrdbench`.

The purpose of the experiment is to test how classical Hurst/LRD estimators
behave on data that are deliberately close to neural time-series analysis
conditions: finite sample lengths, weak-to-strong long memory, trends, level
shifts, outliers, and heavy-tailed noise. The benchmark is designed to make the
failure modes visible against known synthetic ground truth.

## Contents

- `neural_classical_estimator_benchmark_spec.md`: full benchmark design and
  supervisory-committee-facing specification.
- `neural_classical_workstation_analysis.md`: interpretation of the completed
  workstation ground-truth and stress runs.
- `results/neural_classical_workstation/`: compact public result tables derived
  from the completed runs.
- `../configs/suites/neural_classical_workstation_ground_truth.yaml`: exact
  ground-truth manifest.
- `../configs/suites/neural_classical_workstation_stress.yaml`: exact stress
  manifest.

Full row-level outputs are intentionally not tracked in git because several
report tables are hundreds of MB. Publish those as release/archive artifacts and
link them from the result page.

## Completed Runs

| Run | Mode | Run ID | Manifest |
| --- | --- | --- | --- |
| Ground truth | `ground_truth` | `2800af31-ae35-4d12-af1d-dd5f4ed17223` | `neural_classical_workstation_ground_truth_v1` |
| Stress | `stress_test` | `5357f529-6c14-40e8-b3ad-027cd06539a8` | `neural_classical_workstation_stress_v1` |

The stress run evaluates 3,200 records and 48,000 estimator fits. The
ground-truth run evaluates 160 clean fGn records and 2,400 estimator fits.

## Headline Findings

- The classical estimators usually return finite estimates; the main failure is
  interpretive rather than a hard runtime failure.
- DFA variants are the strongest performers in this run, but their uncertainty
  intervals still degrade under contamination.
- Polynomial trend is the most damaging stressor, producing the largest mean
  estimate drift and coverage collapse.
- Moment and variance estimators are especially sensitive to trend and
  heavy-tailed/outlier contamination.
- Higuchi and GHE show apparent numerical stability in some settings, but that
  stability reflects saturation or flat-slope behavior rather than reliable
  recovery of the ground truth.
- Nominal confidence intervals can become badly miscalibrated under neural-like
  contamination even when the point estimate looks plausible.

## Reproducing The Public Tables

From the repository root, after generating the two report directories:

```powershell
.\.venv\Scripts\python.exe scripts\export_public_benchmark_results.py `
  --ground-truth reports\neural_classical_workstation\2800af31-ae35-4d12-af1d-dd5f4ed17223 `
  --stress reports\neural_classical_workstation\5357f529-6c14-40e8-b3ad-027cd06539a8 `
  --output benchmark_experiment\results\neural_classical_workstation
```

## Publication Recommendation

Track the documentation, manifests, and compact tables in git. Publish full raw
reports as GitHub Release assets or an archival record such as Zenodo. If the
release is archived with Zenodo, cite the DOI in this directory and in the main
project README.
