# Read the Docs

The public documentation is hosted at [lrdbench.readthedocs.io](https://lrdbench.readthedocs.io/).

Read the Docs builds the MkDocs site from `.readthedocs.yaml`, installs the package with the
`docs` extra, and uses `mkdocs.yml` as the site configuration.

If the project slug changes, update:

- `site_url` in `mkdocs.yml`;
- `Documentation` under `[project.urls]` in `pyproject.toml`;
- README and docs links that point to `lrdbench.readthedocs.io`.

Local check before pushing:

```bash
pip install -e ".[docs]"
mkdocs build --strict
```

The strict build fails on broken internal links and missing snippet files.
