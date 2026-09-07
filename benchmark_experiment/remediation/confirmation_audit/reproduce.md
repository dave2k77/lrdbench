# Rebuilding the audit package

Use the pinned Python environment associated with the completed confirmation.
The auditors do not import `lrdbench` or the original result-summary functions.
They use NumPy, pandas, matplotlib and the standard library; pytest and Ruff
are used for verification. Keep the frozen runtime and raw production archive
read-only throughout.

In the following commands, `SOURCE` is the full `confirmation-production-v1`
directory, `RUNTIME` is the preserved `confirmation-runtime-9c02d04` directory,
and `OUTPUT` is `benchmark_experiment/remediation/confirmation_audit/results`.
Run from this checkout using the pinned interpreter. Replace these placeholders
with paths; quote paths containing spaces.

```text
python benchmark_experiment/remediation/confirmation_audit/audit.py --source SOURCE --lock RUNTIME/benchmark_experiment/remediation/protocol-v1/scientific_design_lock.json --output OUTPUT
python benchmark_experiment/remediation/confirmation_audit/write_findings.py --source SOURCE --output OUTPUT
python benchmark_experiment/remediation/confirmation_audit/export_results.py --source SOURCE --output OUTPUT
python benchmark_experiment/remediation/confirmation_audit/validate_package.py --source SOURCE --runtime RUNTIME --output OUTPUT
python -m pytest -q -o addopts='' benchmark_experiment/remediation/confirmation_audit/test_audit.py
python -m ruff check .
```

If the current user cannot access pytest's default temporary directory, select
a new writable temporary directory with `--basetemp`.

The complete audit took about 123 seconds on this machine. It streams raw chunks
and limits cell-level reconstruction to the 31 fixed summary-draw positions in
the audit specification. Domain validation loads its constituent summary arrays;
allow roughly 1–2 GiB of working memory. The script stops on a failed check and
does not alter any raw or canonical producer artifact. A fresh destination is
preferable when retaining evidence from multiple audit executions.

The six compressed cell/domain CSV tables contain all 118,917 summary rows.
The plain CSV files provide convenient subsets, and `planned_contrasts.csv.gz`
retains every declared contrast. These subsets overlap; their row counts must
not be added as if they represented additional simulation records.
`narrative_evidence.csv` identifies the source rows used in the findings report.
The original canonical archive additionally retains all 1,999 summary draws,
availability counts and support files.

`audit_evidence.json` binds the independent auditor to its exact source and
specification hashes. `export_provenance.json` binds tables and figures to the
canonical summary hash. `package_validation.json` checks every derived table
against the canonical rows, all historical baseline hashes and the 90 preserved
runtime source files. Tests specifically reject altered values, draw positions,
denominators, method rosters and support labels.

This is a results and reporting package. Public library source, frozen protocol,
producer source, and public CSV contracts are unchanged. The original OneDrive
dependency-lock filename has two preserved conflict copies in the working tree;
the authoritative runtime uses the exact archived lock outside OneDrive.
