# Citation Guidance

If you use `lrdbench` in research, cite the software release and report enough benchmark metadata
for another researcher to reproduce the comparison.

## Software Citation

Use the repository `CITATION.cff` as the citation authority for the current public release. For
manual reference lists, include:

- software name: `lrdbench`;
- author: Davian Chin;
- version: `1.2.1`;
- DOI (concept, resolves to latest): `10.5281/zenodo.20937726`;
- repository: `https://github.com/dave2k77/lrdbench`;
- license: MIT.

Releases are archived on Zenodo. Prefer the concept DOI `10.5281/zenodo.20937726`, which always
resolves to the latest archived version; to cite a specific version, use that version's DOI from
the Zenodo record rather than a moving repository URL.

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
