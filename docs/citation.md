# Citation Guidance

If you use `lrdbench` in research, cite the software release and report enough benchmark metadata
for another researcher to reproduce the comparison.

## Software Citation

Use the repository `CITATION.cff` as the citation authority for the current release candidate. For
manual reference lists, include:

- software name: `lrdbench`;
- author: Davian Chin;
- version: `0.9.0rc1`;
- repository: `https://github.com/dave2k77/lrdbench`;
- license: MIT.

If a DOI or archived release bundle is added for `v1.0.0`, cite that archived artefact instead of a
moving repository URL.

## Benchmark Metadata to Report

For published comparisons, report:

- `lrdbench` package version or Git commit;
- public output contract version;
- benchmark suite name or manifest path;
- `manifest_id`;
- estimator names and versions;
- Python version and dependency environment;
- generated `manifest/environment.json`;
- generated `artefacts/artefact_index.csv`.

## Method Citations

Also cite the original methodological references for estimators, generators, datasets, or
observational sources used in a benchmark. `lrdbench` records estimator and source metadata, but it
does not replace method-specific citations.

