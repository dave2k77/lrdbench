from __future__ import annotations

import copy
import json

import numpy as np
import pandas as pd
import pytest
from benchmark_experiment.remediation import compile_confirmation_protocol as design
from benchmark_experiment.remediation import confirmation_batch as batch
from benchmark_experiment.remediation import confirmation_intervals as ci
from benchmark_experiment.remediation import profile_confirmation as profile

from lrdbench.defaults import build_default_estimator_registry


@pytest.fixture
def protocol():
    return design.load_protocol()


def test_protocol_counts_do_not_count_descendants_or_subsets_as_new_parents(protocol):
    design.validate(protocol)
    w = design.workload(protocol)
    assert w["accuracy_cells"] == 33 and w["independent_clean_parents"] == 66000
    assert w["stress_parent_subset"] == 7000 and w["interval_parent_subset"] == 15500
    assert w["contamination_conditions"] == 23 and w["descendants"] == 161000
    assert w["clean_point_fits"] == 1386000 and w["stressed_point_fits"] == 3381000
    assert w["total_point_fits"] == 4767000 and w["interval_rows"] == 248000
    assert w["physical_bootstrap_records"] == 61969000
    assert w["bootstrap_statistic_attempts"] == 278860500
    assert not w["descendants_and_interval_subsets_add_independent_parents"]


def test_cell_selection_and_precision_are_explicit(protocol):
    table = design.cell_table(protocol)
    assert table.accuracy_parents.eq(2000).all()
    assert table.interval_role.eq("core").sum() == 7
    assert table.interval_role.eq("length_sensitivity").sum() == 3
    assert table.stress_parents.gt(0).sum() == 14
    assert (table.interval_parents <= table.accuracy_parents).all()
    p = design.precision_table(protocol)
    core = p[p.role.eq("interval_core") & p.assumed_event_probability.eq(0.95)].iloc[0]
    assert core.mcse == pytest.approx(0.004873397172404484)
    worst = p[p.role.eq("interval_core") & p.assumed_event_probability.eq(0.5)].iloc[0]
    assert worst.mcse == pytest.approx(1 / np.sqrt(8000))


@pytest.mark.parametrize(
    "mutation",
    ["reuse", "subset", "overlap", "precision", "draws", "mean", "signal", "step", "stage"],
)
def test_inconsistent_or_leaking_designs_are_rejected(protocol, mutation):
    if mutation == "reuse":
        protocol["randomness"]["confirmation_namespace"] = "lrdbench-mean-candidates-v1"
    elif mutation == "subset":
        protocol["stress"]["repetitions"] = 2001
    elif mutation == "overlap":
        protocol["intervals"]["length_sensitivity"]["lengths"] = [512]
    elif mutation == "precision":
        protocol["intervals"]["core"]["repetitions"] = 1000
    elif mutation == "draws":
        protocol["intervals"]["bootstrap_draws"] = 199
    elif mutation == "mean":
        protocol["intervals"]["model"] = "known_zero_mean"
    elif mutation == "signal":
        protocol["signal"] = "EEG_envelope"
    elif mutation == "step":
        protocol["stress"]["step_positions"] = [0.0, 0.5]
    else:
        protocol["execution"]["status"] = "approved_for_confirmation"
    with pytest.raises(ValueError):
        design.validate(protocol)


def test_compile_is_reproducible_refuses_changed_or_corrupt_lock_and_never_generates(
    protocol, tmp_path, monkeypatch
):
    def unexpected(*args, **kwargs):
        raise AssertionError(
            "Compiling a protocol must not generate or inspect confirmation signals"
        )

    monkeypatch.setattr(design.shared, "generate_record", unexpected)
    first = design.compile_protocol(protocol, tmp_path)
    assert first == design.compile_protocol(copy.deepcopy(protocol), tmp_path)
    assert first["confirmation_inputs_generated"] == 0
    lock = json.loads((tmp_path / "scientific_design_lock.json").read_text(encoding="utf-8"))
    assert lock["design"]["seed_reservation"]["clean_seed_count"] == 66000
    assert lock["design"]["seed_reservation"]["no_rehearsal_or_interval_seed_collisions"]
    changed = copy.deepcopy(protocol)
    changed["randomness"]["global_seed"] += 1
    with pytest.raises(ValueError, match="frozen scientific design"):
        design.compile_protocol(changed, tmp_path)
    lock["design"]["status"] = "tampered"
    (tmp_path / "scientific_design_lock.json").write_text(json.dumps(lock), encoding="utf-8")
    with pytest.raises(ValueError, match="corrupted"):
        design.compile_protocol(protocol, tmp_path)


@pytest.mark.parametrize("n", [512, 1024, 2048])
def test_resolved_settings_preserve_all_public_point_results(n):
    x = np.random.default_rng(128 + n).normal(size=n)
    cell = {"family": "fGn", "parameter": 0.5, "n": n}
    meta = {
        "record_id": "p",
        "parent_id": "p",
        "condition": "clean",
        "sha256": design.shared.array_hash(x),
        "input_seed": 1,
        "resampling_seed": 2,
        "repetition": 0,
    }
    registry = build_default_estimator_registry()
    resolved = {r["method"]: r for r in design.point_settings(n)}
    for setting in design.stress.roster():
        old = design.stress.fit(registry, cell, x, meta, setting)
        explicit = design.stress.fit(registry, cell, x, meta, resolved[setting["method"]])
        assert old["valid"] and explicit["valid"]
        assert old["point"] == pytest.approx(explicit["point"], abs=1e-14)
        if setting["base"] in {"GPH", "Higuchi", "GHE"} and setting["method"] != "GPH::wider_band":
            y = x - x.mean() if setting["center"] else x
            method = "GPH::narrow_band" if setting["base"] == "GPH" else setting["base"]
            assert ci.statistic(y, method) == pytest.approx(explicit["point"], abs=1e-14)
    assert resolved["GHE"]["params"]["h_max"] == (n + 1) // 8
    assert len(resolved["WaveletOLS::conservative_band"]["retained_wavelet_levels"]) >= 3


