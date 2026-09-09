# Reproducibility

`lrdbench` runs are intended to be reproducible from a manifest, package version, seed policy, and
input data.

For the completed manuscript experiment, use the [confirmation reproduction guide](confirmation_benchmark.md).
Its frozen producer/runtime and raw audit archive differ from the public CLI workflows below.
Rebuilding the manuscript from tracked summaries does not require rerunning that experiment.

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
uncertainty defaults. Synthetic records derive stable per-record seeds from the global seed and record identity.
The observational loader currently derives its record seeds from record identity without using
the supplied global seed; changing `global_seed` alone therefore does not change those record
seeds. Record this limitation when comparing resampling behavior on observational inputs.

When a manifest includes an `uncertainty.seed`, benchmark-level bootstrap intervals use that value.
Otherwise they default to `seeds.global_seed`.

## Caches

The optional `execution.estimate_cache_dir` stores pickled `EstimateResult` objects keyed by record,
estimator, parameters, signal hash, record seed and shared-fitting version. Use caches only
from trusted locations. The September repairs changed seed derivation and estimator behavior;
preserve old outputs and regenerate affected comparisons under an explicitly recorded revision.

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

The project has a stable public research release. Any change that affects public outputs must be
reflected in the changelog, migration notes, and output contract.

## Packaging Check

Before tagging a release candidate or stable public release, install the `build` and `twine`
tools and build into a fresh `dist` directory from the repository root:

```bash
python -m build
python -m twine check --strict dist/*
python scripts/check_dist.py dist
```

The default build produces a source distribution, then builds the wheel from that distribution.
The audit checks version consistency, metadata, the CLI entry point, licenses and configured
package assets. The source archive includes the documentation and both audit scripts.

Install the wheel in a clean virtual environment, then change to a temporary directory outside
the checkout before exercising the CLI. Use the absolute path to the built wheel:

```bash
python -m pip install /absolute/path/to/dist/lrdbench-VERSION-py3-none-any.whl
python -m pip check
lrdbench list-metrics
lrdbench validate public_small_canonical_ground_truth
lrdbench run smoke_ground_truth
lrdbench validate-output <result_store_printed_by_run>
```

Replace the wheel path and output path with actual values. This verifies that packaged assets
are available without help from the source checkout. Full research tests require the Git
checkout, including `benchmark_experiment`; that research archive is outside the package.

The GitHub `package` workflow runs distribution checks and installed-wheel smoke tests on
Python 3.11 and 3.12 for every push and pull request. See the
[release process](governance.md#release-process) for version tags and publishing behavior.
