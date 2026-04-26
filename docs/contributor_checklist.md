# Contributor Checklist

Use this checklist before opening a contribution that adds or changes benchmark behaviour.

## Estimators

- The estimator implements `BaseEstimator`.
- The estimator has a stable name and version.
- The target estimand is explicit.
- Assumptions and expected operating regimes are documented.
- Parameters are read from `EstimatorSpec.parameter_schema`.
- Short or degenerate signals return `valid=False` with `failure_reason`.
- Unexpected exceptions are captured as `exception:<type>:<message>`.
- Diagnostics are structured and JSON-serialisable.
- Estimator-level uncertainty support is documented.
- Tests cover at least one valid fit and one invalid fit.

## Benchmark Outputs

- Any new report table has documented columns.
- Any public output surface change updates `configs/contracts/public_output_contract.json`.
- `lrdbench validate-output <run_root>` still passes for smoke reports.
- Changelog entries describe public-surface changes.

## Validation

Run:

```bash
python -m ruff check .
python -m pytest
python -m mkdocs build --strict
python -m build
```

For packaging or CLI changes, also install the built wheel in a temporary environment and run:

```bash
lrdbench list-suites
lrdbench run smoke_ground_truth
lrdbench validate-output reports/<run_id>
```
