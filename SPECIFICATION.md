# Specification traceability (Phase 0)

Implementation of **lrdbench** follows the tracked design specification in
`docs/design_specification.md`. That page is the clean-clone design authority for library
architecture, object schema, contracts, metrics by mode, reporting, YAML manifests,
Python-facing interfaces, and release-stability expectations.

The earlier local file `lrdbench-design-specifications.pdf`, when present, is historical design
context rather than the public source of truth.

Runnable benchmark manifests for CI and smoke checks live under `configs/suites/`. A longer-term target tree for the whole repository (including an aspirational `src/lrdbench/` package layout) is sketched in `lrdbench_repo_schema.txt`.
