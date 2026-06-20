from __future__ import annotations

import numpy as np
import pytest

from lrdbench.defaults import build_default_generator_registry
from lrdbench.enums import SourceType
from lrdbench.generators._signal import simulate_fou, simulate_mrw
from lrdbench.generators.fou import FOUGenerator
from lrdbench.generators.mrw import MRWGenerator
from lrdbench.generators.nonstationary_lrd import NonstationaryLRDGenerator
from lrdbench.strata import stratum_from_record


def test_default_generator_registry_lists_mrw_and_fou() -> None:
    reg = build_default_generator_registry()

    assert "MRW" in reg.list()
    assert "fOU" in reg.list()
    assert "NonstationaryLRD" in reg.list()


def test_mrw_generator_is_deterministic_and_records_truth() -> None:
    gen = MRWGenerator()
    params = {"H": 0.7, "n": 96, "sigma": 1.0, "lambda2": 0.04, "integral_scale": 24}

    a = gen.generate(record_id="mrw_a", params=params, seed=123, manifest_id="m")
    b = gen.generate(record_id="mrw_a", params=params, seed=123, manifest_id="m")

    assert a.source_type is SourceType.SYNTHETIC
    assert a.source_name == "MRW"
    assert a.truth is not None
    assert a.truth.target_estimand == "hurst_scaling_proxy"
    assert a.truth.target_value == 0.7
    assert a.annotations["lambda2"] == 0.04
    np.testing.assert_allclose(a.values, b.values)
    assert np.isfinite(a.values).all()
    assert float(np.std(a.values)) > 0.0


def test_fou_generator_is_deterministic_and_records_truth() -> None:
    gen = FOUGenerator()
    params = {"H": 0.65, "n": 96, "theta": 0.2, "sigma": 1.0, "dt": 1.0, "burnin": 32}

    a = gen.generate(record_id="fou_a", params=params, seed=123, manifest_id="m")
    b = gen.generate(record_id="fou_a", params=params, seed=123, manifest_id="m")

    assert a.source_type is SourceType.SYNTHETIC
    assert a.source_name == "fOU"
    assert a.truth is not None
    assert a.truth.target_estimand == "hurst_scaling_proxy"
    assert a.truth.target_value == 0.65
    assert a.annotations["theta"] == 0.2
    np.testing.assert_allclose(a.values, b.values)
    assert np.isfinite(a.values).all()
    assert float(np.std(a.values)) > 0.0


def test_nonstationary_lrd_generator_is_deterministic_and_records_truth() -> None:
    gen = NonstationaryLRDGenerator()
    params = {
        "case": "lrd_randomwalk_gain",
        "H": 0.7,
        "n": 128,
        "gain_amplitude": 0.8,
        "sigma": 1.0,
    }

    a = gen.generate(record_id="nlrd_a", params=params, seed=123, manifest_id="m")
    b = gen.generate(record_id="nlrd_a", params=params, seed=123, manifest_id="m")

    assert a.source_type is SourceType.SYNTHETIC
    assert a.source_name == "NonstationaryLRD"
    assert a.truth is not None
    assert a.truth.target_estimand == "hurst_scaling_proxy"
    assert a.truth.target_value == 0.7
    assert a.annotations["nonstationary_case"] == "lrd_randomwalk_gain"
    assert a.annotations["nonstationarity_source"] == "observational"
    assert a.annotations["nonstationarity_family"] == "randomwalk_gain"
    assert a.annotations["latent_gain_std"] > 0.0
    np.testing.assert_allclose(a.values, b.values)
    assert np.isfinite(a.values).all()
    assert float(np.std(a.values)) > 0.0


def test_nonstationary_lrd_short_case_uses_short_memory_target() -> None:
    gen = NonstationaryLRDGenerator()
    rec = gen.generate(
        record_id="nlrd_short",
        params={"case": "short_regime_switch", "H": 0.7, "n": 128},
        seed=123,
        manifest_id="m",
    )

    assert rec.truth is not None
    assert rec.truth.target_value == 0.5
    assert rec.annotations["target_H"] == 0.5
    assert rec.annotations["nonstationarity_source"] == "intrinsic"
    assert rec.annotations["nonstationarity_family"] == "regime_switch"


def test_nonstationary_lrd_cases_have_taxonomy_sources() -> None:
    gen = NonstationaryLRDGenerator()
    expected = {
        "pure_short": "control",
        "pure_lrd": "control",
        "short_smooth_gain": "observational",
        "short_piecewise_gain": "observational",
        "short_randomwalk_gain": "observational",
        "short_bursty_t": "intrinsic",
        "short_regime_switch": "intrinsic",
        "short_qsoc": "physical",
        "lrd_smooth_gain": "observational",
        "lrd_piecewise_gain": "observational",
        "lrd_randomwalk_gain": "observational",
        "lrd_drift": "intrinsic",
        "lrd_qsoc": "physical",
    }

    for case, source in expected.items():
        rec = gen.generate(
            record_id=f"nlrd_{case}",
            params={"case": case, "H": 0.7, "n": 128},
            seed=123,
            manifest_id="m",
        )
        assert rec.annotations["nonstationarity_source"] == source


def test_nonstationary_lrd_case_is_part_of_report_stratum() -> None:
    gen = NonstationaryLRDGenerator()
    rec = gen.generate(
        record_id="nlrd_case_stratum",
        params={"case": "lrd_qsoc", "H": 0.7, "n": 128},
        seed=123,
        manifest_id="m",
    )

    stratum = dict(stratum_from_record(rec))

    assert stratum["nonstationary_case"] == "lrd_qsoc"
    assert stratum["nonstationarity_source"] == "physical"
    assert stratum["nonstationarity_family"] == "qsoc_gain"
    assert stratum["target_value"] == 0.7


def test_mrw_signal_parameter_validation() -> None:
    rng = np.random.default_rng(1)

    with pytest.raises(ValueError, match="lambda2"):
        simulate_mrw(32, 0.6, rng, lambda2=-0.1)


def test_fou_signal_parameter_validation() -> None:
    rng = np.random.default_rng(1)

    with pytest.raises(ValueError, match="theta"):
        simulate_fou(32, 0.6, 0.0, rng)
