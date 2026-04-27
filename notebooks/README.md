# Research Workshop Notebooks

These notebooks are lightweight research-usecase walkthroughs for workshops and
hands-on teaching sessions. They are intentionally small enough to run on a
laptop while still exercising the same manifest, execution, reporting, and
validation paths used by larger studies.

## Notebook sequence

1. `01_ground_truth_benchmark_design.ipynb` - design and run a small synthetic
   ground-truth benchmark.
2. `02_stress_testing_robustness.ipynb` - compare clean and contaminated
   synthetic records to assess robustness.
3. `03_observational_csv_workflow.ipynb` - create a CSV-backed observational
   benchmark and interpret stability-oriented outputs.
4. `04_custom_estimator_comparison.ipynb` - register a custom estimator and
   compare it with a bundled estimator.

## Running from a checkout

Install the package with reporting support, then start Jupyter from the
repository root:

```bash
pip install -e ".[reports,notebooks]"
jupyter lab
```

Generated reports are written under `reports/notebooks/`, which is ignored by
Git.

## Maintenance

Notebook outputs should not be committed. The integration test
`tests/integration/test_research_notebooks.py` validates notebook JSON, checks
that outputs are empty, and executes code cells in a temporary workspace.
