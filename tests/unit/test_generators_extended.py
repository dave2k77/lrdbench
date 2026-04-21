from __future__ import annotations

import numpy as np
import pytest

from lrdbench.defaults import build_default_generator_registry
from lrdbench.enums import SourceType
from lrdbench.generators._signal import simulate_fou, simulate_mrw
from lrdbench.generators.fou import FOUGenerator
from lrdbench.generators.mrw import MRWGenerator


def test_default_generator_registry_lists_mrw_and_fou() -> None:
    reg = build_default_generator_registry()

    assert "MRW" in reg.list()
    assert "fOU" in reg.list()


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


def test_mrw_signal_parameter_validation() -> None:
    rng = np.random.default_rng(1)

    with pytest.raises(ValueError, match="lambda2"):
        simulate_mrw(32, 0.6, rng, lambda2=-0.1)


def test_fou_signal_parameter_validation() -> None:
    rng = np.random.default_rng(1)

    with pytest.raises(ValueError, match="theta"):
        simulate_fou(32, 0.6, 0.0, rng)
