from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

import numpy as np

from lrdbench.enums import SourceType
from lrdbench.generators._signal import simulate_arfima_zero_d_zero
from lrdbench.interfaces import BaseGenerator
from lrdbench.schema import ProvenanceRecord, SeriesRecord, TruthSpec


def _standardize(x: np.ndarray, eps: float = 1e-12) -> np.ndarray:
    x = np.asarray(x, dtype=float)
    return (x - float(np.mean(x))) / (float(np.std(x)) + eps)


def _ar1_process(
    n: int,
    phi: float,
    rng: np.random.Generator,
    *,
    innovation: str = "gaussian",
) -> np.ndarray:
    eps = rng.standard_t(df=3.0, size=n) if innovation == "student_t" else rng.standard_normal(n)
    x = np.zeros(n, dtype=float)
    for i in range(1, n):
        x[i] = float(phi) * x[i - 1] + eps[i]
    return _standardize(x)


def _smooth_gain(n: int, amplitude: float, period: int | None = None) -> np.ndarray:
    period = 2 * n if period is None else int(period)
    t = np.arange(n, dtype=float)
    return np.exp(float(amplitude) * np.sin(2.0 * np.pi * t / period))


def _piecewise_gain(
    n: int,
    rng: np.random.Generator,
    *,
    amplitude: float,
    segments: int,
) -> np.ndarray:
    segments = max(1, int(segments))
    values = np.exp(float(amplitude) * rng.standard_normal(segments))
    edges = np.linspace(0, n, segments + 1, dtype=int)
    gain = np.ones(n, dtype=float)
    for j in range(segments):
        gain[edges[j] : edges[j + 1]] = values[j]
    return gain


def _randomwalk_gain(
    n: int,
    rng: np.random.Generator,
    *,
    amplitude: float,
    step_scale: float,
) -> np.ndarray:
    log_gain = np.cumsum(float(step_scale) * rng.standard_normal(n))
    return np.exp(float(amplitude) * _standardize(log_gain))


