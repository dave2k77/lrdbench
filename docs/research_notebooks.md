# Research Notebooks

Workshop-oriented Jupyter notebooks live under the repository `notebooks/`
directory. They are designed for short research training sessions where users
need to see complete benchmark workflows rather than only API snippets.

## Available notebooks

- `01_ground_truth_benchmark_design.ipynb` - synthetic ground-truth benchmark
  design, execution, and metric inspection.
- `02_stress_testing_robustness.ipynb` - contamination-based robustness testing.
- `03_observational_csv_workflow.ipynb` - CSV-backed observational data workflow.
- `04_custom_estimator_comparison.ipynb` - custom estimator registration and
  comparison with a bundled estimator.

## Workshop setup

From a repository checkout:

```bash
pip install -e ".[reports,notebooks]"
jupyter lab
```

Run notebooks from the repository root. Generated reports are written under
`reports/notebooks/` and remain local-only.

The notebooks are tested in CI-style integration checks by executing their code
cells in a temporary workspace and validating that committed notebooks do not
include captured outputs.
