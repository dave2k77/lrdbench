# Public Research Release Roadmap

This roadmap tracks the path from the current working research framework to a public,
citeable research release. The goal is not to polish the local manuscript workflow, but to make
the tracked library defensible as an open benchmark framework for long-range dependence (LRD)
estimation.

## Release Philosophy

The public product is the tracked package, docs, examples, tests, and public benchmark suites.
Local paths such as `paper_support/`, `configs/suites/paper/`, generated reports, and local caches
are personal research infrastructure and should not block the public library release.

The core public mission is:

> A comprehensive, reproducible benchmarking framework for LRD estimation with uncertainty
> quantification, leaderboards, and failure-mode analysis.

## Current Position

The project has crossed from scaffold/prototype into a usable research instrument. The remaining
work is mostly validation, documentation, canonical benchmark curation, and public reproducibility
hardening.

Approximate status:

- Core research framework: 80-90% complete for an alpha/beta research tool.
- Open research usefulness: 70-80% complete.
- Polished public v1.0 library: 55-65% complete.
- Local manuscript workflow: separate from public release readiness.

## Alpha 0.1: Public Research Alpha

Goal: make the framework understandable, runnable, and citeable by early research users.

Scope:

- Freeze a tracked public benchmark suite set:
  - `smoke_*`: CI-fast.
  - `public_small_*`: reproducible tutorial-scale.
  - `public_medium_*`: serious but still laptop-runnable.
- Move the core design specification from local PDF dependency into tracked docs.
- Add a clear estimator status table:
  - `baseline`;
  - `approximate`;
  - `experimental`;
  - `reference-grade` only where strongly validated.
- Document uncertainty semantics:
  - estimator bootstrap CI;
  - benchmark bootstrap CI;
  - paired estimator-difference CI;
  - missing uncertainty.
- Document leaderboard semantics and failure modes.
- Ensure `lrdbench run configs/suites/public_small_*.yaml` works from a clean clone.
- Add a "how to add an estimator" guide with one tested custom estimator example.
- Keep README language honest: alpha, research tool, not a truth oracle.

Exit criteria:

- `python -m ruff check .` passes.
- `python -m pytest` passes.
- `python -m mkdocs build --strict` passes.
- Clean clone can run public small suites.
- Docs explain modes, metrics, uncertainty, leaderboards, limitations.
- Tag `v0.1.0-alpha`.

## Alpha 0.2: Validation Alpha

Goal: make implementation quality defensible.

Scope:

- Add validation tests for generators:
  - fGn/fBm scaling sanity;
  - ARFIMA memory-parameter sanity;
  - MRW/fOU smoke statistical checks.
- Add estimator validation tests or notebooks against known synthetic regimes.
- Improve coverage for:
  - spectral estimators;
  - wavelet estimators;
  - contaminations;
  - observational sources.
- Add estimator assumption metadata consistently.
- Add failure-mode taxonomy docs and tests.
- Add a public "known limitations" page.

Progress:

- Done: statistical generator validation tests cover fGn/fBm scaling ordering, ARFIMA memory
  behavior, MRW intermittency, and fOU mean reversion.
- Done: statistical estimator validation tests cover baseline Hurst-proxy estimators on fGn and
  baseline spectral long-memory estimators on ARFIMA.
- Done: focused unit coverage now covers contamination operators, wavelet valid/invalid paths, and
  observational source loading.
- Done: estimator status docs list each estimator target, assumptions, expected regime, and known
  failure risks.
- Done: public failure-mode taxonomy and known-limitations pages are included in the user guide.

Exit criteria:

- Coverage is meaningfully improved in weak modules.
- Each estimator has documented target estimand, assumptions, expected regime, and known failure
  risks.
- Tag `v0.2.0-alpha`.

## Beta 0.3: Public Benchmark Beta

Goal: make the benchmark protocol stable enough for external comparison.

Scope:

- Define canonical tracked suites:
  - `canonical_ground_truth_small` / `canonical_ground_truth_medium`;
  - `stress_contamination_small` / `stress_contamination_medium`;
  - `null_false_positive_small` / `null_false_positive_medium`;
  - `sensitivity_disagreement_small` / `sensitivity_disagreement_medium`;
  - optional observational demo suite.
