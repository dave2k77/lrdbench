# Python API reference

Generated with [mkdocstrings](https://mkdocstrings.github.io/) from package docstrings. Install the package and docs extras: `pip install -e ".[docs]"`.

## Runner

::: lrdbench.runner.BenchmarkRunner
    options:
      members:
        - run
        - __init__

## Manifest

::: lrdbench.manifest.load_manifest
::: lrdbench.manifest.manifest_from_mapping

## Estimator interface

::: lrdbench.interfaces.BaseEstimator
    options:
      members:
        - spec
        - fit

## Generator interface

::: lrdbench.interfaces.BaseGenerator
    options:
      members:
        - family
        - version
        - generate
