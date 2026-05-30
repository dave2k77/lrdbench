from __future__ import annotations

import csv
import json
import urllib.request
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import yaml
from scipy.io import loadmat

OPENNEURO_S3_BASE = "https://s3.amazonaws.com/openneuro.org"
DEFAULT_DS002691_SUBJECTS = ("sub-001", "sub-002", "sub-003", "sub-004")
DEFAULT_DS002691_CHANNELS = ("E1", "E8", "E16", "E24")


@dataclass(frozen=True)
class EeglabRecording:
    data: np.ndarray
    sampling_rate: float
    channel_labels: tuple[str, ...]

    @classmethod
    def from_set_file(cls, path: str | Path) -> EeglabRecording:
        mat = loadmat(path, squeeze_me=True, struct_as_record=False)
        container = mat.get("EEG")
        if container is not None:
            data = container.data
            sampling_rate = float(container.srate)
            chanlocs = container.chanlocs
        else:
            data = mat["data"]
            sampling_rate = float(mat["srate"])
            chanlocs = mat["chanlocs"]
        if isinstance(data, str):
            raise ValueError(
                f"EEGLAB .set file {path} points to external data file {data!r}; "
                "embedded numeric data are required for this lightweight importer"
            )
        arr = np.asarray(data, dtype=float)
        if arr.ndim != 2:
            raise ValueError(f"EEGLAB data in {path} must be a 2-D channels x samples array")
        labels = _channel_labels(chanlocs, expected_channels=arr.shape[0])
        return cls(data=arr, sampling_rate=sampling_rate, channel_labels=labels)

    def channel_indices(self, channels: Sequence[str]) -> dict[str, int]:
        label_to_idx = {label: i for i, label in enumerate(self.channel_labels)}
        missing = [channel for channel in channels if channel not in label_to_idx]
        if missing:
            raise ValueError(
                "channels not found in EEGLAB recording: "
                f"{missing}; available channels include {self.channel_labels[:10]}"
            )
        return {channel: label_to_idx[channel] for channel in channels}


def _channel_labels(chanlocs: Any, *, expected_channels: int) -> tuple[str, ...]:
    labels: list[str] = []
    for i, item in enumerate(np.atleast_1d(chanlocs)):
        label = None
        if hasattr(item, "labels"):
            label = item.labels
        elif getattr(item, "dtype", None) is not None and "labels" in item.dtype.names:
            label = item["labels"]
        if isinstance(label, np.ndarray):
            label = label.item() if label.shape == () else label.reshape(-1)[0]
        labels.append(str(label) if label is not None else f"ch{i + 1}")
    if len(labels) != expected_channels:
        return tuple(f"ch{i + 1}" for i in range(expected_channels))
    return tuple(labels)


def convert_eeglab_subject_to_csv_records(
    *,
    eeg_path: str | Path,
    output_dir: str | Path,
    dataset_id: str,
    dataset_version: str,
    subject: str,
    task: str,
    channels: Sequence[str],
    window_seconds: float,
    max_windows: int,
    session: str = "n/a",
    condition: str = "continuous_window",
    preprocessing: str = "openneuro_raw_eeglab_export_demeaned_per_window",
) -> list[dict[str, Any]]:
    recording = EeglabRecording.from_set_file(eeg_path)
    channel_indices = recording.channel_indices(channels)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    window_samples = int(round(window_seconds * recording.sampling_rate))
    if window_samples < 2:
        raise ValueError("window_seconds must produce at least two samples")
    available_windows = recording.data.shape[1] // window_samples
    n_windows = min(max_windows, available_windows)
    if n_windows < 1:
        raise ValueError(
            f"recording has {recording.data.shape[1]} samples, not enough for a "
            f"{window_seconds}-second window at {recording.sampling_rate} Hz"
        )

    blocks: list[dict[str, Any]] = []
    for channel in channels:
        channel_idx = channel_indices[channel]
        for window_idx in range(n_windows):
            start = window_idx * window_samples
            end = start + window_samples
            values = recording.data[channel_idx, start:end].astype(float, copy=True)
            values = values - float(np.mean(values))
            segment_id = f"seg-{window_idx + 1:04d}"
            record_id = f"{dataset_id}_{subject}_task-{task}_{channel}_{segment_id}"
            csv_name = f"{record_id}.csv"
            csv_path = output_dir / csv_name
            _write_series_csv(csv_path, values, recording.sampling_rate, start_sample=start)
            blocks.append(
                {
                    "record_id": record_id,
                    "path": str(csv_path.as_posix()),
                    "value_column": "value",
                    "time_column": "time_seconds",
                    "sampling_rate": float(recording.sampling_rate),
                    "missing_policy": "error",
                    "metadata": {
                        "dataset": dataset_id,
                        "dataset_version": dataset_version,
                        "subject": subject,
                        "session": session,
                        "task": task,
                        "channel": channel,
                        "condition": condition,
                        "segment_id": segment_id,
                        "window_start_seconds": float(start / recording.sampling_rate),
                        "window_duration_seconds": float(window_seconds),
                        "preprocessing": preprocessing,
                        "source_format": "eeglab_set",
                    },
                }
            )
    return blocks


