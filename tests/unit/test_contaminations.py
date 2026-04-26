from __future__ import annotations

import numpy as np

from lrdbench.contaminations._common import contamination_severity_label
from lrdbench.contaminations.heavy_tail import HeavyTailNoiseContamination
from lrdbench.contaminations.level_shift import LevelShiftContamination
from lrdbench.contaminations.outliers import OutliersContamination
from lrdbench.contaminations.polynomial import PolynomialTrendContamination
from lrdbench.enums import SourceType
from lrdbench.schema import SeriesRecord


def _record(values: np.ndarray) -> SeriesRecord:
    return SeriesRecord(
        record_id="clean",
        values=values,
        time_axis=None,
        sampling_rate=None,
        source_type=SourceType.SYNTHETIC,
        source_name="synthetic",
        annotations={"process_family": "test", "pair_group_id": "pair-1"},
    )


def _assert_contamination_metadata(out: SeriesRecord, *, name: str, family: str) -> None:
    assert out.source_type is SourceType.CONTAMINATED
    assert out.source_name == f"contaminated:{name}"
    assert out.annotations["stress_role"] == "contaminated"
    assert out.annotations["pair_group_id"] == "pair-1"
    assert out.annotations["clean_record_id"] == "clean"
    assert out.annotations["contamination_operator"] == name
    assert out.annotations["contamination_family"] == family
    assert len(out.contamination_history) == 1
    assert out.contamination_history[0].name == name
    assert out.contamination_history[0].family == family


def test_contamination_severity_label_is_stable_and_allows_override() -> None:
    assert contamination_severity_label("outliers", {"amplitude": 5.0, "rate": 0.02}) == (
        "amplitude=5.0;rate=0.02"
    )
    assert contamination_severity_label("level_shift", {"severity": "negative_control"}) == (
        "negative_control"
    )
    assert contamination_severity_label("noop", {}) == "default"


def test_level_shift_adds_constant_std_scaled_offset_and_metadata() -> None:
    rec = _record(np.linspace(-2.0, 2.0, 64))
    out = LevelShiftContamination().apply(
        rec,
        params={"shift": 0.75},
        seed=123,
        manifest_id="m",
        new_record_id="shifted",
    )

    diff = out.values - rec.values
    np.testing.assert_allclose(diff, np.full(rec.values.size, 0.75 * np.std(rec.values)))
    _assert_contamination_metadata(out, name="level_shift", family="level")
    assert out.contamination_history[0].severity == "shift=0.75"


def test_outliers_changes_expected_number_of_points_deterministically() -> None:
    rec = _record(np.linspace(-1.0, 1.0, 100))
    op = OutliersContamination()

    a = op.apply(
        rec,
        params={"rate": 0.07, "amplitude": 4.0},
        seed=123,
        manifest_id="m",
        new_record_id="outliers_a",
    )
    b = op.apply(
        rec,
        params={"rate": 0.07, "amplitude": 4.0},
        seed=123,
        manifest_id="m",
        new_record_id="outliers_b",
    )

    np.testing.assert_allclose(a.values, b.values)
    assert int(np.count_nonzero(np.abs(a.values - rec.values) > 1e-12)) == 7
    _assert_contamination_metadata(a, name="outliers", family="impulsive")


def test_polynomial_trend_adds_centered_trend_component() -> None:
    rec = _record(np.sin(np.linspace(0.0, 4.0 * np.pi, 128)))
    out = PolynomialTrendContamination().apply(
        rec,
        params={"order": 2, "strength": 0.8},
        seed=123,
        manifest_id="m",
        new_record_id="trend",
    )

    diff = out.values - rec.values
    t = np.linspace(-1.0, 1.0, rec.values.size)
    expected_shape = t + t**2
    expected_shape = expected_shape - float(np.mean(expected_shape))
    assert abs(float(np.mean(diff))) < 1e-12
    assert float(np.corrcoef(diff, expected_shape)[0, 1]) > 0.99
    _assert_contamination_metadata(out, name="polynomial_trend", family="trend")


def test_heavy_tail_noise_adds_scaled_finite_noise_with_alpha_alias() -> None:
    rec = _record(np.sin(np.linspace(0.0, 8.0 * np.pi, 512)))
    out = HeavyTailNoiseContamination().apply(
        rec,
        params={"alpha": 3.0, "scale": 0.5},
        seed=123,
        manifest_id="m",
        new_record_id="heavy",
    )

    residual = out.values - rec.values
    assert np.isfinite(out.values).all()
    assert 0.45 * float(np.std(rec.values)) < float(np.std(residual)) < 0.55 * float(
        np.std(rec.values)
    )
    _assert_contamination_metadata(out, name="heavy_tail_noise", family="heavy_tail")
