# Specification traceability (Phase 0)

Implementation of **lrdbench** follows the frozen architecture from `lrdbench-design-specifications.pdf` (library architecture, object schema, contracts, metrics by mode, reporting, YAML manifest, Python-facing interfaces, and phased roadmap §6). That PDF is the design authority when present in a local working copy; it is not currently tracked in the clean repository.

Phase 0 exit: the local design PDF is the authoritative design when available; code maps to sections 1–5 (schema, evaluation, reporting, interfaces, manifests) and Phase 1 scope in §6.5 / backlog §6.13.

Runnable benchmark manifests for CI and smoke checks live under `configs/suites/`. A longer-term target tree for the whole repository (including an aspirational `src/lrdbench/` package layout) is sketched in `lrdbench_repo_schema.txt`.
