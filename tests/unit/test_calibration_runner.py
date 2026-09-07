"""Shared input identity, honest denominators and checkpoint recovery."""

from __future__ import annotations

import copy
import json
import sqlite3

import numpy as np
import pytest
from benchmark_experiment.remediation import run_calibration as calibration


@pytest.fixture
def config():
    return {
        "schema_version": 1,
        "stage": "development",
        "seed_namespace": "software-test-v1",
        "global_seed": 457,
        "lengths": [64],
        "processes": {"fGn": [0.5], "AR1": [-0.5]},
        "repetitions": 3,
        "bootstrap_draws": 7,
        "nominal": 0.95,
        "block_divisors": [8, 4],
        "ci_methods": {"GPH": {"m": 8}},
    }


ROSTER = [("GPH", "GPH", {"m": 8, "n_bootstrap": 0})]


def scientific_rows(path):
    rows = [json.loads(line) for line in (path / "estimates.jsonl").read_text().splitlines()]
    for row in rows:
        row.pop("elapsed_seconds")
    return rows


def test_published_screen_workload():
    spec = json.loads(calibration.DEFAULT_CONFIG.read_text())
    calibration.validate_config(spec)
    assert calibration.workload(spec, calibration.configurations(calibration.ROOT), 256) == {
        "cells": 36,
        "independent_inputs": 9216,
        "point_fits": 175104,
        "ci_fits": 82944,
        "bootstrap_draws": 33094656,
    }


def test_input_prefix_method_order_and_stream_independence(config, tmp_path):
    cell = {"family": "ARFIMA", "parameter": -0.3, "n": 64}
    short, long = tmp_path / "short", tmp_path / "long"
    short.mkdir()
    long.mkdir()
    a, meta_a = calibration.input_pool(short, config, cell, 2)
    changed = copy.deepcopy(config)
    changed["ci_methods"] = {"Higuchi": {"k_max": 8, "input_representation": "increments"}}
    changed["repetitions"] = 9
    changed["lengths"] = [128, 64]
    changed["processes"] = {"ARFIMA": [-0.3], "AR1": [0.9]}
    b, meta_b = calibration.input_pool(long, changed, cell, 4)
    np.testing.assert_array_equal(a, b[:2])
    assert meta_a["records"] == meta_b["records"][:2]
    assert not a.flags.writeable
    assert calibration.record_seed(config, cell, 0, "input") != calibration.record_seed(
        config, cell, 0, "resampling"
    )
    changed["seed_namespace"] = "fresh-confirmation-stream"
    assert calibration.record_seed(config, cell, 0, "input") != calibration.record_seed(
        changed, cell, 0, "input"
    )


@pytest.mark.parametrize(
    "family,parameter", [("fGn", 0.2), ("fGn", 0.8), ("ARFIMA", -0.3), ("ARFIMA", 0.3)]
)
def test_cholesky_declared_covariance(family, parameter):
    n = 16
    cell = {"family": family, "parameter": parameter, "n": n}
    factor = calibration.covariance_factor(cell)
    if family == "fGn":
        k = np.arange(n)
        gamma = (
            np.abs(k - 1) ** (2 * parameter) - 2 * k ** (2 * parameter) + (k + 1) ** (2 * parameter)
        ) / 2
    else:
        # Independent Fourier quadrature, including negative d.
        from scipy.integrate import quad

        gamma = np.array(
            [
                quad(
                    lambda w, k=k: (2 * np.sin(w / 2)) ** (-2 * parameter) * np.cos(k * w),
                    0,
                    np.pi,
                    epsabs=1e-10,
                )[0]
                / np.pi
                for k in range(n)
            ]
        )
    expected = gamma[np.abs(np.arange(n)[:, None] - np.arange(n)[None, :])]
    np.testing.assert_allclose(factor @ factor.T, expected, atol=2e-9)


@pytest.mark.parametrize("phi", [-0.5, 0.8, 0.95])
def test_ar1_stationary_initial_covariance(config, monkeypatch, phi):
    n = 8
    cell = {"family": "AR1", "parameter": phi, "n": n}
    basis = iter(np.eye(n))

    class BasisRng:
        def normal(self, *, size):
            assert size == n
            return next(basis)

    monkeypatch.setattr(np.random, "default_rng", lambda seed: BasisRng())
    factor = np.column_stack([calibration.generate_record(config, cell, r, None) for r in range(n)])
    np.testing.assert_allclose(
        factor @ factor.T, phi ** np.abs(np.arange(n)[:, None] - np.arange(n)[None, :]), atol=1e-14
    )


def test_resume_equals_uninterrupted_and_completed_run_is_noop(config, tmp_path):
    interrupted, whole = tmp_path / "interrupted", tmp_path / "whole"
    first = calibration.run(config, interrupted, roster=ROSTER, max_new_fits=4)
    assert first == {"complete": False, "new_fits": 4, "total_fits": 4}
    resumed = calibration.run(config, interrupted, roster=ROSTER)
    assert resumed == {"complete": True, "new_fits": 14, "total_fits": 18}
    calibration.run(config, whole, roster=ROSTER)
    assert scientific_rows(interrupted) == scientific_rows(whole)
    before = (interrupted / "estimates.jsonl").read_bytes()
    assert calibration.run(config, interrupted, roster=ROSTER)["new_fits"] == 0
    assert before == (interrupted / "estimates.jsonl").read_bytes()


