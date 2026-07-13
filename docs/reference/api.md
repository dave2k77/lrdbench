# Python API reference

Generated with [mkdocstrings](https://mkdocstrings.github.io/) from package docstrings.
Install the package and docs extras: `pip install -e ".[docs]"`.

## Runner

::: lrdbench.runner.BenchmarkRunner
    options:
      members:
        - run
        - preview
        - __init__

::: lrdbench.runner.run_manifest_path
::: lrdbench.runner.run_manifest_mapping

## Manifest

::: lrdbench.manifest.load_manifest
::: lrdbench.manifest.manifest_from_mapping

## Estimator interface

::: lrdbench.interfaces.BaseEstimator
    options:
      members:
        - spec
        - fit

::: lrdbench.interfaces.BaseGenerator
    options:
      members:
        - family
        - version
        - generate

## Bundled temporal estimators

::: lrdbench.estimators.temporal.RSEstimator
::: lrdbench.estimators.temporal.DFAEstimator
::: lrdbench.estimators.temporal.DMAEstimator
::: lrdbench.estimators.temporal.AbsoluteMomentEstimator
::: lrdbench.estimators.temporal.VarianceEstimator
::: lrdbench.estimators.temporal.VarianceResidualEstimator

## Bundled spectral estimators

::: lrdbench.estimators.spectral.GPHEstimator
::: lrdbench.estimators.spectral.PeriodogramRegressionEstimator
::: lrdbench.estimators.spectral.PeriodogramBetaEstimator
::: lrdbench.estimators.spectral.WhittleMLEEstimator
::: lrdbench.estimators.spectral.ModifiedLocalWhittleEstimator

## Bundled timescale estimators

::: lrdbench.estimators.timescale.ACFDecayEstimator

## Bundled geometric estimators

::: lrdbench.estimators.geometric.HiguchiEstimator
::: lrdbench.estimators.geometric.GHEEstimator

## Bundled wavelet estimators

::: lrdbench.estimators.wavelet.WaveletOLSEstimator
::: lrdbench.estimators.wavelet.WaveletAbryVeitchEstimator
::: lrdbench.estimators.wavelet.WaveletBardetEstimator
::: lrdbench.estimators.wavelet.WaveletJensenEstimator
::: lrdbench.estimators.wavelet.WaveletWhittleEstimator

## Bundled data-driven estimators

::: lrdbench.estimators.data_driven.MLRandomForestEstimator
::: lrdbench.estimators.data_driven.MLSVREstimator
::: lrdbench.estimators.data_driven.MLCNNEstimator
::: lrdbench.estimators.data_driven.MLLSTMEstimator

## LRD discriminators

These target the decision estimand `lrd_class` and emit a `[0, 1]` score scored by the
classification metric family (`roc_auc`, `balanced_accuracy`, `true_positive_rate`,
`false_positive_rate`).

::: lrdbench.estimators.discrimination.ThresholdHurstDiscriminator
::: lrdbench.estimators.discrimination.LowFreqSpectralDiscriminator
::: lrdbench.estimators.discrimination.ScaleCrossoverDiscriminator
::: lrdbench.estimators.discrimination.ICModelSelectDiscriminator

## Registries

::: lrdbench.registries.EstimatorRegistry
::: lrdbench.registries.GeneratorRegistry
::: lrdbench.registries.ContaminationRegistry

## Defaults

::: lrdbench.defaults.build_default_estimator_registry
::: lrdbench.defaults.build_default_generator_registry
::: lrdbench.defaults.build_default_contamination_registry

## Schema dataclasses

::: lrdbench.schema.BenchmarkManifest
::: lrdbench.schema.SeriesRecord
::: lrdbench.schema.EstimateResult
::: lrdbench.schema.EstimatorSpec
::: lrdbench.schema.MetricSpec
::: lrdbench.schema.MetricValue
::: lrdbench.schema.MetricBundle
::: lrdbench.schema.LeaderboardSpec
::: lrdbench.schema.LeaderboardRow
::: lrdbench.schema.ReportSpec
::: lrdbench.schema.ReportBundle
::: lrdbench.schema.BenchmarkRunOutput
::: lrdbench.schema.PluginProvenanceRecord

## Validation and contracts

::: lrdbench.validation.validate_manifest
::: lrdbench.validation.validate_metric_admissibility
::: lrdbench.validation.validate_truth_compatibility
::: lrdbench.validation.truth_for
::: lrdbench.output_contract.public_output_contract
::: lrdbench.output_contract.required_output_files
::: lrdbench.output_contract.validate_output_contract

## Bootstrap utilities

::: lrdbench.bootstrap.circular_block_resample
::: lrdbench.bootstrap.bootstrap_statistic_distribution
::: lrdbench.bootstrap.symmetric_percentile_cis

## Plugin discovery

::: lrdbench.plugin_loader.PluginDiscoveryResult
::: lrdbench.plugin_loader.discover_plugins_from_env
::: lrdbench.plugin_loader.build_estimator_registry_with_plugins

## Packaged assets and testing helpers

::: lrdbench.public_assets.list_public_suites
::: lrdbench.public_assets.resolve_manifest_argument
::: lrdbench.testing.estimator_spec
::: lrdbench.testing.synthetic_series_record
::: lrdbench.testing.smoke_fit_estimator
::: lrdbench.testing.assert_valid_estimate
::: lrdbench.testing.assert_invalid_estimate

