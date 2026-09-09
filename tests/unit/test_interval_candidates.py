from __future__ import annotations

import copy
import json

import numpy as np
import pytest
from benchmark_experiment.remediation import interval_candidates as ci
from benchmark_experiment.remediation import run_interval_comparison as runner
from scipy.linalg import toeplitz
from scipy.optimize import minimize
from scipy.stats import multivariate_normal, norm

from lrdbench.estimators.geometric import _higuchi_fractal_dimension


def direct_higuchi(path, k_max):
    n = len(path)
    lengths, lags = [], np.arange(1, min(max(4, k_max), n // 4) + 1)
    for lag in lags:
        offset_lengths = []
        for start in range(lag):
            subset = path[start::lag]
            length = sum(abs(subset[j] - subset[j - 1]) for j in range(1, len(subset)))
            offset_lengths.append(length * (n - 1) / ((len(subset) - 1) * lag**2))
        lengths.append(np.mean(offset_lengths))
    return np.polyfit(np.log(1 / lags), np.log(lengths), 1)[0]


@pytest.mark.parametrize("n", [64, 129, 257, 512, 1025, 2048])
@pytest.mark.parametrize("k_max", [4, 13, 32, 64])
def test_vectorized_higuchi_matches_direct_offset_formula(n, k_max):
    rng = np.random.default_rng(852 + n)
    for path in (rng.normal(size=n), np.cumsum(rng.normal(size=n)), np.arange(n) ** 1.7):
        assert _higuchi_fractal_dimension(path, k_max=k_max) == pytest.approx(
            direct_higuchi(path, k_max), abs=3e-14
        )


@pytest.mark.parametrize("h", [0.1, 0.5, 0.9])
def test_profile_likelihood_matches_independent_eigendecomposition(h):
    x = np.random.default_rng(137).normal(size=64) + 0.5
    covariance = toeplitz(ci.fgn_covariance(len(x), h))
    eigenvalues, eigenvectors = np.linalg.eigh(covariance)
    quadratic = np.sum((eigenvectors.T @ x) ** 2 / eigenvalues)
    objective, variance = ci.profiled_fgn_likelihood(x, h)
    assert variance == pytest.approx(quadratic / len(x), rel=1e-12)
    assert objective == pytest.approx(
        len(x) * np.log(quadratic / len(x)) + np.log(eigenvalues).sum(), abs=1e-10
    )
    if h == 0.5:
        assert variance == pytest.approx(np.mean(x**2))  # Known zero, not sample mean.


def test_profile_optimizer_matches_full_gaussian_joint_optimization():
    x = np.random.default_rng(175).normal(size=64)
    fit = ci.fit_zero_mean_fgn(x)

    def objective(parameters):
        h, log_variance = parameters
        return -multivariate_normal.logpdf(
            x,
            mean=np.zeros(len(x)),
            cov=np.exp(log_variance) * toeplitz(ci.fgn_covariance(len(x), h)),
        )

    joint = minimize(
        objective,
        [0.5, 0],
        method="Nelder-Mead",
        bounds=[ci.H_BOUNDS, (-8, 8)],
        options={"xatol": 1e-7, "fatol": 1e-7, "maxfev": 3000},
    )
    assert joint.success
    assert fit["H"] == pytest.approx(joint.x[0], abs=2e-5)
    assert fit["sigma"] ** 2 == pytest.approx(np.exp(joint.x[1]), rel=2e-5)
    scaled = ci.fit_zero_mean_fgn(-x * 1e-8)
    assert scaled["H"] == pytest.approx(fit["H"], abs=2e-7)
    assert scaled["sigma"] == pytest.approx(fit["sigma"] * 1e-8, rel=1e-6)


def test_parametric_sampler_recovers_declared_covariance():
    class BasisRng:
        def normal(self, *, size):
            assert size == (16, 16)
            return np.eye(16)

    samples = ci.fitted_fgn_samples({"H": 0.75, "sigma": 2}, 16, 16, BasisRng())
    np.testing.assert_allclose(
        samples.T @ samples, 4 * toeplitz(ci.fgn_covariance(16, 0.75)), atol=1e-13
    )


def test_basic_center_and_nominal_tails_are_correct_without_clipping():
    samples = np.linspace(0, 1, 101)
    assert ci.bootstrap_interval(0.8, samples, center=0.6, method="percentile") == pytest.approx(
        (0.025, 0.975)
    )
    assert ci.bootstrap_interval(0.8, samples, center=0.6, method="basic") == pytest.approx(
        (0.425, 1.375)
    )
    assert ci.bootstrap_interval(0.8, samples, center=0.8, method="basic") == pytest.approx(
        (0.625, 1.575)
    )


@pytest.mark.parametrize("samples", [[], [0.4] * 4, [0.4] * 5 + [np.nan]])
def test_interval_requires_finite_sufficient_draws(samples):
    assert ci.bootstrap_interval(0.5, samples, center=0.5, method="basic") is None


def test_discarded_statistic_draws_are_counted(monkeypatch):
    def broken(x, method):
        if x[0] == 0:
            raise ValueError("injected")
        return None if x[0] == 1 else np.nan if x[0] == 2 else 0.5

    monkeypatch.setattr(ci, "statistic", broken)
    values, counts = ci.evaluate_draws(np.arange(5).reshape(5, 1), "GPH")
    np.testing.assert_array_equal(values, [0.5, 0.5])
    assert (counts["attempted"], counts["used"], counts["invalid"], counts["failed"]) == (
        5,
        2,
        2,
        1,
    )


def test_gph_ols_variance_against_independent_log_exponential_experiment():
    n, m = 512, 32
    regressor = np.log(4 * np.sin(np.pi * np.arange(1, m + 1) / n) ** 2)
    design = np.column_stack([np.ones(m), regressor])
    influence = np.linalg.pinv(design)[1]
    errors = np.log(np.random.default_rng(6771).exponential(size=(100000, m)))
    slopes = errors @ influence
    interval = ci.gph_asymptotic_interval(0.5, n, m=m)
    predicted_variance = ((interval[1] - 0.5) / norm.ppf(0.975)) ** 2
    assert slopes.var(ddof=1) == pytest.approx(predicted_variance, rel=0.015)


@pytest.fixture
def config():
    value = json.loads(runner.DEFAULT_CONFIG.read_text())
    value.update(
        lengths=[128],
        processes={"fGn": [0.5], "AR1": [0.8]},
        repetitions=2,
        bootstrap_draws=7,
        methods=["GPH"],
        seed_namespace="interval-software-test",
    )
    return value


def scientific_records(path):
    records = [json.loads(line) for line in (path / "records.jsonl").read_text().splitlines()]
    for record in records:
        for key in ("elapsed_seconds", "point_seconds", "model_seconds"):
            record.pop(key)
        for pool in record["draw_pools"].values():
            pool.pop("elapsed_seconds")
    return records


def test_declared_comparison_workload():
    value = json.loads(runner.DEFAULT_CONFIG.read_text())
    runner.validate(value)
    assert runner.workload(value) == {
        "cells": 7,
        "independent_records": 448,
        "model_fits": 448,
        "point_statistics": 1344,
        "physical_bootstrap_records": 178304,
        "bootstrap_statistic_attempts": 534912,
        "interval_rows": 5824,
    }


def test_candidate_runner_resume_reproduces_results(config, tmp_path):
    resumed, whole = tmp_path / "resumed", tmp_path / "whole"
    assert runner.run(config, resumed, max_new_records=1)["completed_records"] == 1
    assert runner.run(config, resumed)["new_records"] == 3
    runner.run(config, whole)
    assert scientific_records(resumed) == scientific_records(whole)
    assert runner.run(config, resumed)["new_records"] == 0
    changed = copy.deepcopy(config)
    changed["bootstrap_draws"] = 9
    with pytest.raises(ValueError, match="Resume refused"):
        runner.run(changed, resumed)


def test_failed_model_preserves_cbc_and_counts_zero_generated_records(config, monkeypatch):
    def fail(x):
        raise ValueError("injected")

    monkeypatch.setattr(ci, "fit_zero_mean_fgn", fail)
    cell = {"family": "fGn", "parameter": 0.5, "n": 128}
    x = np.random.default_rng(777).normal(size=128)
    record = runner.fit_record(
        x, {"record_id": "x", "sha256": "hash", "repetition": 0}, cell, config
    )
    assert record["draw_pools"]["fgn"]["generated_records"] == 0
    assert record["draw_pools"]["cbc"]["generated_records"] == 7
    frame = runner.interval_frame([record])
    summary = runner.summarize(frame)
    assert summary[summary.candidate.str.startswith("fgn")].n_available.eq(0).all()
    assert summary[summary.candidate.str.startswith("cbc")].n_available.eq(1).all()
    pairs = runner.paired_comparisons(frame)
    assert pairs[pairs.candidate.str.startswith("fgn")].n_missing_pairs.eq(1).all()


def test_fgn_model_does_not_receive_truth(config, monkeypatch):
    x = np.random.default_rng(998).normal(size=128)
    metadata = {"record_id": "x", "sha256": "hash", "repetition": 0}
    records = [
        runner.fit_record(x, metadata, {"family": "fGn", "parameter": h, "n": 128}, config)
        for h in (0.25, 0.75)
    ]
    assert records[0]["points"] == records[1]["points"]
    assert records[0]["fitted_model"] == records[1]["fitted_model"]
    # Seeds are process-keyed by design, so the generated bootstrap draws differ.
