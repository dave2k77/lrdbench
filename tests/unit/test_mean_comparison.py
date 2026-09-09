from __future__ import annotations

import copy
import json

import numpy as np
import pytest
from benchmark_experiment.remediation import run_mean_comparison as mean
from scipy.linalg import toeplitz
from scipy.optimize import minimize
from scipy.stats import multivariate_normal


@pytest.mark.parametrize("h", [0.1, 0.5, 0.9])
def test_unknown_mean_profile_against_dense_generalized_least_squares(h):
    x = np.random.default_rng(887).normal(size=64) + 2.3
    covariance = toeplitz(mean.ci.fgn_covariance(len(x), h))
    inverse = np.linalg.inv(covariance)
    ones = np.ones(len(x))
    mu = ones @ inverse @ x / (ones @ inverse @ ones)
    residual = x - mu
    variance = residual @ inverse @ residual / len(x)
    objective = len(x) * np.log(variance) + np.linalg.slogdet(covariance)[1]
    actual = mean.profiled_unknown_mean_likelihood(x, h)
    np.testing.assert_allclose(actual, (objective, variance, mu), atol=2e-11)
    if h == 0.5:
        assert actual[1] == pytest.approx(x.var(ddof=0))  # ML divisor, not REML.
        assert actual[2] == pytest.approx(x.mean())


def test_unknown_mean_fit_against_independent_joint_gaussian_optimization():
    x = np.random.default_rng(776).normal(size=64) + 1.2
    fit = mean.fit_unknown_mean_fgn(x)

    def objective(parameters):
        h, log_variance, mu = parameters
        return -multivariate_normal.logpdf(
            x,
            mean=np.full(len(x), mu),
            cov=np.exp(log_variance) * toeplitz(mean.ci.fgn_covariance(len(x), h)),
        )

    joint = minimize(
        objective,
        [0.5, 0, 1],
        method="Nelder-Mead",
        bounds=[mean.ci.H_BOUNDS, (-8, 8), (-10, 10)],
        options={"xatol": 1e-7, "fatol": 1e-7, "maxfev": 3000},
    )
    assert joint.success
    assert fit["H"] == pytest.approx(joint.x[0], abs=2e-5)
    assert fit["sigma"] ** 2 == pytest.approx(np.exp(joint.x[1]), rel=2e-5)
    assert fit["mean"] == pytest.approx(joint.x[2], abs=2e-5)
    transformed = mean.fit_unknown_mean_fgn(-3 * x + 17)
    assert transformed["H"] == pytest.approx(fit["H"], abs=2e-7)
    assert transformed["sigma"] == pytest.approx(3 * fit["sigma"], rel=1e-6)
    assert transformed["mean"] == pytest.approx(-3 * fit["mean"] + 17, abs=2e-6)


@pytest.mark.parametrize("x", [np.ones(64), np.ones(32), np.ones((64, 2)), np.full(64, np.nan)])
def test_unknown_mean_fit_rejects_invalid_inputs(x):
    with pytest.raises(ValueError, match="finite nonconstant"):
        mean.fit_unknown_mean_fgn(x)


@pytest.fixture
def config():
    value = json.loads(mean.DEFAULT_CONFIG.read_text())
    value.update(
        lengths=[128],
        processes={"fGn": [0.75]},
        repetitions=2,
        bootstrap_draws=7,
        seed_namespace="mean-software-test",
    )
    return value


def record(x, config):
    return mean.fit_record(
        x,
        {"record_id": "x", "sha256": "hash", "repetition": 0},
        {"family": "fGn", "parameter": 0.75, "n": len(x)},
        config,
    )


