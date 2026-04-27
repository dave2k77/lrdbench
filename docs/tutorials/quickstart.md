# Quickstart

This tutorial runs the smallest packaged ground-truth benchmark and opens the path to the
generated report. It is intended as a first check that the library, CLI, estimators, result store,
and reporter all work together.

## Install

From a checkout of the repository:

```bash
pip install -e ".[reports]"
```

For a released package, use:

```bash
pip install "lrdbench[reports]"
```

## Run the first benchmark

From the repository root:

```bash
python examples/quickstart_pure.py
```

The script runs `configs/suites/smoke_ground_truth.yaml` and prints:

- the `run_id`;
- the result store directory;
- the HTML report path;
- a command for validating the public output contract.

The same run can be launched through the CLI:

```bash
lrdbench run configs/suites/smoke_ground_truth.yaml
```

Packaged suite names can also be inspected with:

```bash
lrdbench list-suites
```

## Validate the output

Use the `result_store` path printed by the command:

```bash
lrdbench validate-output reports/<run_id>
```

The command returns exit code `0` when the expected CSV, HTML, manifest, environment, and artefact
files are present with the required columns.

## What was benchmarked

The smoke suite generates one fractional Gaussian noise series with known target value and runs the
bundled `RS` estimator. Because this is ground-truth mode, truth-based metrics such as bias, MAE,
RMSE, empirical coverage, and interval width are meaningful.

For a fuller explanation of those metrics, continue with
[Ground-truth benchmark](ground_truth_benchmark.md).
