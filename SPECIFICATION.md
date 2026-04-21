# Specification traceability (Phase 0)

Implementation of **lrdbench** follows the frozen architecture in [`lrdbench-design-specifications.pdf`](lrdbench-design-specifications.pdf) (library architecture, object schema, contracts, metrics by mode, reporting, YAML manifest, Python-facing interfaces, and phased roadmap §6).

Phase 0 exit: the PDF is the authoritative design; code maps to sections 1–5 (schema, evaluation, reporting, interfaces, manifests) and Phase 1 scope in §6.5 / backlog §6.13.

Runnable benchmark manifests for CI and smoke checks live under `configs/suites/`. A longer-term target tree for the whole repository (including an aspirational `src/lrdbench/` package layout) is sketched in `lrdbench_repo_schema.txt`.
