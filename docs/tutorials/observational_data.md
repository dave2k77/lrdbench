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

## Run the neural-like observational fixture

For a stronger workflow rehearsal, run the multi-record fixture:

```bash
PYTHONPATH=src .venv/Scripts/python.exe -m lrdbench.cli.main validate configs/suites/neural_observational_fixture.yaml
PYTHONPATH=src .venv/Scripts/python.exe -m lrdbench.cli.main run configs/suites/neural_observational_fixture.yaml --no-plugins
```

This fixture contains eight non-sensitive CSV records across two subjects, two channels, and two
conditions. It exercises time columns, sampling rates, metadata strata, source hashes, QC summaries,
classical estimator variants, disagreement metrics, and scale/window sensitivity. It has no benchmark
truth and should be interpreted only as a truth-free observational workflow rehearsal.

## Run the OpenNeuro ds002691 EEG pilot

The repository also includes a small real-data observational pilot derived from the CC0 OpenNeuro
`ds002691` internal-attention EEG dataset:

```bash
PYTHONPATH=src .venv/Scripts/python.exe -m lrdbench.cli.main validate configs/suites/openneuro_ds002691_pilot.yaml
PYTHONPATH=src .venv/Scripts/python.exe -m lrdbench.cli.main run configs/suites/openneuro_ds002691_pilot.yaml --no-plugins
```

The committed pilot CSVs contain four subjects (`sub-001` to `sub-004`), four EEG channels (`E1`,
`E8`, `E16`, `E24`), and one 10-second demeaned continuous window per subject/channel pair. The
manifest preserves the OpenNeuro accession, DOI, license, subject, channel, task, segment ID, sampling
rate, preprocessing, and raw-source SHA-256 metadata. Compact summaries from the validated run live in
`benchmark_experiment/results/openneuro_ds002691_pilot/`.

As with all observational-mode runs, this pilot has no benchmark truth. Use it to demonstrate real EEG
ingestion, QC/source metadata, estimator validity/runtime/CI-width/disagreement summaries, and
scale/window sensitivity. Do not use it to claim estimator accuracy or empirical coverage.

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

### Optional time, sampling, metadata, and missing-data fields

CSV-backed observational entries may also include a numeric time column, sampling rate, study
metadata, and an explicit missing-data policy:

```yaml
source:
  type: csv_series_index
  series:
    - record_id: sub-01_ses-01_Cz_rest_seg-0001
      path: data/neural/sub-01_ses-01_Cz_rest_seg-0001.csv
      value_column: value
      time_column: time_seconds
      sampling_rate: 1000.0
      missing_policy: drop
      metadata:
        subject: sub-01
        session: ses-01
        channel: Cz
        condition: rest
        segment_id: seg-0001
```

Supported `missing_policy` values are:

- `drop` (default): drop rows where the value or declared time column is missing or non-finite;
- `error`: reject the record if any value or declared time entry is missing or non-finite.

The loader preserves `time_column` as `SeriesRecord.time_axis`, stores `sampling_rate`, attaches the
metadata to record annotations, and records a SHA-256 hash of each source CSV in
`annotations.source_sha256`. Common metadata keys such as `subject`, `session`, `channel`,
`condition`, and `segment_id` are also available as strata for observational summaries.

Each CSV-backed record also receives a lightweight QC summary in `annotations.qc`, and the same
fields are flattened into `raw/records.csv` with a `qc_` prefix. The current QC summary includes:

- original, retained, and missing sample counts;
- missing fraction after applying the declared missing-data policy;
- time start, time end, and duration when a time column is supplied;
- retained-value minimum, maximum, mean, and standard deviation.

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
