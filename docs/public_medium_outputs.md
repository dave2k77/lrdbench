# Public Medium Outputs

This page records reference output shapes for the tracked `public_medium_*` suites. Generated
reports are intentionally ignored by Git; these notes provide clean-clone comparison targets for
release-candidate users.

All runs below were produced from an installed release wheel on 2026-04-26 with:

```bash
lrdbench run <suite-name>
lrdbench validate-output reports/public_medium/<run_id>
```

The row shapes are expected to remain valid under the `1.0.0` output contract.

| Suite | Run ID | Per-stratum rows | Benchmark uncertainty rows | Disagreement rows | Failure rows | Leaderboard rows | Suite-specific rows |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `public_medium_canonical_ground_truth` | `12eda89e-8c35-481b-9746-2350273abedb` | 459 | 170 | 363 | 128 | 5 | 0 sensitivity |
| `public_medium_stress_contamination` | `054d5baa-0b98-4fb8-9ce1-a27c8691c0f8` | 2631 | 880 | 1575 | 616 | 4 | 1872 stress |
| `public_medium_null_false_positive` | `d2d92952-a246-4965-9ab2-67c66a855516` | 167 | 32 | 371 | 44 | 4 | 0 sensitivity |
| `public_medium_sensitivity_disagreement` | `1cd2ceb3-d970-4d35-8583-f1cb22421008` | 616 | 105 | 925 | 294 | 9 | 150 sensitivity |

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
