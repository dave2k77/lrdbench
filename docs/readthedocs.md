# Documentation maintenance

Read the Docs builds the MkDocs site from `.readthedocs.yaml`, installs the package with the
`docs` extra, and uses `mkdocs.yml`. The hosted site is
[lrdbench.readthedocs.io](https://lrdbench.readthedocs.io/).
An open documentation PR does not by itself update the hosted default version; check the deployed
page after merge and a successful Read the Docs build.

## Build and verify

From the repository root:

```bash
pip install -e ".[docs]"
python -m mkdocs build --strict
python scripts/check_docs.py site
```

The strict build checks links and missing snippets. The additional audit checks navigation
coverage, page titles, local link targets/anchors, the embedded output contract, math assets and
historical-page search exclusions. CI runs both checks. Browser review is still required for
layout, search behavior and actual equation typesetting; structural checks cannot certify those.

## Mathematical notation

Use `$...$` for inline mathematics and `$$` on separate lines for display equations. Keep
parameter keys and literal code in backticks. For example:

```text
For stationary fGn, $\beta=2H-1$.

$$
H=\frac{\beta+1}{2}.
$$
```

Arithmatex protects TeX during Markdown conversion. The MathJax configuration in
`docs/javascripts/mathjax.js` renders those wrappers with the pinned MathJax 3.2.2 script.
It follows the [Material math integration](https://squidfunk.github.io/mkdocs-material/reference/math/).
The script and its fonts require CDN access. If equations show literal delimiters, check asset
loading and browser errors; a successful MkDocs build alone does not confirm math rendering.

Normal page navigation uses a fresh MathJax startup. If instant navigation is enabled later,
add and verify the corresponding re-typesetting lifecycle. Display equations scroll inside their
container on small screens. Check fractions, subscripts, Greek symbols and equations inside tables
in both color modes and at a narrow viewport.

## Navigation and indexing

Every Markdown page belongs in `mkdocs.yml`. Keep the six top-level sections focused: Home,
Tutorials, User guide, Research, Development and History. Use one H1 per page, H2 for sections,
and H3 for subsections. API object headings sit below their section heading; deeper members stay
out of the page TOC, whose depth is capped at three.

Old plans retain their URLs and carry dated banners plus `search.exclude: true`.
Matching `.readthedocs.yaml` search exclusions cover the hosted server-side index too. They remain
accessible through History without competing with current instructions in search. Do not exclude
current migration notes or provenance guidance. The homepage links reading paths rather than
repeating the full sidebar.

## Content review

Trace defaults and accepted parameters to the implementation. Validate complete YAML examples,
label partial fragments, and distinguish a released package install from a source checkout.
For scientific claims, state the signal representation, model assumptions, estimand and failure
or missingness denominator. Preserve the frozen study's producer identity and original evidence.

The [September review](documentation_review.md) records findings, fixes and validation limits.

## Hosting changes

If the project slug changes, update `site_url` in `mkdocs.yml`, the Documentation URL in
`pyproject.toml`, and repository/docs links. Keep `.readthedocs.yaml` and the local build aligned;
review the hosted Read the Docs build and version settings separately from GitHub Actions.
`mkdocs.fail_on_warning: true` makes Read the Docs treat MkDocs warnings as errors, following
the [Read the Docs configuration reference](https://docs.readthedocs.com/platform/stable/config-file/v2.html#mkdocs).
