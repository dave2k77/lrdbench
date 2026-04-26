# Governance and Maintenance

`lrdbench` is maintained as a research benchmark framework. The maintainer reviews changes for
scientific interpretation risk, reproducibility impact, and compatibility with the public benchmark
contract.

## Maintenance Scope

The maintained public surface includes:

- the Python package under `src/lrdbench`;
- tracked smoke, public-small, and public-medium benchmark suites;
- the estimator interface and author test utilities;
- the manifest schema exercised by public suites;
- the public output contract;
- documentation, examples, issue templates, and release workflows.

Local manuscript workflows, generated reports, local caches, and ignored paper-support artefacts are
not part of the public release contract.

## Compatibility Policy

For `1.x` releases:

- existing public manifest fields should remain valid;
- required output files and required output columns should not be removed or renamed;
- core metric names should not be repurposed;
- estimator-interface changes should be additive where possible;
- breaking changes require migration notes and a major-version release.

Additive metrics, optional output files, new suites, new estimators, and new diagnostics may be
introduced in minor releases when they do not invalidate existing public comparisons.

## Contribution Review

Estimator and benchmark submissions should include:

- a stable estimator or suite name;
- version metadata;
- declared target estimand and assumptions;
- reproducible manifests or tests;
- interpretation caveats where relevant;
- output contract validation for generated reports.

Submissions that affect public benchmark interpretation should be reviewed against the known
limitations, estimator contract, leaderboard policy, and reproducibility guide.

## Release Process

Public releases should:

- pass lint, tests, docs build, package build, and distribution checks;
- validate representative installed-package benchmark runs;
- update changelog, citation metadata, and migration notes when public surfaces change;
- tag the release in Git;
- archive or DOI-tag release artefacts when an archive is available.

No DOI is attached to `v1.0.0`; citation currently uses the software version and GitHub release.

