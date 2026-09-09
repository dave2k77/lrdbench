# Documentation review — September 2026

Reviewed on 9 September 2026 against the development branch, library implementation,
tracked manifests and built MkDocs pages. This review extends the architecture/output review;
it does not rerun the frozen experiment or certify every scientific method.

## Findings and corrections

| Area | Finding | Correction |
| --- | --- | --- |
| Mathematics | No math extension or renderer configured; mathematical expressions appeared as prose/code | Enable Arithmatex and pinned MathJax; typeset the estimand relations and coverage equation; contain wide display equations |
| Scientific meaning | Tutorial treated H, spectral slope and timescale as universally convertible; claimed null outcomes without run evidence | State stationary-fGn and OU restrictions, distinguish fBm paths, remove unsupported performance claims |
| Classification | Point-cutoff exceedance described as a test false-positive rate; scores described too strongly | Separate point diagnostics, experimental classifier scores and calibrated hypothesis tests |
| Truths and intervals | fOU incorrectly said to declare spectral truth; raw exports implied to retain full diagnostics | Match generator truth declarations and distinguish interval CSV fields from in-memory diagnostics |
| Parameters | Wavelet `max_level` was advertised but not consumed; ACF stopping and taper support were inaccurate | Document actual level-drop controls, automatic ACF threshold/cap and estimator-specific taper use |
| Examples | FAQ CSV keys were wrong; stress fragment omitted a required metric; custom-registry snippet omitted its import | Correct examples, label fragments, provide an installed-suite quickstart and portable observational commands |
| Setup/plugins | Editable install presented as a PyPI command; plotting dependency and Windows plugin path separators misdescribed | Separate release/source installs and document core dependencies and platform path-list separators |
| Navigation | Long mixed user guide and flat API object headings obscured reading paths | Group by purpose, add a task-oriented homepage and nest API objects under their sections |
| Historical material | Old observational gaps looked current and competed with current guides in search | Add historical banners, a History section and explicit search exclusions for old plans |
| Validation | Minimum-header checks described as reproduction or content verification | Explain structural limits and add a separate built-site audit to CI |

## Verification

- Strict build and built-site audit passed across 47 Markdown pages. A deliberately broken
  cross-page anchor was detected, and the restored build passed.
- Six existing tutorial/custom-estimator integration tests passed.
- Corrected custom-estimator code was executed directly, including constant/nonfinite failure
  cases; ground-truth/stress YAML fragments and the custom manifest import validated.
- Browser review checked desktop and narrow-screen layout, mobile navigation, light/dark math,
  inline mathematics in glossary tables, and search results for `j_drop_high`.
- MathJax produced no math-error elements on the reviewed mathematical pages.


The strict MkDocs build and `scripts/check_docs.py` validate the built site, including
all local link targets/anchors, one H1 per page, complete navigation, the embedded contract,
math assets and historical search exclusions. Mathematical rendering and responsive layout
are checked separately in a browser. The review also exercises corrected examples against
the package and checks relevant tutorial workflows.

## Deployment and limits

The live default Read the Docs site inspected during review still showed the earlier homepage
and navigation. Changes in the documentation PR need merging and a successful Read the Docs
build before the hosted default can reflect them. GitHub Actions and local builds are separate
from the hosted deployment.

MathJax loads from a pinned CDN URL; blocked network access can prevent typesetting despite a
successful static build. Structural CI does not evaluate mathematical truth or browser layout.
Content review should continue in the same PR as changes to scientific behavior, defaults and
outputs; see the [maintenance guide](readthedocs.md).
