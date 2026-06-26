# Contributing

Pull requests are welcome. Please keep changes focused and match the existing style in the files you touch.

## Quick start for contributors

1. **Install in editable mode with dev dependencies:**
   ```bash
   pip install -e ".[test,dev,docs,reports]"
   ```

   Use `pip install -e ".[all]"` only when you also need the heavier data-driven dependencies
   (`scikit-learn` and `torch`).

2. **Read the architecture overview:**
   [`docs/architecture.md`](docs/architecture.md) explains the benchmark loop, key modules, and how to add generators, contaminations, and estimators.

3. **Follow the estimator guide if needed:**
   [`docs/adding_estimators.md`](docs/adding_estimators.md) shows the shortest path for enrolling a new estimator.

4. **Run validation before submitting:**
   ```bash
   python -m ruff check .
   python -m pytest
   python -m mkdocs build --strict
   python -m build
   ```

5. **Verify smoke output (for packaging or CLI changes):**
   ```bash
   lrdbench list-suites
   lrdbench run smoke_ground_truth --dry-run
   lrdbench run smoke_ground_truth
   lrdbench validate-output reports/<run_id>
   ```

If you are working in a minimal environment without `pytest-cov`, use
`python -m pytest -q -o addopts=''` for a no-coverage smoke check. Full submissions should still
run the default `python -m pytest` after installing the `test` extra.

## Windows notes

- **Line endings** are governed by `.gitattributes` (text files are LF, `*.ps1`/`*.bat`/`*.cmd`
  are CRLF). Leave Git's `core.autocrlf` unset or `false`; the attributes take precedence, so no
  per-file configuration is needed.
- **Long paths:** some bundled fixtures (e.g. under
  `configs/suites/data/openneuro_ds002691_pilot/csv/`) have long filenames. Cloning into a deep
  directory can hit Windows' 260-character `MAX_PATH` limit and fail checkout with
  `Filename too long`. Enable long-path support once:
  ```bash
  git config --global core.longpaths true
  ```
  (You may also need to enable long paths in Windows itself via the
  `LongPathsEnabled` policy.) Cloning into a short path such as `C:\src\lrdbench` also avoids this.

## Checklists and policies

- [`docs/contributor_checklist.md`](docs/contributor_checklist.md) — pre-submission checklist for estimators, outputs, and validation.
- [`docs/estimator_contract.md`](docs/estimator_contract.md) — formal contract every estimator must satisfy.
- [`docs/third_party_estimators.md`](docs/third_party_estimators.md) — how to register estimators without modifying the core package.
- [`docs/leaderboard_submission_policy.md`](docs/leaderboard_submission_policy.md) — rules for public leaderboard entries.

## Getting help

If you are unsure whether a change fits the project scope, open a [GitHub issue](https://github.com/dave2k77/lrdbench/issues) first. For common errors during development, see [`docs/faq.md`](docs/faq.md).
