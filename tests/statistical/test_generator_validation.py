from __future__ import annotations

import numpy as np
import pytest

from lrdbench.generators._signal import (
    simulate_arfima_zero_d_zero,
    simulate_fbm,
    simulate_fgn,
    simulate_fou,
    simulate_mrw,
)


def _block_sum_variance_slope(x: np.ndarray, blocks: tuple[int, ...] = (2, 4, 8, 16, 32)) -> float:
    variances: list[float] = []
    for block in blocks:
        n_used = (x.size // block) * block
        blocked = x[:n_used].reshape(-1, block).sum(axis=1)
        variances.append(float(np.var(blocked, ddof=1)))
    return float(np.polyfit(np.log(np.asarray(blocks)), np.log(np.asarray(variances)), 1)[0])


def _increment_variance_slope(x: np.ndarray, lags: tuple[int, ...] = (1, 2, 4, 8, 16)) -> float:
    variances = [float(np.var(x[lag:] - x[:-lag], ddof=1)) for lag in lags]
    return float(np.polyfit(np.log(np.asarray(lags)), np.log(np.asarray(variances)), 1)[0])


def _standardized_kurtosis(x: np.ndarray) -> float:
    z = (x - float(np.mean(x))) / float(np.std(x))
    return float(np.mean(z**4))


@pytest.mark.statistical
def test_fgn_block_sum_scaling_tracks_hurst_ordering() -> None:
    low_h_slopes = [
        _block_sum_variance_slope(simulate_fgn(512, 0.35, np.random.default_rng(seed)))
        for seed in range(8)
    ]
    high_h_slopes = [
        _block_sum_variance_slope(simulate_fgn(512, 0.75, np.random.default_rng(seed + 20)))
        for seed in range(8)
    ]

    assert float(np.mean(low_h_slopes)) < 1.05
    assert float(np.mean(high_h_slopes)) > 1.25
    assert float(np.mean(high_h_slopes)) - float(np.mean(low_h_slopes)) > 0.45


@pytest.mark.statistical
def test_fbm_increment_variance_scaling_tracks_hurst_ordering() -> None:
    low_h_slopes = [
        _increment_variance_slope(simulate_fbm(256, 0.35, np.random.default_rng(seed + 100)))
        for seed in range(8)
    ]
    high_h_slopes = [
        _increment_variance_slope(simulate_fbm(256, 0.75, np.random.default_rng(seed + 120)))
        for seed in range(8)
    ]

    assert float(np.mean(low_h_slopes)) < 0.9
    assert float(np.mean(high_h_slopes)) > 1.1
    assert float(np.mean(high_h_slopes)) - float(np.mean(low_h_slopes)) > 0.45


@pytest.mark.statistical
def test_arfima_memory_parameter_changes_block_scaling_and_autocorrelation() -> None:
    short_memory_slopes: list[float] = []
    long_memory_slopes: list[float] = []
    short_memory_acf1: list[float] = []
    long_memory_acf1: list[float] = []

    for seed in range(8):
        short = simulate_arfima_zero_d_zero(1024, 0.0, np.random.default_rng(seed + 200))
        long = simulate_arfima_zero_d_zero(1024, 0.35, np.random.default_rng(seed + 220))
        short_memory_slopes.append(_block_sum_variance_slope(short))
        long_memory_slopes.append(_block_sum_variance_slope(long))
        short_memory_acf1.append(float(np.corrcoef(short[:-1], short[1:])[0, 1]))
        long_memory_acf1.append(float(np.corrcoef(long[:-1], long[1:])[0, 1]))

    assert abs(float(np.mean(short_memory_acf1))) < 0.15
    assert float(np.mean(long_memory_acf1)) > 0.35
    assert float(np.mean(long_memory_slopes)) - float(np.mean(short_memory_slopes)) > 0.4


@pytest.mark.statistical
def test_mrw_intermittency_increases_tail_heaviness() -> None:
    gaussian_like_kurtosis = [
        _standardized_kurtosis(
            simulate_mrw(
                512,
                0.65,
                np.random.default_rng(seed + 300),
                lambda2=0.0,
                integral_scale=64,
            )
        )
        for seed in range(8)
    ]
    intermittent_kurtosis = [
        _standardized_kurtosis(
            simulate_mrw(
                512,
                0.65,
                np.random.default_rng(seed + 320),
                lambda2=0.08,
                integral_scale=64,
            )
        )
        for seed in range(8)
    ]

    assert float(np.mean(gaussian_like_kurtosis)) < 3.5
    assert float(np.mean(intermittent_kurtosis)) > 3.5
    assert float(np.mean(intermittent_kurtosis)) - float(np.mean(gaussian_like_kurtosis)) > 0.5


@pytest.mark.statistical
def test_fou_mean_reversion_strength_changes_lag_one_autocorrelation() -> None:
    weak_reversion_acf1 = [
        float(
            np.corrcoef(
                (x := simulate_fou(512, 0.65, 0.05, np.random.default_rng(seed + 400), burnin=128))[
                    :-1
                ],
                x[1:],
            )[0, 1]
        )
        for seed in range(8)
    ]
    strong_reversion_acf1 = [
        float(
            np.corrcoef(
                (x := simulate_fou(512, 0.65, 0.5, np.random.default_rng(seed + 420), burnin=128))[
                    :-1
                ],
                x[1:],
            )[0, 1]
        )
        for seed in range(8)
    ]

    assert float(np.mean(weak_reversion_acf1)) > 0.9
    assert float(np.mean(strong_reversion_acf1)) < 0.85
    assert float(np.mean(weak_reversion_acf1)) - float(np.mean(strong_reversion_acf1)) > 0.15
