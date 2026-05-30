# OpenNeuro ds002691 EEG Observational Pilot Results

This directory contains compact, tracked CSV summaries from a clean observational-mode pilot run using a small subset of the CC0 OpenNeuro ds002691 EEG dataset.

The full row-level report is intentionally not tracked because `reports/` is ignored. Re-run the manifest to regenerate it locally.

## Dataset

- OpenNeuro: `ds002691`
- Name: Internal attention study
- DOI: `10.18112/openneuro.ds002691.v1.1.0`
- License: CC0
- Source URL: https://openneuro.org/datasets/ds002691/versions/1.1.0

## Run

| Run | Mode | Run ID | Manifest |
| --- | --- | --- | --- |
| OpenNeuro ds002691 EEG pilot | `observational` | `3762d43d-5610-4ce2-a931-bf11aac9317a` | `openneuro_ds002691_pilot_v1` |

Manifest:

`configs/suites/openneuro_ds002691_pilot.yaml`

Local full report:

`reports/openneuro_ds002691_pilot/3762d43d-5610-4ce2-a931-bf11aac9317a`

HTML report:

`reports/openneuro_ds002691_pilot/3762d43d-5610-4ce2-a931-bf11aac9317a/html/report.html`

## Pilot subset

- Subjects: 4 (`sub-001` to `sub-004`)
- Channels: 4 (`E1`, `E8`, `E16`, `E24`)
- Records: 16 truth-free observational records
- Samples per record: 2500
- Sampling rate: 250 Hz
- Window duration: 10 seconds
- Preprocessing: per-window demeaning only

## Interpretation boundary

These summaries demonstrate observational-mode ingestion and estimator/report generation on real open EEG. They do not establish estimator accuracy or empirical CI coverage because no benchmark truth is available for these EEG windows.
