# Paper workflow

The publication workflow is intentionally split between tracked library support and local-only
benchmark assets.

Tracked in the repository:

- core metrics, reporting, LaTeX table export, and figure generation;
- smoke and shared suite manifests under `configs/suites/`;
- documentation and handoff notes.

Local-only by design:

- `paper_support/`;
- `configs/suites/paper/`;
- `tests/integration/test_paper_workflow.py`;
- generated `reports/`;
- `.lrdbench_cache/`.

These paths are ignored by Git so draft paper runs, generated artefacts, and machine-specific cache
state do not enter the remote repository.

## Expected local layout

When the paper kit is available on a workstation, a typical setup is:

```text
paper_support/
configs/suites/paper/
  canonical_ground_truth.yaml
  stress_contamination.yaml
  null_false_positive.yaml
  sensitivity_disagreement.yaml
```

Run paper suites from the repository root:

```bash
python -m paper_support.run_paper_suites configs/suites/paper/canonical_ground_truth.yaml
```

The local runner should write normal reports under `reports/paper/<run_id>/`, stage selected
LaTeX tables and figures under `paper_support/artefacts/`, and append a run index when configured.

For clean clones without the paper kit, use the tracked manifests under `configs/suites/` and the
standard CLI:

```bash
lrdbench run configs/suites/smoke_ground_truth.yaml
```

See the development handoff for current execution notes and phase planning.
