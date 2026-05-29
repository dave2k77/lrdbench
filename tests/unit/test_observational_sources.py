from __future__ import annotations

import hashlib
from pathlib import Path

import pandas as pd
import pytest

from lrdbench.enums import BenchmarkMode, SourceType
from lrdbench.observational_sources import load_observational_records
from lrdbench.result_store import CsvResultStore
from lrdbench.schema import BenchmarkManifest
from lrdbench.strata import stratum_from_record


def _manifest(source: dict[str, object]) -> BenchmarkManifest:
    return BenchmarkManifest(
        manifest_id="obs_unit",
        name="observational unit",
        mode=BenchmarkMode.OBSERVATIONAL,
        source_spec=source,
    )


def test_inline_table_records_have_no_truth_and_stable_seed() -> None:
    manifest = _manifest(
        {
            "type": "inline_table",
            "series": [{"record_id": "inline_a", "values": [1.0, 2.0, 3.0]}],
        }
    )

    first = load_observational_records(manifest, base_dir=Path("."), global_seed=11)
    second = load_observational_records(manifest, base_dir=Path("."), global_seed=11)

    assert len(first) == 1
    rec = first[0]
    assert rec.record_id == "inline_a"
    assert rec.source_type is SourceType.OBSERVATIONAL
    assert rec.truth is None
    assert rec.annotations["source_kind"] == "inline_table"
    assert rec.provenance is not None
    assert rec.provenance.seed == second[0].provenance.seed


def test_inline_table_rejects_single_sample_series() -> None:
    manifest = _manifest(
        {
            "type": "inline_table",
            "series": [{"record_id": "too_short", "values": [1.0]}],
        }
    )

    with pytest.raises(ValueError, match="at least two samples"):
        load_observational_records(manifest, base_dir=Path("."), global_seed=1)


def test_csv_series_index_loads_relative_path_and_drops_missing_values(tmp_path: Path) -> None:
    csv_path = tmp_path / "series.csv"
    csv_path.write_text("value,ignored\n1.0,a\n,b\n3.5,c\n", encoding="utf-8")
    manifest = _manifest(
        {
            "type": "csv_series_index",
            "series": [{"path": "series.csv", "record_id": "csv_a", "value_column": "value"}],
        }
    )

    records = load_observational_records(manifest, base_dir=tmp_path, global_seed=17)

    assert len(records) == 1
    rec = records[0]
    assert rec.record_id == "csv_a"
    assert rec.values.tolist() == [1.0, 3.5]
    assert rec.source_name == "series.csv"
    assert rec.annotations["source_kind"] == "csv_series_index"
    assert rec.annotations["value_column"] == "value"
    assert rec.provenance is not None
    assert rec.provenance.source_version.endswith("series.csv")


def test_csv_series_index_accepts_absolute_path(tmp_path: Path) -> None:
    csv_path = tmp_path / "absolute.csv"
    csv_path.write_text("value\n2.0\n4.0\n", encoding="utf-8")
    manifest = _manifest(
        {
            "type": "csv_series_index",
            "series": [{"path": str(csv_path)}],
        }
    )

    records = load_observational_records(manifest, base_dir=Path("/unused"), global_seed=3)

    assert records[0].record_id == "absolute"
    assert records[0].values.tolist() == [2.0, 4.0]


def test_csv_series_index_loads_time_axis_sampling_rate_metadata_and_file_hash(
    tmp_path: Path,
) -> None:
    csv_path = tmp_path / "rich.csv"
    csv_text = "time,value\n0.0,1.0\n0.1,\n0.2,3.0\n0.3,4.0\n"
    csv_path.write_text(csv_text, encoding="utf-8")
    manifest = _manifest(
        {
            "type": "csv_series_index",
            "series": [
                {
                    "path": "rich.csv",
                    "record_id": "rich_a",
                    "value_column": "value",
                    "time_column": "time",
                    "sampling_rate": 10.0,
                    "metadata": {
                        "subject": "sub-01",
                        "session": "ses-01",
                        "channel": "Cz",
                        "condition": "rest",
                    },
                }
            ],
        }
    )

    records = load_observational_records(manifest, base_dir=tmp_path, global_seed=17)

    rec = records[0]
    assert rec.values.tolist() == [1.0, 3.0, 4.0]
    assert rec.time_axis is not None
    assert rec.time_axis.tolist() == [0.0, 0.2, 0.3]
    assert rec.sampling_rate == 10.0
    assert rec.annotations["time_column"] == "time"
    assert rec.annotations["missing_policy"] == "drop"
    assert rec.annotations["metadata"] == {
        "subject": "sub-01",
        "session": "ses-01",
        "channel": "Cz",
        "condition": "rest",
    }
    assert rec.annotations["subject"] == "sub-01"
    assert rec.annotations["condition"] == "rest"
    assert rec.annotations["source_sha256"] == hashlib.sha256(
        csv_path.read_bytes()
    ).hexdigest()
    stratum = dict(stratum_from_record(rec))
    assert stratum["subject"] == "sub-01"
    assert stratum["session"] == "ses-01"
    assert stratum["channel"] == "Cz"
    assert stratum["condition"] == "rest"
    assert rec.annotations["qc"] == {
        "original_sample_count": 4,
        "retained_sample_count": 3,
        "missing_sample_count": 1,
        "missing_fraction": 0.25,
        "duration": 0.3,
        "time_start": 0.0,
        "time_end": 0.3,
        "value_min": 1.0,
        "value_max": 4.0,
        "value_mean": pytest.approx(8.0 / 3.0),
        "value_std": pytest.approx(1.247219128924647),
    }


