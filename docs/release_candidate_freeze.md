# Release Candidate Freeze Review

This page records the public surfaces reviewed for `0.9.0rc1`. The intent is to make the release
candidate explicit: changes after this point should be bug fixes, documentation corrections, or
additive extensions that do not break existing manifests or result consumers.

## Package and Contract Versions

- Python package version: `0.9.0rc1`.
- Planned Git tag: `v0.9.0-rc1`.
- Public output contract version: `0.9.0-rc1`.

## Stable Public Entry Points

- CLI: `lrdbench run`, `lrdbench validate`, `lrdbench validate-output`,
  `lrdbench list-suites`, `lrdbench list-metrics`, and `lrdbench list-estimators`.
- Estimator API: `lrdbench.interfaces.BaseEstimator`,
  `lrdbench.interfaces.EstimatorMetadata`, and `lrdbench.schema.EstimateResult`.
- Author utilities: `lrdbench.testing` helpers for estimator metadata and smoke checks.
- Output contract: `lrdbench.output_contract.PUBLIC_OUTPUT_CONTRACT` and
  `configs/contracts/public_output_contract.json`.

## Manifest Schema

The release-candidate manifest surface is the schema exercised by the packaged smoke,
public-small, and public-medium suites:

- benchmark identity and `mode`;
- `records`;
- `estimators`;
- `metrics`;
- `leaderboard`;
- `report`;
- `seeds`;
- optional `uncertainty`;
- optional `execution`;
- optional contamination and observational-source blocks for the modes that use them.

No manifest-field rename is planned before `v1.0.0`.

## Result-Store and Report Columns

The required files and columns listed in the output contract are frozen for release-candidate
review. Downstream tools should treat the contract as a minimum required set and allow documented
dynamic columns such as `metric__*` and `stratum__*`.

No result-store or report-column rename is planned before `v1.0.0`.

## Metric Names

The core metric names exposed by `lrdbench list-metrics` are frozen for release-candidate review:

- `bias`
- `mae`
- `rmse`
- `coverage`
- `coverage_error`
- `ci_width`
- `validity_rate`
- `runtime`
- `instability`
- `preprocessing_sensitivity`
- `estimate_drift`
- `relative_degradation_ratio`
- `validity_collapse`
- `coverage_collapse`
- `false_positive_lrd_rate`
- `cross_estimator_dispersion`
- `pairwise_estimator_disagreement`
- `family_level_disagreement`
- `parameter_variant_sensitivity`
- `max_variant_drift`

New metrics may be added after `0.9.0rc1`, but existing metric names should not be repurposed.

## Known Pre-1.0 Caveats

The project remains pre-1.0 until the final public release. The known limitations page remains the
authority for scientific and implementation caveats; this freeze review covers public interface
stability rather than claims of estimator superiority.

