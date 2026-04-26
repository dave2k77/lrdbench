# Citation Guidance

If you use `lrdbench` in research, cite the software release and report enough benchmark metadata
for another researcher to reproduce the comparison.

## Software Citation

Use the repository `CITATION.cff` as the citation authority for the current public release. For
manual reference lists, include:

- software name: `lrdbench`;
- author: Davian Chin;
- version: `1.0.0`;
- repository: `https://github.com/dave2k77/lrdbench`;
- license: MIT.

No DOI is attached to `v1.0.0`. If a DOI or archived release bundle is added later, cite that
archived artefact instead of a moving repository URL.

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