def test_centered_pipeline_translation_invariance_and_per_draw_mean(config):
    x = np.random.default_rng(7762).normal(size=128)
    base, shifted = record(x, config), record(x + 1, config)
    assert base["fitted_models"]["unknown"]["H"] == pytest.approx(
        shifted["fitted_models"]["unknown"]["H"],
        abs=2e-7,
    )
    for left, right in zip(base["intervals"], shifted["intervals"], strict=True):
        if left["treatment"] == "centered" and not left["candidate"].startswith("zero"):
            np.testing.assert_allclose(
                [left[k] for k in ("point", "ci_low", "ci_high")],
                [right[k] for k in ("point", "ci_low", "ci_high")],
                atol=2e-7,
            )
    pool = base["draw_pools"]["cbc"]
    rng = np.random.default_rng(pool["seed"])
    draws = [mean.circular_block_resample(x, rng, len(x) // 16) for _ in range(7)]
    for method in config["methods"]:
        # Independent per-record reference, not a once-only parent correction.
        reference = [mean.ci.statistic(draw - np.mean(draw), method) for draw in draws]
        np.testing.assert_allclose(pool["statistics"][f"centered:{method}"], reference, atol=1e-13)
    assert abs(base["points"]["raw:Higuchi"] - shifted["points"]["raw:Higuchi"]) > 0.1
    assert sum(p["generated_records"] for p in base["draw_pools"].values()) == 21
    assert (
        sum(c["attempted"] for p in base["draw_pools"].values() for c in p["accounting"].values())
        == 105
    )
    assert len(base["intervals"]) == 20


def test_unknown_model_generation_includes_fitted_mean(config, monkeypatch):
    def fit(x):
        return {"mean": 9.0, "sigma": 1, "H": 0.75, "boundary_hit": False}

    def samples(model, n, draws, rng):
        return np.arange(draws * n, dtype=float).reshape(draws, n)

    original = mean.centered
    observed = []

    def spy(x):
        if np.ndim(x) == 2:
            observed.append(np.asarray(x).copy())
        return original(x)

    monkeypatch.setattr(mean, "fit_unknown_mean_fgn", fit)
    monkeypatch.setattr(mean.ci, "fitted_fgn_samples", samples)
    monkeypatch.setattr(mean, "centered", spy)
    record(np.random.default_rng(277).normal(size=128), config)
    np.testing.assert_array_equal(observed[-1], np.arange(7 * 128).reshape(7, 128) + 9)


def test_unknown_model_failure_leaves_baselines_and_missing_pairs(config, monkeypatch):
    def fail(x):
        raise ValueError("injected")

    monkeypatch.setattr(mean, "fit_unknown_mean_fgn", fail)
    result = record(np.random.default_rng(4).normal(size=128), config)
    frame = mean.engine.interval_frame([result])
    assert not frame[frame.candidate == "unknown_centered_basic"].available.any()
    assert frame[frame.candidate != "unknown_centered_basic"].available.all()
    pairs = mean.engine.paired_comparisons(frame)
    assert pairs[pairs.candidate == "unknown_centered_basic"].n_missing_pairs.eq(1).all()


def test_mean_comparison_workload():
    config = json.loads(mean.DEFAULT_CONFIG.read_text())
    mean.validate(config)
    assert mean.workload(config) == {
        "cells": 21,
        "independent_records": 1344,
        "model_fits": 2688,
        "point_statistics": 8064,
        "offset_probe_statistics": 8064,
        "physical_bootstrap_records": 802368,
        "bootstrap_statistic_attempts": 4011840,
        "interval_rows": 26880,
    }


def scientific_records(path):
    records = [json.loads(line) for line in (path / "records.jsonl").read_text().splitlines()]
    for r in records:
        for key in ("point_seconds", "model_seconds", "elapsed_seconds"):
            r.pop(key)
        for pool in r["draw_pools"].values():
            pool.pop("elapsed_seconds")
    return records


def test_mean_runner_resume_and_frozen_config(config, tmp_path):
    resumed, whole = tmp_path / "resumed", tmp_path / "whole"
    assert mean.run(config, resumed, max_new_records=1)["completed_records"] == 1
    assert mean.run(config, resumed)["new_records"] == 1
    mean.run(config, whole)
    assert scientific_records(resumed) == scientific_records(whole)
    assert mean.run(config, resumed)["new_records"] == 0
    changed = copy.deepcopy(config)
    changed["global_seed"] += 1
    with pytest.raises(ValueError, match="Resume refused"):
        mean.run(changed, resumed)
    assert json.loads((resumed / "progress.json").read_text())["complete"]


def test_unknown_mean_model_and_points_do_not_use_benchmark_truth(config):
    x = np.random.default_rng(283).normal(size=128)
    a = record(x, config)
    b = mean.fit_record(
        x,
        {"record_id": "x", "sha256": "hash", "repetition": 0},
        {"family": "fGn", "parameter": 0.25, "n": 128},
        config,
    )
    assert a["points"] == b["points"]
    assert a["fitted_models"] == b["fitted_models"]
