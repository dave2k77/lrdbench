# Python API reference

Generated with [mkdocstrings](https://mkdocstrings.github.io/) from package docstrings.
Install the package and docs extras: `pip install -e ".[docs]"`.

## Runner

::: lrdbench.runner.BenchmarkRunner
    options:
      members:
        - run
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
::: lrdbench.estimators.spectral.WhittleMLEEstimator
::: lrdbench.estimators.spectral.ModifiedLocalWhittleEstimator

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

## Registries

::: lrdbench.registries.EstimatorRegistry
::: lrdbench.registries.GeneratorRegistry
::: lrdbench.registries.ContaminationRegistry

## Defaults

::: lrdbench.defaults.build_default_estimator_registry
::: lrdbench.defaults.build_default_generator_registry
::: lrdbench.defaults.build_default_contamination_registry
