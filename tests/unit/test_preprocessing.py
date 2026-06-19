from __future__ import annotations

import numpy as np

from lrdbench.enums import SourceType
from lrdbench.generators.nonstationary_lrd import NonstationaryLRDGenerator
from lrdbench.preprocessing import OracleGainPreprocessing, RollingZScorePreprocessing
from lrdbench.runner import _expand_preprocessing_grid


def test_expand_preprocessing_grid_cartesian() -> None:
    spec = {
        "operators": [
            {
                "name": "rolling_zscore",
                "params": {"window": [32, 64], "center": True},
            },
            {"name": "oracle_gain", "params": {}},
        ],
    }

    out = _expand_preprocessing_grid(spec)

    assert out == [
        ("rolling_zscore", {"window": 32, "center": True}),
        ("rolling_zscore", {"window": 64, "center": True}),
        ("oracle_gain", {}),
    ]


def test_rolling_zscore_preprocessing_records_history() -> None:
    gen = NonstationaryLRDGenerator()
    rec = gen.generate(
        record_id="raw",
        params={"case": "lrd_randomwalk_gain", "H": 0.7, "n": 256},
        seed=123,
        manifest_id="m",
    )

    out = RollingZScorePreprocessing().apply(
        rec,
        params={"window": 64},
        seed=1,
        manifest_id="m",
        new_record_id="corrected",
    )

    assert out.source_type is SourceType.PREPROCESSED
    assert out.annotations["preprocessing_operator"] == "rolling_zscore"
    assert out.annotations["preprocessing_kind"] == "empirical"
    assert out.annotations["correction_target"] == "local_mean_variance"
    assert out.annotations["raw_record_id"] == "raw"
    assert len(out.preprocessing_history) == 1
    assert np.isfinite(out.values).all()
    assert abs(float(np.mean(out.values))) < 1e-8


def test_oracle_gain_uses_latent_gain() -> None:
    gen = NonstationaryLRDGenerator()
    rec = gen.generate(
        record_id="raw",
        params={"case": "lrd_smooth_gain", "H": 0.7, "n": 256, "gain_amplitude": 0.8},
        seed=123,
        manifest_id="m",
    )

    out = OracleGainPreprocessing().apply(
        rec,
        params={},
        seed=1,
        manifest_id="m",
        new_record_id="oracle",
    )

    assert out.annotations["preprocessing_operator"] == "oracle_gain"
    assert out.annotations["preprocessing_kind"] == "oracle"
    assert out.annotations["correction_target"] == "gain"
    assert np.isfinite(out.values).all()
    assert not np.allclose(out.values, rec.values)
