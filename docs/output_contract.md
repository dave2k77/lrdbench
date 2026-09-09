# Output Contract

This specification describes public `BenchmarkRunner` exports. It is distinct from the
Python dataclass schema and the paper's frozen research archive. The current contract below
is included directly from `configs/contracts/public_output_contract.json` during the docs build;
`tests/unit/test_output_contract.py` checks that it equals
`lrdbench.output_contract.PUBLIC_OUTPUT_CONTRACT`.

## Run root and file requirements

Runs write under `<report.export_root>/<run_id>/`. Required files and minimum CSV headers,
conditional files, dynamic columns and the contract version are defined in the embedded source.
Extra columns are allowed; readers must not assume an exact column count or a fixed set of
manifest-dependent metric/stratum columns.

```json
--8<-- "configs/contracts/public_output_contract.json"
```

Contract 1.1.0 added the conditional `raw/truths.csv` companion-truth ledger while retaining the
1.0.0 columns in existing files. It stores primary and companion estimands on the same
realisation, with `is_primary` identifying the primary truth. `raw/records.csv` retains only
that primary truth. Conditional correction and stress tables carry paired-record identifiers.

The manifest snapshot is written whenever `BenchmarkManifest.raw_yaml` is available. This
includes both YAML loading and `manifest_from_mapping()`; a directly constructed dataclass
with `raw_yaml=None` does not produce that snapshot.

## Persistence boundaries

The public store also writes `run_summary.json`, signal arrays under
`raw/values/<record_id>.npy`, and `raw/plugin_provenance.csv` when plugin provenance rows exist.
`raw/records.csv` points to each array through `values_path`. Preserve or relocate referenced
files when moving a report; the CSVs alone are not a self-contained signal archive.

`raw/estimates.csv` retains points, endpoint fields, standard errors, validity, runtime,
failure reasons, warnings and labelled bootstrap intervals. It does not persist the full
`EstimateResult.diagnostics` mapping or bootstrap draw arrays. Use the returned Python objects
when those fields are needed; a public CSV export cannot reconstruct the entire in-memory run.

The [confirmation archive](confirmation_benchmark.md) has separate point/draw storage,
completion evidence, paired resampling and hash checks. Its files are not interchangeable
with these public exports. Follow its protocol and audit instructions for paper reproduction.

## Validation command and limits

```bash
lrdbench validate-output reports/public_small/<run_id>
```

The command checks required-file presence and minimum CSV headers, including headers of
conditional CSVs that exist. It returns `0` when those checks pass, or `2` with an `error=...`
line per violation. It does not determine whether a conditional file should exist, verify a
stored contract version, inspect row values/counts, follow array paths, verify hashes, or
establish scientific validity. A passing check is structural validation, not a completeness audit.

## Artefact inventories

`artefacts/artefact_index.csv` inventories report artefacts known to the reporter, including
metric tables, figures, environment metadata, HTML and the index itself. Its hash and dependency
metadata are optional; their presence as columns does not mean all files have been hashed.

`raw/artefacts.csv` records the returned report bundle and any model artefacts appended by the
runner after report generation. Consequently it can contain model files absent from the reporter
index. Neither inventory enumerates every signal array or every raw CSV in the directory.

## Maintaining the specification

Change the Python contract and tracked JSON together when changing a stable requirement; the
existing equality test guards against divergence. Review the contract version and migration
notes for compatibility changes. The docs include the JSON directly, so required paths and
headers should not be copied into a second manually maintained schema table.

For workflow or serialization changes, run relevant runner/reporter tests, generate a smoke
report and validate it, then build the documentation with `python -m mkdocs build --strict`.
Check conditional outputs and persistence semantics separately from the minimum-header check.
