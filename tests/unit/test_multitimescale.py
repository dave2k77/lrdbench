"""Phase 2: multi_timescale generator (apparent-LRD short-memory null)."""

from __future__ import annotations

import numpy as np

from lrdbench.enums import SourceType
from lrdbench.estimators.temporal import DFAEstimator
from lrdbench.generators._signal import simulate_multitimescale
from lrdbench.generators.multitimescale import MultiTimescaleGenerator
from lrdbench.schema import EstimatorSpec, ProvenanceRecord, SeriesRecord
from lrdbench.validation import truth_for


def _dfa() -> DFAEstimator:
    spec = EstimatorSpec(
        name="DFA",
        family="temporal",
        target_estimand="hurst_scaling_proxy",
        assumptions=(),
        supports_ci=False,
        supports_diagnostics=False,
        parameter_schema={"n_bootstrap": 0},
    )
    return DFAEstimator(spec)


def _record(values: np.ndarray, seed: int) -> SeriesRecord:
    return SeriesRecord(
        record_id="r",
        values=values,
        time_axis=None,
        sampling_rate=None,
        source_type=SourceType.SYNTHETIC,
        source_name="mt",
        provenance=ProvenanceRecord(
            record_id="r", parent_id=None, manifest_id="m", created_at="t", seed=seed
        ),
    )


def test_multitimescale_is_deterministic_and_declares_null_truth() -> None:
    gen = MultiTimescaleGenerator()
    params = {"n": 256, "tau_max": 8.0, "n_components": 6, "sigma": 1.0}

    a = gen.generate(record_id="mt_a", params=params, seed=7, manifest_id="m")
    b = gen.generate(record_id="mt_a", params=params, seed=7, manifest_id="m")

    assert a.source_type is SourceType.SYNTHETIC
    assert a.source_name == "multi_timescale"
    # Rigorously short-memory: the Hurst truth is the 0.5 null.
    assert a.truth is not None
    assert a.truth.target_estimand == "hurst_scaling_proxy"
    assert a.truth.target_value == 0.5
    # No single characteristic timescale.
    tau = truth_for(a, "timescale_tau")
    assert tau is not None and tau.target_value is None
    np.testing.assert_allclose(a.values, b.values)
    assert np.isfinite(a.values).all()
    assert float(np.std(a.values)) > 0.0


def test_multitimescale_autocovariance_is_summable() -> None:
    # Short memory => normalised ACF tail decays and the partial sum stays bounded
    # (does not diverge the way an LRD process would).
    rng = np.random.default_rng(3)
    x = simulate_multitimescale(8192, rng, n_components=8, tau_min=1.5, tau_max=8.0)
    xc = x - x.mean()
    acf = np.correlate(xc, xc, "full")[len(x) - 1 :] / float(np.dot(xc, xc))
    # ACF should be small well beyond the largest timescale (~8): effectively decayed.
    assert abs(float(acf[200])) < 0.1


def test_multitimescale_apparent_hurst_increases_with_tau_max() -> None:
    # Same truth (H=0.5) but the apparent Hurst reported by DFA grows with tau_max.
    dfa = _dfa()

    def apparent_h(tau_max: float) -> float:
        vals = []
        for r in range(6):
            rng = np.random.default_rng(900 + int(tau_max) + r)
            x = simulate_multitimescale(4096, rng, n_components=8, tau_min=1.5, tau_max=tau_max)
            res = dfa.fit(_record(x, r))
            if res.point is not None:
                vals.append(res.point)
        return float(np.mean(vals))

    h_low = apparent_h(4.0)
    h_high = apparent_h(16.0)

    # Both are false positives (truth is 0.5) and severity is ordered by tau_max.
    assert h_low > 0.5
    assert h_high > h_low