def _burst_envelope(
    n: int,
    rng: np.random.Generator,
    *,
    rate: float,
    width: int,
    amplitude: float,
) -> np.ndarray:
    impulses = rng.random(n) < float(rate)
    width = max(1, int(width))
    kernel_t = np.arange(-4 * width, 4 * width + 1, dtype=float)
    kernel = np.exp(-(kernel_t**2) / (2.0 * width**2))
    envelope = np.convolve(impulses.astype(float), kernel, mode="same")
    if envelope.size != n:
        start = max(0, (envelope.size - n) // 2)
        envelope = envelope[start : start + n]
    if float(np.max(envelope)) > 0.0:
        envelope = envelope / float(np.max(envelope))
    return 1.0 + float(amplitude) * envelope


def _smooth_drift(n: int, amplitude: float, period: int | None = None) -> np.ndarray:
    period = 2 * n if period is None else int(period)
    t = np.arange(n, dtype=float)
    return float(amplitude) * (
        np.sin(2.0 * np.pi * t / period)
        + 0.35 * np.sin(2.0 * np.pi * t / (period / 4.0))
    )


def _regime_state(n: int, rng: np.random.Generator, *, switch_prob: float) -> np.ndarray:
    state = np.zeros(n, dtype=int)
    for i in range(1, n):
        state[i] = 1 - state[i - 1] if rng.random() < float(switch_prob) else state[i - 1]
    return state


def _qsoc_state(
    n: int,
    rng: np.random.Generator,
    *,
    kappa: float,
    dissipation: float,
    drive_amplitude: float,
    noise_scale: float,
    drive_period: int | None,
) -> np.ndarray:
    drive_period = 3 * n if drive_period is None else int(drive_period)
    state = np.zeros(n, dtype=float)
    drive = float(drive_amplitude) * np.sin(2.0 * np.pi * np.arange(n) / drive_period)
    for i in range(1, n):
        restorative = -float(kappa) * state[i - 1]
        loss = -float(dissipation) * state[i - 1]
        state[i] = (
            state[i - 1]
            + restorative
            + loss
            + drive[i - 1]
            + float(noise_scale) * rng.standard_normal()
        )
    return _standardize(state)


class NonstationaryLRDGenerator(BaseGenerator):
    """Joint LRD/nonstationarity generator for variance-trap benchmarks.

    The ``case`` parameter selects a nonstationarity family. Cases beginning
    with ``short_`` have target ``H = 0.5`` and are false-positive controls.
    Cases beginning with ``lrd_`` embed an ARFIMA(0,d,0) source with
    ``d = H - 0.5`` and are false-negative / correction-stress controls.
    """

    CASES = {
        "pure_short",
        "pure_lrd",
        "short_smooth_gain",
        "short_piecewise_gain",
        "short_randomwalk_gain",
        "short_bursty_t",
        "short_regime_switch",
        "short_qsoc",
        "lrd_smooth_gain",
        "lrd_piecewise_gain",
        "lrd_randomwalk_gain",
        "lrd_drift",
        "lrd_qsoc",
    }
    CASE_SOURCES = {
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

    @property
    def family(self) -> str:
        return "NonstationaryLRD"

    @property
    def version(self) -> str:
        return "0.1.0"

    def generate(
        self,
        *,
        record_id: str,
        params: Mapping[str, Any],
        seed: int | None,
        manifest_id: str | None,
    ) -> SeriesRecord:
        n = int(params["n"])
        if n < 16:
            raise ValueError("n must be at least 16 for NonstationaryLRD")
        case = str(params["case"])
        if case not in self.CASES:
            raise ValueError(f"unknown NonstationaryLRD case: {case!r}")
        nonstationarity_source = self.CASE_SOURCES[case]

        hurst = float(params.get("H", 0.7))
        if not 0.5 <= hurst < 1.0:
            raise ValueError("H must be in [0.5, 1) for NonstationaryLRD")
        gain_amplitude = float(params.get("gain_amplitude", 0.8))
        ar_phi = float(params.get("ar_phi", 0.35))
        noise_scale = float(params.get("noise_scale", 0.04))
        sigma = float(params.get("sigma", 1.0))
        rng = np.random.default_rng(seed)

        lrd = _standardize(simulate_arfima_zero_d_zero(n, hurst - 0.5, rng, sigma=1.0))
        short = _ar1_process(n, ar_phi, rng)
        gain = np.ones(n, dtype=float)
        drift = np.zeros(n, dtype=float)
        state = np.zeros(n, dtype=float)
        eps = float(noise_scale) * rng.standard_normal(n)

        if case == "pure_short":
            z, target_h = short + eps, 0.5
            nonstationarity_family = "control"
        elif case == "pure_lrd":
            z, target_h = lrd + eps, hurst
            nonstationarity_family = "control"
        elif case == "short_smooth_gain":
            gain = _smooth_gain(n, gain_amplitude, params.get("gain_period"))
            z, target_h = gain * short + eps, 0.5
            nonstationarity_family = "multiplicative_gain"
        elif case == "short_piecewise_gain":
            gain = _piecewise_gain(
                n,
                rng,
                amplitude=gain_amplitude,
                segments=int(params.get("segments", 8)),
            )
            z, target_h = gain * short + eps, 0.5
            nonstationarity_family = "piecewise_gain"
        elif case == "short_randomwalk_gain":
            gain = _randomwalk_gain(
                n,
                rng,
                amplitude=gain_amplitude,
                step_scale=float(params.get("gain_step_scale", 0.035)),
            )
            z, target_h = gain * short + eps, 0.5
            nonstationarity_family = "randomwalk_gain"
        elif case == "short_bursty_t":
            gain = _burst_envelope(
                n,
                rng,
                rate=float(params.get("burst_rate", 0.012)),
                width=int(params.get("burst_width", 24)),
                amplitude=float(params.get("burst_amplitude", 1.6)),
            )
            short_t = _ar1_process(n, ar_phi, rng, innovation="student_t")
            z, target_h = gain * short_t + eps, 0.5
            nonstationarity_family = "bursty_heavy_tail"
        elif case == "short_regime_switch":
            state = _regime_state(n, rng, switch_prob=float(params.get("switch_prob", 0.004)))
            short2 = _ar1_process(n, float(params.get("regime_ar_phi", 0.75)), rng)
            gain = np.where(state > 0, np.exp(gain_amplitude), np.exp(-gain_amplitude / 2.0))
            z, target_h = np.where(state > 0, short2, short) * gain + eps, 0.5
            nonstationarity_family = "regime_switch"
        elif case == "short_qsoc":
            state = _qsoc_state(
                n,
                rng,
                kappa=float(params.get("qsoc_kappa", 0.022)),
                dissipation=float(params.get("qsoc_dissipation", 0.004)),
                drive_amplitude=float(params.get("qsoc_drive_amplitude", 0.03)),
                noise_scale=float(params.get("qsoc_noise_scale", 0.08)),
                drive_period=params.get("qsoc_drive_period"),
            )
            gain = np.exp(gain_amplitude * state / 2.0)
            z, target_h = gain * short + eps, 0.5
            nonstationarity_family = "qsoc_gain"
        elif case == "lrd_smooth_gain":
            gain = _smooth_gain(n, gain_amplitude, params.get("gain_period"))
            z, target_h = gain * lrd + eps, hurst
            nonstationarity_family = "multiplicative_gain"
        elif case == "lrd_piecewise_gain":
            gain = _piecewise_gain(
                n,
                rng,
                amplitude=gain_amplitude,
                segments=int(params.get("segments", 8)),
            )
            z, target_h = gain * lrd + eps, hurst
            nonstationarity_family = "piecewise_gain"
        elif case == "lrd_randomwalk_gain":
            gain = _randomwalk_gain(
                n,
                rng,
                amplitude=gain_amplitude,
                step_scale=float(params.get("gain_step_scale", 0.035)),
            )
            z, target_h = gain * lrd + eps, hurst
            nonstationarity_family = "randomwalk_gain"
        elif case == "lrd_drift":
            drift = _smooth_drift(
                n,
                float(params.get("drift_amplitude", 0.9)),
                params.get("drift_period"),
            )
            z, target_h = lrd + drift + eps, hurst
            nonstationarity_family = "additive_drift"
        elif case == "lrd_qsoc":
            state = _qsoc_state(
                n,
                rng,
                kappa=float(params.get("qsoc_kappa", 0.022)),
                dissipation=float(params.get("qsoc_dissipation", 0.004)),
                drive_amplitude=float(params.get("qsoc_drive_amplitude", 0.03)),
                noise_scale=float(params.get("qsoc_noise_scale", 0.08)),
                drive_period=params.get("qsoc_drive_period"),
            )
            gain = np.exp(gain_amplitude * state / 2.0)
            z, target_h = gain * lrd + eps, hurst
            nonstationarity_family = "qsoc_gain"
        else:  # pragma: no cover - guarded above
            raise ValueError(f"unhandled NonstationaryLRD case: {case!r}")

        values = sigma * _standardize(z)
        generating_params = dict(params)
        generating_params["resolved_target_H"] = target_h
        truth = TruthSpec(
            process_family=f"{self.family}:{case}",
            generating_params=generating_params,
            target_estimand="hurst_scaling_proxy",
            target_value=float(target_h),
            validity_domain={
                "stationarity": "conditional",
                "observable": "scalar_observed_signal",
                "representation": "Euclidean amplitude time series",
            },
            notes=(
                "Joint LRD/nonstationarity benchmark case. For short_* cases the "
                "target H=0.5 denotes the short-memory null; for lrd_* cases the "
                "target is the latent ARFIMA source H."
            ),
        )
        prov = ProvenanceRecord(
            record_id=record_id,
            parent_id=None,
            manifest_id=manifest_id,
            created_at=datetime.now(UTC).isoformat(),
            source_version=self.version,
            software_version=None,
            git_commit=None,
            seed=seed,
        )
        annotations: dict[str, Any] = {
            "process_family": self.family,
            "nonstationary_case": case,
            "nonstationarity_source": nonstationarity_source,
            "nonstationarity_family": nonstationarity_family,
            "n": n,
            "H": hurst,
            "target_H": float(target_h),
            "gain_amplitude": gain_amplitude,
            "ar_phi": ar_phi,
            "noise_scale": noise_scale,
            "sigma": sigma,
            "latent_gain_mean": float(np.mean(gain)),
            "latent_gain_std": float(np.std(gain)),
            "latent_drift_std": float(np.std(drift)),
            "latent_state_std": float(np.std(state)),
        }
        return SeriesRecord(
            record_id=record_id,
            values=values,
            time_axis=None,
            sampling_rate=None,
            source_type=SourceType.SYNTHETIC,
            source_name=self.family,
            truth=truth,
            annotations=annotations,
            provenance=prov,
        )
