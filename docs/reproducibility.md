# Reproducibility

`lrdbench` runs are intended to be reproducible from a manifest, package version, seed policy, and
input data.

## Minimal Reproduction Steps

From a clean clone or installed package:

```bash
lrdbench validate public_small_canonical_ground_truth
lrdbench run public_small_canonical_ground_truth
lrdbench validate-output reports/public_small/<run_id>
```

The run writes outputs under the manifest `report.export_root` and prints the generated `run_id`.
Use `lrdbench list-suites` to list packaged public suite names. In a source checkout, manifest file
paths under `configs/suites/` work as well.

## Seeds

The manifest `seeds.global_seed` controls synthetic record generation and benchmark-level
uncertainty defaults. Individual records derive stable per-record seeds from the global seed and
record identity.

When a manifest includes an `uncertainty.seed`, benchmark-level bootstrap intervals use that value.
Otherwise they default to `seeds.global_seed`.

## Caches

The optional `execution.estimate_cache_dir` stores pickled `EstimateResult` objects keyed by record,
estimator, parameters, and signal hash. Use caches only from trusted locations.

For strict reproduction checks, either disable cache reads or use an empty cache directory:

```yaml
execution:
  cache_read: false
  cache_write: false
```

## Environment Capture

Each report writes `manifest/environment.json` with:

- run and manifest identifiers;
- Python executable and version;
- platform metadata;
- selected package versions;
- seed, execution, and uncertainty settings.

Keep this file with generated reports when comparing runs.

## Version Pinning

For public comparisons, report at least:

- `lrdbench` version or Git commit;
- manifest file and `manifest_id`;
- Python version;
- dependency lockfile or environment export when available;
- generated `manifest/environment.json`;
- generated `artefacts/artefact_index.csv`.

The project is in release-candidate review. No known output-column or schema churn is planned
before `v1.0.0`; any change that affects public outputs must be reflected in the changelog,
migration notes, and output contract.

## Packaging Check

Before tagging a release candidate or stable public release, build and install the package from
local artefacts:

```bash
python -m build
python -m pip install dist/*.whl
lrdbench list-metrics
lrdbench validate public_small_canonical_ground_truth
```

The GitHub `package` workflow runs the build, wheel install, and basic CLI discovery checks.