def test_csv_result_store_exports_observational_qc_columns(tmp_path: Path) -> None:
    csv_path = tmp_path / "rich.csv"
    csv_path.write_text("time,value\n0.0,1.0\n0.1,\n0.2,3.0\n0.3,4.0\n", encoding="utf-8")
    manifest = _manifest(
        {
            "type": "csv_series_index",
            "series": [
                {
                    "path": "rich.csv",
                    "record_id": "rich_a",
                    "value_column": "value",
                    "time_column": "time",
                    "sampling_rate": 10.0,
                    "metadata": {"subject": "sub-01"},
                }
            ],
        }
    )
    records = load_observational_records(manifest, base_dir=tmp_path, global_seed=17)
    store = CsvResultStore(tmp_path / "results")

    store.write_records(records)
    store.finalise()

    rows = pd.read_csv(tmp_path / "results" / "raw" / "records.csv")
    row = rows.iloc[0]
    assert row["qc_original_sample_count"] == 4
    assert row["qc_retained_sample_count"] == 3
    assert row["qc_missing_sample_count"] == 1
    assert row["qc_missing_fraction"] == 0.25
    assert row["qc_duration"] == 0.3
    assert row["qc_value_min"] == 1.0
    assert row["qc_value_max"] == 4.0
    assert row["source_sha256"] == records[0].annotations["source_sha256"]


def test_csv_series_index_missing_policy_error_rejects_missing_values(
    tmp_path: Path,
) -> None:
    csv_path = tmp_path / "missing.csv"
    csv_path.write_text("time,value\n0.0,1.0\n0.1,\n", encoding="utf-8")
    manifest = _manifest(
        {
            "type": "csv_series_index",
            "series": [
                {
                    "path": "missing.csv",
                    "record_id": "missing_error",
                    "value_column": "value",
                    "time_column": "time",
                    "missing_policy": "error",
                }
            ],
        }
    )

    with pytest.raises(ValueError, match="missing_policy='error'"):
        load_observational_records(manifest, base_dir=tmp_path, global_seed=17)


def test_csv_series_index_rejects_unknown_missing_policy(tmp_path: Path) -> None:
    csv_path = tmp_path / "unknown_policy.csv"
    csv_path.write_text("value\n1.0\n2.0\n", encoding="utf-8")
    manifest = _manifest(
        {
            "type": "csv_series_index",
            "series": [
                {
                    "path": "unknown_policy.csv",
                    "record_id": "unknown_policy",
                    "missing_policy": "ignore",
                }
            ],
        }
    )

    with pytest.raises(ValueError, match="unknown missing_policy"):
        load_observational_records(manifest, base_dir=tmp_path, global_seed=17)


def test_csv_series_index_rejects_missing_time_column(tmp_path: Path) -> None:
    csv_path = tmp_path / "missing_time_column.csv"
    csv_path.write_text("value\n1.0\n2.0\n", encoding="utf-8")
    manifest = _manifest(
        {
            "type": "csv_series_index",
            "series": [
                {
                    "path": "missing_time_column.csv",
                    "record_id": "missing_time_column",
                    "time_column": "time",
                }
            ],
        }
    )

    with pytest.raises(ValueError, match="missing required column"):
        load_observational_records(manifest, base_dir=tmp_path, global_seed=17)


def test_csv_series_index_rejects_missing_file(tmp_path: Path) -> None:
    manifest = _manifest(
        {
            "type": "csv_series_index",
            "series": [{"path": "missing.csv", "record_id": "missing"}],
        }
    )

    with pytest.raises(FileNotFoundError, match="observational series file not found"):
        load_observational_records(manifest, base_dir=tmp_path, global_seed=1)


def test_csv_series_index_rejects_too_few_finite_values(tmp_path: Path) -> None:
    csv_path = tmp_path / "too_short.csv"
    csv_path.write_text("value\n1.0\n\n", encoding="utf-8")
    manifest = _manifest(
        {
            "type": "csv_series_index",
            "series": [{"path": "too_short.csv", "record_id": "too_short"}],
        }
    )

    with pytest.raises(ValueError, match="at least two finite samples"):
        load_observational_records(manifest, base_dir=tmp_path, global_seed=1)


def test_unknown_observational_source_type_is_rejected() -> None:
    manifest = _manifest({"type": "unknown", "series": []})

    with pytest.raises(ValueError, match="unknown observational source.type"):
        load_observational_records(manifest, base_dir=Path("."), global_seed=1)