- Add a machine-readable expected output contract:
  - required CSVs;
  - required metadata;
  - required columns.
- Add report artefact-index docs.
- Add reproducibility guide:
  - seeds;
  - caches;
  - environment capture;
  - version pinning.
- Add CLI commands:
  - `lrdbench validate <manifest>`;
  - `lrdbench list-metrics`;
  - optionally `lrdbench list-estimators`.
- Add packaging checks.

Progress:

- Done: canonical public-small and public-medium tracked suites are present.
- Done: `lrdbench validate <manifest>` exists.
- Done: machine-readable output contract is tracked in
  `configs/contracts/public_output_contract.json`.
- Done: `lrdbench validate-output <run_root>` checks generated reports against the public output
  contract.
- Done: `lrdbench list-metrics` and `lrdbench list-estimators` expose built-in discovery.
- Done: `lrdbench list-suites` and suite-name resolution let installed users validate/run
  packaged public suites.
- Done: output-contract and reproducibility guides are included in the user guide.
- Done: packaging workflow builds distributions, installs the wheel, runs a smoke report, and
  checks the generated output contract.
- Done: all tracked public-medium manifests validate cleanly.
- Done: all tracked public-medium suites were run locally and passed `validate-output`; reference
  row counts are documented.
- Done: Beta 0.3 changes were committed and pushed.

Exit criteria:

- External user can run medium suites and compare outputs.
- Public benchmark protocol is stable enough to cite.
- Tag `v0.3.0-beta`.

## Beta 0.4: External Contributor Beta

Goal: make it easy for other researchers to plug in estimators.

Scope:

- Harden estimator interface docs.
- Add estimator plugin/enrolment examples:
  - Python class;
  - custom params;
  - custom diagnostics;
  - uncertainty support.
- Add contributor checklist.
- Add manifest examples for third-party estimators.
- Add test utilities for estimator authors.
- Add issue templates for estimator validation and benchmark submissions.
- Add leaderboard submission policy: what counts and what does not.

Progress:

- Done: expanded estimator contract docs and added an "Adding estimators" guide.
- Done: added importable test helpers in `lrdbench.testing` for estimator-author smoke tests.
- Done: added packaged `lrdbench.examples.custom_estimator` with valid and invalid path tests.
- Done: added contributor checklist and issue templates for estimator validation and benchmark
  submissions.
- Done: added a programmatic third-party estimator workflow example with report and leaderboard
  output validation.
- Done: added leaderboard submission policy.
- Done: Beta 0.4 changes were committed and pushed.

Exit criteria:

- A researcher can add an estimator without reading internals.
- Third-party estimator outputs are evaluated consistently.
- Tag `v0.4.0-beta`.

## Release Candidate 0.9

Goal: prepare for a stable public research release.

Scope:

- API review.
- Manifest schema review.
- Result-store schema review.
- Documentation pass.
- Rename or deprecate awkward fields.
- Freeze metric names and output column names.
- Add migration notes.
- Add citation guidance.
- Publish docs.
- Build source and wheel locally.
- Test install in a clean environment.

Progress:

- In progress: package and output-contract versions advanced for release-candidate checks.
- In progress: API/schema/metric freeze review, migration notes, and citation guidance added to
  the public docs.
- In progress: stale alpha/beta roadmap status is being folded into phase progress notes.

Exit criteria:

- No known schema churn is planned.
- Clean install works.
- Docs are complete enough for independent use.
- Tag `v0.9.0-rc1`.

## v1.0 Public Research Release

Goal: credible, stable, citeable benchmark framework.

Scope:

- Stable manifest schema.
- Stable estimator contract.
- Stable core metric catalog.
- Stable public benchmark suites.
- Stable result export contract.
- Full docs site.
- Changelog.
- Citation file.
- Clear governance and maintenance statement.
- Optional archived benchmark result bundle or DOI.

Exit criteria:

- External reproducibility is demonstrated.
- Public docs are coherent.
- Known limitations are explicit.
- Release artefacts are built and tested.
- Tag `v1.0.0`.
