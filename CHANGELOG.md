# Changelog

## Unreleased

- Phase 6 documentation: MkDocs + Material (`mkdocs.yml`), Read the Docs config (`.readthedocs.yaml`), expanded `docs/` pages, pymdownx snippets for root markdown, GitHub Action `docs.yml` for `mkdocs build --strict`, and `Documentation` URL in `pyproject.toml`.
- Phase 5 execution: optional `execution.max_workers` for threaded parallel fits, optional `execution.estimate_cache_dir` (+ `cache_read` / `cache_write`) for on-disk pickled `EstimateResult` reuse; manifest validation for `execution` keys.
- Repository layout: benchmark YAML suites under `configs/suites/`; scaffold `configs/{estimators,generators,contaminations,reports}/`, `docs/`, `examples/`, `paper_support/`, and `tests/{unit,integration,…}` per `lrdbench_repo_schema.txt`.

## 0.1.0

- Initial public alpha: ground-truth, stress-test, and observational modes; baseline estimators and generators; CSV/HTML reporting.