def _write_series_csv(
    path: Path, values: np.ndarray, sampling_rate: float, *, start_sample: int) -> None:
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=("time_seconds", "value"))
        writer.writeheader()
        for i, value in enumerate(values):
            writer.writerow(
                {
                    "time_seconds": float((start_sample + i) / sampling_rate),
                    "value": float(value),
                }
            )


def download_openneuro_file(dataset_id: str, relative_path: str, destination: Path) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.is_file() and destination.stat().st_size > 0:
        return destination
    url = f"{OPENNEURO_S3_BASE}/{dataset_id}/{relative_path}"
    urllib.request.urlretrieve(url, destination)  # noqa: S310
    return destination


def prepare_ds002691_pilot(
    *,
    output_root: str | Path = "configs/suites/data/openneuro_ds002691_pilot",
    subjects: Sequence[str] = DEFAULT_DS002691_SUBJECTS,
    channels: Sequence[str] = DEFAULT_DS002691_CHANNELS,
    window_seconds: float = 60.0,
    max_windows: int = 1,
    dataset_version: str = "1.1.0",
) -> list[dict[str, Any]]:
    output_root = Path(output_root)
    raw_dir = output_root / "raw"
    csv_dir = output_root / "csv"
    blocks: list[dict[str, Any]] = []
    for subject in subjects:
        rel_base = f"{subject}/eeg/{subject}_task-internalattention"
        set_path = download_openneuro_file(
            "ds002691", f"{rel_base}_eeg.set", raw_dir / f"{subject}_task-internalattention_eeg.set"
        )
        download_openneuro_file(
            "ds002691", f"{rel_base}_eeg.json", raw_dir / f"{subject}_task-internalattention_eeg.json"
        )
        download_openneuro_file(
            "ds002691",
            f"{rel_base}_channels.tsv",
            raw_dir / f"{subject}_task-internalattention_channels.tsv",
        )
        blocks.extend(
            convert_eeglab_subject_to_csv_records(
                eeg_path=set_path,
                output_dir=csv_dir,
                dataset_id="openneuro_ds002691",
                dataset_version=dataset_version,
                subject=subject,
                task="internalattention",
                channels=channels,
                window_seconds=window_seconds,
                max_windows=max_windows,
            )
        )
    # Keep paths manifest-relative to configs/suites.
    for block in blocks:
        block["path"] = str(Path(block["path"]).as_posix()).replace("configs/suites/", "")
    return blocks


def write_ds002691_manifest(blocks: Sequence[dict[str, Any]], path: str | Path) -> Path:
    manifest = {
        "manifest_id": "openneuro_ds002691_pilot_v1",
        "name": "openneuro_ds002691_pilot",
        "description": "CC0 OpenNeuro ds002691 EEG observational-mode pilot for truth-free manuscript benchmarking.",
        "mode": "observational",
        "source": {"type": "csv_series_index", "series": list(blocks)},
        "estimators": _pilot_estimators(),
        "metrics": [
            "validity_rate",
            "runtime",
            "cross_estimator_dispersion",
            "pairwise_estimator_disagreement",
            "family_level_disagreement",
            "parameter_variant_sensitivity",
            "max_variant_drift",
            {"name": "ci_width", "levels": [0.95]},
            "instability",
            "preprocessing_sensitivity",
        ],
        "preprocessing": {"sensitivity_eps": 1.0e-4},
        "leaderboards": [
            {
                "name": "openneuro_ds002691_observational_stability",
                "mode": "observational",
                "component_metrics": [
                    "instability",
                    "validity_rate",
                    "runtime",
                    "max_variant_drift",
                ],
                "weights": {
                    "instability": 0.35,
                    "validity_rate": 0.30,
                    "runtime": 0.20,
                    "max_variant_drift": 0.15,
                },
                "ranking_rule": "weighted_rank",
                "tie_break_rule": "best_primary_metric",
            }
        ],
        "seeds": {"global_seed": 20260530},
        "report": {
            "formats": ["html", "csv"],
            "export_root": "reports/openneuro_ds002691_pilot",
        },
        "execution": {
            "max_workers": 4,
            "estimate_cache_dir": ".lrdbench_cache/openneuro_ds002691_pilot",
            "cache_read": True,
            "cache_write": True,
        },
    }
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")
    return path


