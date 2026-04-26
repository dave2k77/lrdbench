# Public Medium Outputs

This page records reference output shapes for the tracked `public_medium_*` suites. Generated
reports are intentionally ignored by Git; these notes provide clean-clone comparison targets for
release-candidate users.

All runs below were produced from an installed `0.9.0rc1` wheel on 2026-04-26 with:

```bash
lrdbench run <suite-name>
lrdbench validate-output reports/public_medium/<run_id>
```

The row shapes are expected to remain valid under the `0.9.0-rc1` output contract.

| Suite | Run ID | Per-stratum rows | Benchmark uncertainty rows | Disagreement rows | Failure rows | Leaderboard rows | Suite-specific rows |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `public_medium_canonical_ground_truth` | `364e87e6-b122-4a7d-b569-bf454e280824` | 459 | 170 | 363 | 128 | 5 | 0 sensitivity |
| `public_medium_stress_contamination` | `145a05bd-1aad-4583-96a6-c9124ec8b97c` | 2631 | 880 | 1575 | 616 | 4 | 1872 stress |
| `public_medium_null_false_positive` | `92bfbf83-6c0d-43a0-a1be-077172f88a5a` | 167 | 32 | 371 | 44 | 4 | 0 sensitivity |
| `public_medium_sensitivity_disagreement` | `75b13d2b-3d24-4d26-8169-0eb3b8ce9228` | 616 | 105 | 925 | 294 | 9 | 150 sensitivity |

The row counts above exclude CSV headers. Different package versions may change numeric values or
row counts; such changes should be intentional and reflected in the changelog and output contract
when public surfaces change.

## Verification Commands

Run medium suites one at a time:

```bash
lrdbench list-suites
lrdbench run public_medium_canonical_ground_truth
lrdbench validate-output reports/public_medium/<run_id>
```

The stress-contamination and sensitivity/disagreement suites are the slowest medium checks. For
reproducibility comparisons, keep the generated `manifest/environment.json` and
`artefacts/artefact_index.csv` beside the raw CSV exports.
