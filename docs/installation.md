# Installation

## Library and CLI

From the repository root (or after publishing to PyPI):

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

The site configuration is `mkdocs.yml` at the repository root. **Read the Docs** builds the same site using `.readthedocs.yaml` (see the [Read the Docs project](https://readthedocs.org/) once you import this repository).

## Optional extras

| Extra        | Purpose                                      |
| ------------ | -------------------------------------------- |
| `reports`    | Jinja2 / tabulate helpers for richer reporting |
| `parquet`    | Parquet export via PyArrow                   |
| `docs`       | MkDocs + Material + mkdocstrings             |
| `test`       | pytest, coverage, Hypothesis                 |
| `dev`        | Ruff, mypy, build, twine, pre-commit         |

Example: `pip install -e ".[docs,test]"`.
