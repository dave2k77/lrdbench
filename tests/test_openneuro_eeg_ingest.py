from __future__ import annotations

import csv
from pathlib import Path

import numpy as np
import pytest
from scipy.io import savemat

from lrdbench.openneuro_eeg import EeglabRecording, convert_eeglab_subject_to_csv_records


def _write_minimal_eeglab_set(path: Path) -> None:
    dtype = np.dtype([("labels", "O")])
    chanlocs = np.empty((3,), dtype=dtype)
    chanlocs[0]["labels"] = "E1"
    chanlocs[1]["labels"] = "E2"
    chanlocs[2]["labels"] = "E3"
    data = np.vstack(
        [
            np.arange(1000, dtype=np.float32),
            np.arange(1000, dtype=np.float32) + 1000.0,
            np.arange(1000, dtype=np.float32) + 2000.0,
        ]
    )
    savemat(
        path,
        {
            "nbchan": 3,
            "pnts": 1000,
            "trials": 1,
            "srate": 100.0,
            "data": data,
            "chanlocs": chanlocs,
            "task": "synthetic-task",
        },
    )


def test_convert_eeglab_subject_writes_windowed_csv_records_and_manifest_blocks(
    tmp_path: Path,
) -> None:
    eeg_path = tmp_path / "sub-001_task-demo_eeg.set"
    _write_minimal_eeglab_set(eeg_path)
    output_dir = tmp_path / "csv"

    blocks = convert_eeglab_subject_to_csv_records(
        eeg_path=eeg_path,
        output_dir=output_dir,
        dataset_id="ds-test",
        dataset_version="1.0.0",
        subject="sub-001",
        task="demo",
        channels=("E1", "E3"),
        window_seconds=2.0,
        max_windows=2,
    )

    assert [block["record_id"] for block in blocks] == [
        "ds-test_sub-001_task-demo_E1_seg-0001",
        "ds-test_sub-001_task-demo_E1_seg-0002",
        "ds-test_sub-001_task-demo_E3_seg-0001",
        "ds-test_sub-001_task-demo_E3_seg-0002",
    ]
    assert all(block["value_column"] == "value" for block in blocks)
    assert all(block["time_column"] == "time_seconds" for block in blocks)
    assert all(block["sampling_rate"] == 100.0 for block in blocks)
    assert all(block["missing_policy"] == "error" for block in blocks)
    assert blocks[0]["metadata"] == {
        "dataset": "ds-test",
        "dataset_version": "1.0.0",
        "subject": "sub-001",
        "session": "n/a",
        "task": "demo",
        "channel": "E1",
        "condition": "continuous_window",
        "segment_id": "seg-0001",
        "window_start_seconds": 0.0,
        "window_duration_seconds": 2.0,
        "preprocessing": "openneuro_raw_eeglab_export_demeaned_per_window",
        "source_format": "eeglab_set",
    }

    csv_path = tmp_path / blocks[0]["path"]
    assert csv_path.is_file()
    with csv_path.open(newline="") as f:
        rows = list(csv.DictReader(f))
    assert rows[0] == {"time_seconds": "0.0", "value": "-99.5"}
    assert rows[-1] == {"time_seconds": "1.99", "value": "99.5"}


def test_eeglab_recording_rejects_missing_channels(tmp_path: Path) -> None:
    eeg_path = tmp_path / "sub-001_task-demo_eeg.set"
    _write_minimal_eeglab_set(eeg_path)

    recording = EeglabRecording.from_set_file(eeg_path)

    with pytest.raises(ValueError, match="channels not found"):
        recording.channel_indices(("E1", "Cz"))