def test_aligned_draws_count_failures_without_shifting_later_draws(monkeypatch):
    def injected(x, method):
        if x[0] == 1:
            raise ValueError("injected")
        return np.nan if x[0] == 2 else x[0]

    monkeypatch.setattr(ci, "statistic", injected)
    values, counts = ci.evaluate(np.arange(5)[:, None], "unused")
    np.testing.assert_allclose(values, [0, np.nan, np.nan, 3, 4], equal_nan=True)
    assert (counts["attempted"], counts["used"], counts["invalid"], counts["failed"]) == (
        5,
        3,
        1,
        1,
    )
    interval, reason = ci.aligned_interval(
        0.5, values, center=0.5, construction="basic", requested=5
    )
    assert interval is None and reason == "incomplete_or_nonfinite_bootstrap_draws"


def test_interval_construction_uses_fitted_target_and_complete_draws():
    values = np.array([0.1, 0.3, 0.4, 0.5, 0.8])
    actual, reason = ci.aligned_interval(0.7, values, center=0.6, construction="basic", requested=5)
    lower, upper = np.quantile(values, [0.025, 0.975])
    np.testing.assert_allclose(actual, [1.3 - upper, 1.3 - lower])
    assert reason is None
    assert (
        ci.aligned_interval(0.7, values, center=0.6, construction="basic", requested=6)[0] is None
    )


def test_interval_kernel_counts_separates_contrasts_and_reproduces():
    x = np.random.default_rng(940).normal(size=512)
    a = ci.fit_record(x, seeds={"cbc": 1, "fgn": 2}, draws=9, prefixes=[5, 9])
    b = ci.fit_record(x, seeds={"cbc": 1, "fgn": 2}, draws=9, prefixes=[5, 9])
    assert a["intervals"] == b["intervals"]
    assert len(a["intervals"]) == 32
    assert sum(pool["generated_records"] for pool in a["pools"].values()) == 18
    assert (
        sum(c["attempted"] for pool in a["pools"].values() for c in pool["accounting"].values())
        == 81
    )
    assert all(row["available"] for row in a["intervals"])
    frame = pd.DataFrame(a["intervals"])
    assert set(frame.candidate) == {*ci.CANDIDATES, "gph_normal_raw"}
    for method in ci.METHODS:
        for treatment in ("raw", "centered"):
            rows = frame[
                frame.method.eq(method)
                & frame.candidate.isin([f"cbc_{treatment}_percentile", f"cbc_{treatment}_basic"])
                & frame.draws.eq(9)
            ]
            assert rows.point.nunique() == 1


def test_model_failure_keeps_block_and_normal_comparators(monkeypatch):
    def fail(x):
        raise ValueError("injected model failure")

    monkeypatch.setattr(ci.mean, "fit_unknown_mean_fgn", fail)
    result = ci.fit_record(
        np.random.default_rng(44).normal(size=512), seeds={"cbc": 1, "fgn": 2}, draws=9
    )
    frame = pd.DataFrame(result["intervals"])
    assert not frame[frame.candidate.eq("unknown_fgn_centered_basic")].available.any()
    assert frame[~frame.candidate.eq("unknown_fgn_centered_basic")].available.all()
    assert result["pools"]["fgn"]["generated_records"] == 0


def test_rehearsal_is_separate_and_workload_includes_both_streams(protocol):
    a, b = design.data_config(protocol), design.data_config(protocol, rehearsal=True, repetitions=2)
    assert a["seed_namespace"] != b["seed_namespace"]
    assert profile.profile_workload(protocol) == {
        "clean_parents": 66,
        "clean_point_fits": 1386,
        "stress_descendants": 644,
        "stressed_point_fits": 13524,
        "interval_parents": 12,
        "interval_model_fits": 24,
        "physical_bootstrap_records": 143952,
        "bootstrap_statistic_attempts": 647784,
        "confirmation_inputs": 0,
    }


@pytest.mark.parametrize("n", [512, 1024, 2048])
@pytest.mark.parametrize("method", ci.METHODS)
def test_batched_statistics_match_scalar_across_offsets_steps_trends_and_scales(n, method):
    x = np.random.default_rng(n + 333).normal(size=(8, n))
    x[1] += 2
    x[2, n // 2 :] += 3
    x[3] += np.linspace(-4, 4, n)
    x[4, ::13] += 10
    x[5] *= 1e-120
    x[6] *= 1e120
    x[7] = np.cumsum(x[7])
    before = x.copy()
    expected = np.array([ci.statistic(row, method) for row in x])
    for size in (1, 3, 64):
        actual, counts = batch.evaluate(x, method, ci.statistic, batch_size=size)
        np.testing.assert_allclose(actual, expected, rtol=2e-12, atol=2e-13)
        assert counts["used"] == 8 and counts["invalid"] == counts["failed"] == 0
    assert np.array_equal(x, before)


def test_batched_degenerate_rows_preserve_validity_and_aligned_failures():
    x = np.random.default_rng(384).normal(size=(5, 512))
    x[1] = 0
    x[3, 0] = np.nan
    for method in ci.METHODS:
        expected = np.array([ci.statistic(row, method) for row in x], dtype=float)
        actual, counts = batch.evaluate(x, method, ci.statistic)
        np.testing.assert_allclose(actual, expected, rtol=2e-12, atol=2e-13, equal_nan=True)
        assert counts["attempted"] == 5 and counts["invalid"] == 2 and counts["used"] == 3
