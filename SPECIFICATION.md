# Specification traceability

Implementation of **lrdbench** follows the tracked design specification in
`docs/design_specification.md`. That page is the clean-clone design authority for library
architecture, object schema, contracts, metrics by mode, reporting, YAML manifests,
Python-facing interfaces, and release-stability expectations.

The earlier local file `lrdbench-design-specifications.pdf`, when present, is historical design
context rather than the public source of truth.

The current implemented module map and stage order are in [architecture](docs/architecture.md).
The [API reference](docs/reference/api.md) renders Python definitions; the
[output specification](docs/output_contract.md) embeds the tracked JSON contract, which tests
compare with the Python contract. These are separate interfaces: CSV exports retain a subset
of the in-memory schema.

The paper's frozen producer, runtime, research archive and audit follow the separate
[confirmation workflow](docs/confirmation_benchmark.md). Current library documentation must
not silently replace that study's recorded execution contract.

Runnable benchmark manifests for CI and smoke checks live under `configs/suites/`.
`lrdbench_repo_schema.txt` preserves a historical target-layout proposal, not an inventory of
implemented folders. Use the architecture guide for current ownership. Review the
[maintenance checklist](docs/contributor_checklist.md) in the same PR as behavior changes.
