# Public Medium Outputs

This page records reference output shapes for the tracked `public_medium_*` suites. Generated
reports are intentionally ignored by Git; these notes provide clean-clone comparison targets for
public beta users.

All runs below were produced locally on 2026-04-26 with:

```bash
lrdbench run <suite-name>
lrdbench validate-output reports/public_medium/<run_id>
```

Each listed run passed the `0.3.0-beta` output contract.

| Suite | Run ID | Per-stratum rows | Benchmark uncertainty rows | Disagreement rows | Failure rows | Leaderboard rows | Suite-specific rows |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `public_medium_canonical_ground_truth` | `deb4b5d9-89b6-466f-9b5c-fca84540c3e8` | 459 | 170 | 363 | 128 | 5 | 0 sensitivity |
| `public_medium_stress_contamination` | `14741c46-8dc0-4984-a993-ef76b729170f` | 2631 | 880 | 1575 | 616 | 4 | 1872 stress |
| `public_medium_null_false_positive` | `13be456b-5b1e-4a0c-84a2-1c9b6839b9b4` | 167 | 32 | 371 | 44 | 4 | 0 sensitivity |
| `public_medium_sensitivity_disagreement` | `dbfc4552-269a-4174-8c80-a4a4a12e8410` | 616 | 105 | 925 | 294 | 9 | 150 sensitivity |

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
