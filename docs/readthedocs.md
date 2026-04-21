# Hosting on Read the Docs

1. Sign in at [readthedocs.org](https://readthedocs.org/) and **Import a project** from your Git host.
2. Point the default branch at the repository that contains this `mkdocs.yml` and `.readthedocs.yaml`.
3. Read the Docs will detect **MkDocs** from `.readthedocs.yaml` and run `pip install .[docs]` then `mkdocs build`.
4. Under **Admin → Domains**, note the default subdomain (for example `lrdbench.readthedocs.io`). Set that URL in `mkdocs.yml` (`site_url`) and in `pyproject.toml` under `[project.urls]` → `Documentation` if you rename the project slug.

Local check before pushing:

```bash
pip install -e ".[docs]"
mkdocs build --strict
```

The strict build fails on broken internal links and missing snippet files.
