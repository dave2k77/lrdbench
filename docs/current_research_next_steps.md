# Current Research Next Steps

Last updated: 2026-05-29

This page is the short, current-facing handoff for work after the stable public `lrdbench` release. It intentionally separates public-library maintenance from the neural-classical benchmark and future observational neural-data work.

## Current project state

- Public package status: stable `1.0.2` release, with unchanged public output contract `1.0.0`.
- Public library focus: maintain schema/API/output-contract stability, keep docs coherent, and avoid changing public CSV columns without a contract-version bump.
- Current research focus: use the completed `neural_classical_workstation` benchmark campaign to prepare committee/manuscript figures and define the next observational neural-data benchmark.
- Completed synthetic campaign: `benchmark_experiment/neural_classical_workstation_analysis.md` summarises the ground-truth and stress-test runs.
- Compact tracked results: `benchmark_experiment/results/neural_classical_workstation/` contains the public summary CSVs and checksums; large row-level report directories should be published separately as release or archive assets when cited.

## Dedicated local environment

On this Windows workstation, use the repository-local virtual environment and source tree explicitly:

```bash
PYTHONPATH=src .venv/Scripts/python.exe -m pytest -q -o addopts=
PYTHONPATH=src .venv/Scripts/python.exe -m lrdbench.cli.main validate configs/suites/smoke_ground_truth.yaml
PYTHONPATH=src .venv/Scripts/python.exe -m mkdocs build --strict
```

Do not rely on bare `python` for repository verification on this machine; it may resolve to a Python without project dependencies. Keep `PYTHONPATH=src` on source-tree CLI/test/doc commands unless the editable install has been refreshed and verified.

## Immediate next actions

1. Build committee/manuscript figures from the tracked compact summary CSVs:
   - clean accuracy by estimator;
   - stress drift by contamination operator;
   - coverage and coverage-collapse panels;
   - false-positive LRD at `H = 0.5`;
   - estimator disagreement heatmap;
   - scale/window sensitivity heatmap.
2. Keep the scientific claims separated in all writeups:
   - synthetic truth-based claims;
   - stress-test degradation claims;
   - observational neural stability and failure-pattern claims.
3. Decide publication packaging for large outputs:
   - keep compact summaries and checksums in git;
   - publish full report directories as GitHub Release or Zenodo assets if externally cited;
   - update citation/DOI guidance only after an archive exists.
4. Before adding new metrics or report columns, add or update output-contract tests first.
5. When touching evaluator or reporter logic, keep changes narrow and regression-test the exact metric/report behavior.

## Observational neural-data entry criteria

For a concrete implementation backlog, see [Observational mode readiness plan](observational_readiness_plan.md).

Start the observational neural-data suite only after the input segments have:

- stable segment identifiers;
- documented sampling rate and preprocessing history;
- a CSV series index or inline manifest representation compatible with the observational loader;
- a clear separation between raw signal metadata and benchmark annotations;
- an interpretation plan that avoids truth-based metrics and reports only truth-free diagnostics.

The observational run should initially report:

- validity rate;
- runtime;
- confidence-interval width and missing uncertainty;
- window/preprocessing instability;
- estimator disagreement;
- scale/window variant sensitivity;
- failure-map summaries.

## Verification commands

Use this quick gate before committing documentation or benchmark-planning changes:

```bash
PYTHONPATH=src .venv/Scripts/python.exe -m ruff check src tests
PYTHONPATH=src .venv/Scripts/python.exe -m pytest -q -o addopts=
PYTHONPATH=src .venv/Scripts/python.exe -m mkdocs build --strict --quiet
```

Use smoke-suite validation before benchmark-run changes:

```bash
PYTHONPATH=src .venv/Scripts/python.exe -m lrdbench.cli.main validate configs/suites/smoke_ground_truth.yaml
PYTHONPATH=src .venv/Scripts/python.exe -m lrdbench.cli.main validate configs/suites/smoke_stress_test.yaml
PYTHONPATH=src .venv/Scripts/python.exe -m lrdbench.cli.main validate configs/suites/smoke_observational.yaml
PYTHONPATH=src .venv/Scripts/python.exe -m lrdbench.cli.main validate configs/suites/smoke_data_driven.yaml
```
