# Leaderboard Submission Policy

Leaderboards are accepted only as summaries of reproducible benchmark runs. A submitted rank is not
a universal estimator ranking.

## Required Materials

A leaderboard submission must include:

- the manifest or packaged suite name;
- the `lrdbench` version or Git commit;
- the output contract version;
- `manifest/environment.json`;
- `artefacts/artefact_index.csv`;
- `tables/leaderboard.csv`;
- raw metric exports under `raw/`;
- confirmation that `lrdbench validate-output <run_root>` passed.

## Eligible Runs

Use tracked public suites for comparable public submissions:

- `public_small_*` for quick checks;
- `public_medium_*` for public beta comparisons.

Custom manifests are welcome for discussion, but they should be labelled as custom and should not be
mixed with canonical public-suite leaderboards.

## Estimator Requirements

Each estimator must declare:

- name and version;
- family;
- target estimand;
- assumptions;
- parameter settings;
- uncertainty behavior;
- known failure modes.

Third-party estimators should link to implementation code and tests. Invalid estimates, missing
uncertainty, and warnings must remain visible in exported outputs.

## Interpretation Rules

- Report component metrics alongside composite ranks.
- Do not compare estimators that target incompatible estimands unless the manifest explicitly
  defines the comparison.
- Do not use observational-mode leaderboards as evidence of ground-truth accuracy.
- Treat stress-test leaderboards as robustness summaries for declared contaminations only.
- Include failure and missing-output rates when reporting results.

## Review Criteria

Submissions may be rejected or marked non-comparable when:

- required artefacts are missing;
- the output contract check fails;
- estimator metadata is incomplete;
- a custom manifest is presented as a canonical public-suite result;
- interpretation claims exceed the benchmark mode or metric definitions.
