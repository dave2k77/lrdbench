"""Phase 1: Hurst / spectral-exponent / timescale estimand triangle.

Covers the multi-truth record contract (``additional_truths`` + ``truth_for``),
the beta reparametrisation, the companion truths declared by the fGn/fOU
generators, the ACF-decay timescale estimator, and per-estimand scoring in the
GroundTruthEvaluator.
"""

from __future__ import annotations

import numpy as np

from lrdbench.enums import BenchmarkMode, SourceType
from lrdbench.estimators.spectral import _as_target_estimand
from lrdbench.estimators.timescale import _acf_exponential_tau
from lrdbench.evaluator import GroundTruthEvaluator
from lrdbench.generators._signal import simulate_fou
from lrdbench.generators.fgn import FGNGenerator
from lrdbench.generators.fou import FOUGenerator
from lrdbench.metrics_catalog import metric_specs_from_manifest_entries
from lrdbench.schema import (
    BenchmarkManifest,
    EstimateResult,
    EstimatorSpec,
    SeriesRecord,
    TruthSpec,
)
from lrdbench.validation import truth_for


def _truth(estimand: str, value: float | None) -> TruthSpec:
    return TruthSpec(
        process_family="test",
        generating_params={},
        target_estimand=estimand,
        target_value=value,
    )


def _multi_truth_record() -> SeriesRecord:
    return SeriesRecord(
        record_id="r",
        values=np.zeros(8, dtype=float),
        time_axis=None,
        sampling_rate=None,
        source_type=SourceType.SYNTHETIC,
        source_name="test",
        truth=_truth("hurst_scaling_proxy", 0.7),
        additional_truths=(
            _truth("spectral_exponent_beta", 0.4),
            _truth("timescale_tau", 10.0),
        ),
    )


def test_truth_for_resolves_primary_then_additional() -> None:
    rec = _multi_truth_record()

    assert truth_for(rec, "hurst_scaling_proxy").target_value == 0.7
    assert truth_for(rec, "spectral_exponent_beta").target_value == 0.4
    assert truth_for(rec, "timescale_tau").target_value == 10.0
    assert truth_for(rec, "long_memory_parameter") is None


def test_beta_estimand_mapping_is_exact() -> None:
    for d in (-0.3, -0.1, 0.0, 0.16, 0.33, 0.49):
        beta = _as_target_estimand(d, "spectral_exponent_beta")
        hurst = _as_target_estimand(d, "hurst_scaling_proxy")
        assert beta == 2.0 * d
        # review identity H = (beta + 1) / 2
        assert abs((beta + 1.0) / 2.0 - hurst) < 1e-12
    assert _as_target_estimand(None, "spectral_exponent_beta") is None


def test_fgn_declares_beta_and_null_timescale() -> None:
    rec = FGNGenerator().generate(
        record_id="fgn", params={"H": 0.8, "n": 64, "sigma": 1.0}, seed=1, manifest_id="m"
    )
    beta = truth_for(rec, "spectral_exponent_beta")
    tau = truth_for(rec, "timescale_tau")

    assert rec.truth.target_value == 0.8
    assert beta is not None and abs(beta.target_value - (2 * 0.8 - 1.0)) < 1e-12
    assert tau is not None and tau.target_value is None  # power-law ACF, no finite tau


def test_fou_declares_mean_reversion_timescale() -> None:
    theta, dt = 0.1, 1.0
    rec = FOUGenerator().generate(
        record_id="fou",
        params={"H": 0.5, "n": 64, "theta": theta, "dt": dt, "sigma": 1.0, "burnin": 32},
        seed=1,
        manifest_id="m",
    )
    tau = truth_for(rec, "timescale_tau")

    assert tau is not None
    assert abs(tau.target_value - 1.0 / (theta * dt)) < 1e-12


def test_acf_decay_recovers_ou_timescale() -> None:
    # H = 0.5 fOU is a plain AR(1) with rho = exp(-theta*dt): tau = 1/(theta*dt).
    theta = 0.1
    tau_star = 1.0 / theta
    taus = []
    for r in range(11):
        rng = np.random.default_rng(100 + r)
        x = simulate_fou(2048, 0.5, theta, rng, sigma=1.0, dt=1.0)
        t = _acf_exponential_tau(x)
        if t is not None:
            taus.append(t)
    assert len(taus) >= 8
    ratio = float(np.median(taus)) / tau_star
    assert 0.6 < ratio < 1.6, f"median tau ratio {ratio:.2f} off (tau*={tau_star})"


def test_evaluator_scores_each_estimator_against_its_own_estimand() -> None:
    specs = tuple(
        EstimatorSpec(
            name=name,
            family="test",
            target_estimand=estimand,
            assumptions=(),
            supports_ci=False,
            supports_diagnostics=False,
        )
        for name, estimand in (
            ("H_est", "hurst_scaling_proxy"),
            ("B_est", "spectral_exponent_beta"),
            ("T_est", "timescale_tau"),
        )
    )
    metrics = metric_specs_from_manifest_entries(["bias", "validity_rate"])
    manifest = BenchmarkManifest(
        manifest_id="tri",
        name="tri",
        mode=BenchmarkMode.GROUND_TRUTH,
        source_spec={"type": "test"},
        estimator_specs=specs,
        metric_specs=tuple(metrics),
    )
    records = (_multi_truth_record(),)
    estimates = (
        EstimateResult(record_id="r", estimator_name="H_est", point=0.75, valid=True),
        EstimateResult(record_id="r", estimator_name="B_est", point=0.45, valid=True),
        EstimateResult(record_id="r", estimator_name="T_est", point=12.0, valid=True),
    )

    bundle = GroundTruthEvaluator().evaluate(manifest, records, estimates)
    bias = {
        m.estimator_name: m.value for m in bundle.per_series if m.metric_name == "bias"
    }

    assert abs(bias["H_est"] - (0.75 - 0.7)) < 1e-9
    assert abs(bias["B_est"] - (0.45 - 0.4)) < 1e-9
    assert abs(bias["T_est"] - (12.0 - 10.0)) < 1e-9


def test_evaluator_skips_bias_when_estimand_truth_is_absent() -> None:
    # A beta estimator on a record whose only truths are H (primary) and a
    # None-valued timescale gets no bias row (incompatible / no target value).
    rec = SeriesRecord(
        record_id="r",
        values=np.zeros(8, dtype=float),
        time_axis=None,
        sampling_rate=None,
        source_type=SourceType.SYNTHETIC,
        source_name="test",
        truth=_truth("hurst_scaling_proxy", 0.7),
        additional_truths=(_truth("timescale_tau", None),),
    )
    beta_spec = EstimatorSpec(
        name="B_est",
        family="test",
        target_estimand="spectral_exponent_beta",
        assumptions=(),
        supports_ci=False,
        supports_diagnostics=False,
    )
    metrics = metric_specs_from_manifest_entries(["bias", "validity_rate"])
    manifest = BenchmarkManifest(
        manifest_id="tri2",
        name="tri2",
        mode=BenchmarkMode.GROUND_TRUTH,
        source_spec={"type": "test"},
        estimator_specs=(beta_spec,),
        metric_specs=tuple(metrics),
    )
    estimates = (EstimateResult(record_id="r", estimator_name="B_est", point=0.3, valid=True),)

    bundle = GroundTruthEvaluator().evaluate(manifest, records=(rec,), estimates=estimates)

    assert not [m for m in bundle.per_series if m.metric_name == "bias"]
    # validity is estimand-agnostic and should still be recorded
    assert any(m.metric_name == "validity_rate" for m in bundle.per_series)
