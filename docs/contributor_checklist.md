# Contributor Checklist

Use this checklist before opening a contribution that adds or changes benchmark behaviour.

## Estimators

- The estimator implements `BaseEstimator`.
- The estimator has a stable name and version.
- The target estimand is explicit.
- Assumptions and expected operating regimes are documented.
- Parameters are read from `EstimatorSpec.parameter_schema`.
- Short or degenerate signals return `valid=False` with `failure_reason`.
- Unexpected exceptions are captured as `exception:<type>:<message>`.
- Diagnostics are structured and JSON-serialisable.
- Estimator-level uncertainty support is documented.
- Tests cover at least one valid fit and one invalid fit.

## Benchmark Outputs

- Any new report table has documented columns.
- Any public output surface change updates `configs/contracts/public_output_contract.json`.
- `lrdbench validate-output <run_root>` still passes for smoke reports.
- Changelog entries describe public-surface changes.

## Documentation maintenance

Update documentation in the same pull request as the behavior it describes. If no update
is needed, explain why in the pull request's documentation-impact section.

| Change | Review these sources and guides |
| --- | --- |
| Estimator equation, input, default or bound | Implementation and registry; parameter glossary; estimator status; migration notes |
| Metric, denominator, missingness or ranking | Evaluator/metric catalog/leaderboard; interpretation semantics; stress tutorial; output contract |
| CLI, manifest or dependency | CLI/schema and `pyproject.toml`; installation, quickstart and runnable examples |
| Stage order, module ownership or record lineage | Runner/execution/preprocessing; architecture; design specification; benchmark protocol; relevant workflow tests |
| Python schema or persisted outputs | Dataclasses and generated API reference; result store/reporter; Python and JSON output contracts; migration notes; output-contract tests and a generated smoke report |
| Research design, results or manuscript | Frozen protocol and audited exports; confirmation guide; current next steps; paper workflow |
| Release or archive publication | Actual release/deposit metadata; README; citation guidance; availability statements |

- Link to the central [confirmation guide](confirmation_benchmark.md) instead of repeating
  experimental counts across status pages. Check its counts against `audit_evidence.json`
  and its hashes against `export_provenance.json` when the referenced study changes.
- Date status reviews. Mark old development logs as historical; never relabel an old
  result as having been produced by current source or rewrite frozen evidence in place.
- Keep released package behavior distinct from unreleased `main`, and public source
  availability distinct from public deposition of the full raw results.
- Regenerate affected manuscript assets from their sources and repeat numerical and visual
  checks. Do not manually patch generated values to make a claim agree.
- Run the strict documentation build. CI runs it on every push and pull request, but a
  passing build checks rendering and links, not whether prose is scientifically current.
- The output guide embeds the tracked JSON contract and the API reference renders source
  definitions. Keep these generated references; review explanatory prose against stage order,
  pairing, conditional outputs and fields that are not persisted. `validate-output` checks
  minimum structure, not scientific completeness or archive integrity.

## Validation commands

Run:

```bash
python -m ruff check .
python -m pytest
python -m mkdocs build --strict
python scripts/check_docs.py site
python -m build
```

For packaging or CLI changes, also install the built wheel in a temporary environment and run:

```bash
lrdbench list-suites
lrdbench run smoke_ground_truth
lrdbench validate-output reports/<run_id>
```