def test_resume_rejects_config_source_and_environment_drift(config, tmp_path, monkeypatch):
    calibration.run(config, tmp_path, roster=ROSTER, max_new_fits=1)
    changed = copy.deepcopy(config)
    changed["global_seed"] += 1
    with pytest.raises(ValueError, match="Resume refused"):
        calibration.run(changed, tmp_path, roster=ROSTER)
    original = calibration.run_identity
    for key in ("source_sha256", "environment"):

        def different(*args, key=key):
            value = original(*args)
            value[key] = {"changed": True}
            return value

        monkeypatch.setattr(calibration, "run_identity", different)
        with pytest.raises(ValueError, match="Resume refused"):
            calibration.run(config, tmp_path, roster=ROSTER)
    monkeypatch.setattr(calibration, "run_identity", original)


def test_input_corruption_rejected(config, tmp_path):
    calibration.run(config, tmp_path, roster=ROSTER, max_new_fits=1)
    path = next((tmp_path / "inputs").glob("*.npz"))
    with np.load(path, allow_pickle=False) as bundle:
        values, metadata = bundle["values"], bundle["metadata"]
    values[0, 0] += 1
    np.savez_compressed(path, values=values, metadata=metadata)
    with pytest.raises(ValueError, match="hash/seed mismatch"):
        calibration.run(config, tmp_path, roster=ROSTER)


def test_checkpoint_corruption_rejected(config, tmp_path):
    calibration.run(config, tmp_path, roster=ROSTER, max_new_fits=1)
    with sqlite3.connect(tmp_path / "checkpoints.sqlite") as connection:
        connection.execute("UPDATE fits SET payload = '{}' ")
    with pytest.raises(ValueError, match="checksum mismatch"):
        calibration.run(config, tmp_path, roster=ROSTER)


def test_failed_jobs_are_checkpointed_and_missing_counters_explicit(config, tmp_path, monkeypatch):
    class BrokenRegistry:
        def get(self, name):
            raise RuntimeError("injected failure")

    monkeypatch.setattr(calibration, "build_default_estimator_registry", BrokenRegistry)
    calibration.run(config, tmp_path, roster=ROSTER)
    rows = [json.loads(line) for line in (tmp_path / "estimates.jsonl").read_text().splitlines()]
    assert len(rows) == 18 and all(not r["valid"] for r in rows)
    table = calibration.summarize(rows, config)
    assert table.n_invalid.sum() == 18
    ci = table[table.phase == "ci"]
    assert ci.bootstrap_accounting_missing_fits.sum() == 12
    assert ci.ci_availability.eq(0).all()
    assert ci.conditional_coverage.isna().all()


def test_single_writer_lock_is_released(tmp_path):
    with (
        calibration.exclusive_run(tmp_path),
        pytest.raises(ValueError, match="Another calibration process"),
        calibration.exclusive_run(tmp_path),
    ):
        pytest.fail("Concurrent writer was allowed")
    with calibration.exclusive_run(tmp_path):
        pass


def test_method_order_does_not_change_scientific_results(config, tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    roster = [*ROSTER, ("GPH_m12", "GPH", {"m": 12, "n_bootstrap": 0})]
    calibration.run(config, a, roster=roster)
    calibration.run(config, b, roster=list(reversed(roster)))
    assert scientific_rows(a) == scientific_rows(b)


def test_coverage_denominators_do_not_drop_failures(config):
    row = {
        "cell": "test",
        "family": "fGn",
        "parameter": 0.5,
        "n": 64,
        "H_target": 0.5,
        "phase": "ci",
        "method": "GPH",
        "block_divisor": 8,
        "parameters": {"bootstrap_block_len": 8},
        "point": 0.5,
        "valid": True,
        "ci_low": 0.4,
        "ci_high": 0.6,
        "bootstrap_cis": [[0.95, 0.4, 0.6]],
        "elapsed_seconds": 1.0,
        "diagnostics": {},
    }
    rows = [
        row,
        {**row, "ci_low": 0.6, "ci_high": 0.8, "bootstrap_cis": [[0.95, 0.6, 0.8]]},
        {**row, "valid": False},
        {**row, "ci_low": None},
        {**row, "ci_low": 0.8, "ci_high": 0.3},
        {**row, "bootstrap_cis": [[0.8, 0.4, 0.6]]},
        {**row, "point": np.inf},
    ]
    result = calibration.summarize(rows, config).iloc[0]
    assert result.n_attempted == 7
    assert result.n_valid == 5
    assert result.n_available == 2
    assert result.n_covered == 1
    assert result.conditional_coverage == 0.5
    assert result.ci_availability == 2 / 7
    assert result.covered_per_attempt == 1 / 7


@pytest.mark.parametrize(
    "field,value",
    [
        ("stage", "confirmation"),
        ("repetitions", 0),
        ("bootstrap_draws", 0),
        ("lengths", [64, 64]),
        ("nominal", 0.8),
        ("block_divisors", [99]),
        ("processes", {"ARFIMA": [0.5]}),
        ("processes", {"fGn": [float("nan")]}),
        ("ci_methods", {"GHE": {"q": 1}}),
    ],
)
def test_invalid_design_rejected(config, field, value):
    config[field] = value
    with pytest.raises(ValueError):
        calibration.validate_config(config)
