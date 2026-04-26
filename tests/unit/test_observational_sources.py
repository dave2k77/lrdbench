from __future__ import annotations

from pathlib import Path

import pytest

from lrdbench.enums import BenchmarkMode, SourceType
from lrdbench.observational_sources import load_observational_records
from lrdbench.schema import BenchmarkManifest


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
