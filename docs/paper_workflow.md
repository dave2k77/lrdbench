# Paper Workflow

The paper-support workflow provides curated benchmark manifests and a small runner that copies
publication tables and figures into a stable drafting directory.

## Suites

Paper-oriented manifests live under `configs/suites/paper/`:

- `canonical_ground_truth.yaml`: truth-backed Hurst-scaling benchmarks over canonical and
  structured synthetic generators.
- `stress_contamination.yaml`: paired clean/contaminated stress tests for nonstationarity,
  impulsive contamination, and heavy-tailed noise.
- `null_false_positive.yaml`: null boundary cases for false-positive LRD analysis.
- `sensitivity_disagreement.yaml`: estimator disagreement and scale/window sensitivity under
  plausible tuning variants.

These manifests are intentionally versioned as benchmark protocol artefacts. Edit them deliberately
and record changes in the changelog when they affect reported results.

## Running

Run all paper suites from the repository root:

```bash
python -m paper_support.run_paper_suites
```

Run a subset:

```bash
python -m paper_support.run_paper_suites configs/suites/paper/null_false_positive.yaml
```

The runner injects `reports/paper` as the export root by default and writes:

- normal raw result stores and HTML/CSV/LaTeX reports under `reports/paper/<run_id>/`;
- copied publication figures and LaTeX tables under `paper_support/artefacts/`;
- `paper_support/artefacts/run_index.csv` with manifest IDs, run IDs, report paths, and copied
  artefact paths.

Estimate caches are enabled in the manifests under `.lrdbench_cache/` so repeated paper runs can
reuse trusted local `EstimateResult` pickles.
