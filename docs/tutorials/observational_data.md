# Observational Data

Observational mode is for real or user-provided time series where benchmark truth is not available.
It does not report truth-based accuracy metrics. Instead, it focuses on stability, validity,
runtime, preprocessing sensitivity, uncertainty width, and failure patterns.

## Run the packaged CSV example

```bash
lrdbench validate configs/suites/smoke_observational.yaml
lrdbench run configs/suites/smoke_observational.yaml
```

Or:

```bash
python examples/quickstart_observational.py
```

The manifest reads `configs/suites/data/smoke_series.csv` through `source.type:
csv_series_index`.

## Generate a local CSV example

For a self-contained example that creates both a CSV file and an observational manifest, run:

```bash
python examples/custom_csv_data.py
```

The script writes `data/example_series.csv`, writes `custom_csv_observational.yaml`, runs the
benchmark, and prints the result store, HTML report, and output validation command.

## Point a manifest at your own CSV

Copy the observational smoke manifest and replace the `series` entry:

```yaml
mode: observational
source:
  type: csv_series_index
  series:
    - record_id: participant_001_segment_a
      path: data/my_series.csv
      value_column: value
```

Paths are resolved relative to the manifest file. Keep one numeric value column per listed series.
Use stable `record_id` values so reports and downstream analyses can be joined back to your study
metadata.

## Choose metrics

Truth-based metrics such as `bias`, `mae`, `rmse`, and empirical `coverage` require benchmark truth
and are not appropriate for observational mode. Typical observational metrics include:

- `validity_rate`;
- `runtime`;
- `ci_width`;
- `instability`;
- `preprocessing_sensitivity`.

## Interpret the output

Observational leaderboards are stability summaries, not accuracy rankings. A stable estimator may
still be estimating an inappropriate quantity for a given signal. Report the estimator assumptions,
preprocessing, sampling context, segmentation rules, and any failure concentration alongside the
numeric outputs.
