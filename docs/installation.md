# Installation

## Library and CLI

From the repository root or PyPI:

```bash
pip install -e .
```

Development tooling:

```bash
pip install -e ".[test,dev]"
```

## Documentation build (local)

Install documentation dependencies and serve the site:

```bash
pip install -e ".[docs]"
mkdocs serve
```

The site configuration is `mkdocs.yml` at the repository root. **Read the Docs** builds the same site using `.readthedocs.yaml`; the hosted site is [lrdbench.readthedocs.io](https://lrdbench.readthedocs.io/).

## Optional extras

| Extra        | Purpose                                      |
| ------------ | -------------------------------------------- |
| `reports`    | Jinja2 / tabulate helpers for richer reporting |
| `parquet`    | Parquet export via PyArrow                   |
| `ml`         | scikit-learn baselines: `MLRandomForest`, `MLSVR` |
| `nn`         | PyTorch baselines: `MLCNN`, `MLLSTM`         |
| `data-driven` | All ML and NN baseline dependencies        |
| `docs`       | MkDocs + Material + mkdocstrings             |
| `test`       | pytest, coverage, Hypothesis                 |
| `dev`        | Ruff, mypy, build, twine, pre-commit         |
| `all`        | Reports, parquet, docs, notebooks, tests, dev tools, and all data-driven dependencies |

Example: `pip install -e ".[docs,test]"`.

For a full local development environment, including the heavier scikit-learn and PyTorch
data-driven dependencies, use:

```bash
pip install -e ".[all]"
```

For a lighter development environment that avoids PyTorch, prefer `.[test,dev,docs,reports]`.

Because the repository's default pytest configuration enables coverage reports, install the `test`
extra before running `python -m pytest`. For a quick no-coverage smoke check in a minimal
environment, run `python -m pytest -q -o addopts=''`.

Data-driven smoke benchmarks need the feature-based ML extra and reporting support:

```bash
pip install -e ".[ml,reports]"
lrdbench run configs/suites/smoke_data_driven.yaml
```

The neural-network extra may install a large PyTorch distribution depending on your platform. Use
`ml` for the packaged RF/SVR smoke suite, and install `nn` only when running CNN/LSTM benchmarks.