def _pilot_estimators() -> list[dict[str, Any]]:
    return [
        {
            "name": "RS",
            "family": "temporal",
            "target_estimand": "hurst_scaling_proxy",
            "supports_ci": True,
            "supports_diagnostics": True,
            "params": {"n_bootstrap": 32, "bootstrap_block_len": 64, "ci_levels": [0.95]},
        },
        {
            "name": "DFA",
            "family": "temporal",
            "target_estimand": "hurst_scaling_proxy",
            "supports_ci": False,
            "supports_diagnostics": True,
            "params": {"detrend_order": 1},
            "variants": [
                {"name": "short_scales", "params": {"min_scale": 16, "max_scale": 256}},
                {"name": "balanced_scales", "params": {"min_scale": 32, "max_scale": 512}},
            ],
        },
        {
            "name": "DMA",
            "family": "temporal",
            "target_estimand": "hurst_scaling_proxy",
            "supports_ci": False,
            "supports_diagnostics": True,
            "variants": [
                {"name": "short_windows", "params": {"min_scale": 16, "max_scale": 256}},
                {"name": "balanced_windows", "params": {"min_scale": 32, "max_scale": 512}},
            ],
        },
        {
            "name": "AbsoluteMoment",
            "family": "temporal",
            "target_estimand": "hurst_scaling_proxy",
            "supports_ci": False,
            "supports_diagnostics": True,
            "params": {"min_scale": 16, "max_scale": 512},
        },
        {
            "name": "Variance",
            "family": "temporal",
            "target_estimand": "hurst_scaling_proxy",
            "supports_ci": False,
            "supports_diagnostics": True,
            "params": {"min_scale": 16, "max_scale": 512},
        },
        {
            "name": "VarianceResidual",
            "family": "temporal",
            "target_estimand": "hurst_scaling_proxy",
            "supports_ci": False,
            "supports_diagnostics": True,
            "params": {"min_scale": 16, "max_scale": 512, "detrend_order": 1},
        },
        {
            "name": "GHE",
            "family": "geometric",
            "target_estimand": "hurst_scaling_proxy",
            "supports_ci": False,
            "supports_diagnostics": True,
            "params": {"n_scales": 16},
        },
        {
            "name": "Higuchi",
            "family": "geometric",
            "target_estimand": "hurst_scaling_proxy",
            "supports_ci": False,
            "supports_diagnostics": True,
            "params": {"k_max": 32},
        },
        {
            "name": "WaveletOLS",
            "family": "wavelet",
            "target_estimand": "hurst_scaling_proxy",
            "supports_ci": False,
            "supports_diagnostics": True,
            "variants": [
                {
                    "name": "broad_band",
                    "params": {"wavelet": "db2", "j_drop_low": 1, "j_drop_high": 1},
                },
                {
                    "name": "conservative_band",
                    "params": {"wavelet": "db4", "j_drop_low": 1, "j_drop_high": 2},
                },
            ],
        },
    ]


def write_dataset_citation(output_root: str | Path) -> Path:
    output_root = Path(output_root)
    citation = {
        "dataset": "OpenNeuro ds002691",
        "name": "Internal attention study",
        "doi": "10.18112/openneuro.ds002691.v1.1.0",
        "license": "CC0",
        "authors": ["Arnaud Delorme", "Dean Radin"],
        "source_url": "https://openneuro.org/datasets/ds002691/versions/1.1.0",
        "pilot_use": "truth-free observational-mode EEG benchmark pilot",
    }
    path = output_root / "dataset_citation.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(citation, indent=2) + "\n", encoding="utf-8")
    return path
