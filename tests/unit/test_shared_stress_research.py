from __future__ import annotations

import copy
import csv
import json
import sqlite3
from dataclasses import replace

import numpy as np
import pandas as pd
import pytest
from benchmark_experiment.remediation import materialize_shared_stress as inputs
from benchmark_experiment.remediation import run_shared_stress as stress

from lrdbench.defaults import build_default_contamination_registry

shared = stress.shared


@pytest.fixture
def config():
    return json.loads(stress.DEFAULT_CONFIG.read_text(encoding="utf-8"))


@pytest.fixture
def source(config, tmp_path):
    config["processes"] = {"fGn": [0.5]}
    config["repetitions"] = 2
    config["summary"]["draws"] = 19
    folder = tmp_path / "source"
    folder.mkdir()
    source_config = {**config, "seed_namespace": "test-independent-clean-parents"}
    source_identity = {"config": source_config, "actual_repetitions": 2}
    config["clean_pool_identity_sha256"] = shared.digest(source_identity)
    shared.atomic_json(
        folder / "run.json",
        {"identity": source_identity, "identity_sha256": shared.digest(source_identity)},
    )
    shared.input_pool(folder, source_config, shared.cells(config)[0], 2)
    return folder


def edit_npz(path, callback):
    with np.load(path, allow_pickle=False) as bundle:
        values, metadata = bundle["values"], json.loads(str(bundle["metadata"]))
    callback(values, metadata)
    with path.open("wb") as handle:
        np.savez_compressed(handle, values=values, metadata=shared.canonical(metadata))


def test_declared_workload_and_point_only_roster(config):
    inputs.validate_config(config)
    assert stress.workload(config) == {
        "cells": 7,
        "independent_parents": 448,
        "contamination_conditions": 7,
        "descendants": 3136,
        "methods": 21,
        "point_fits": 75264,
        "within_record_interval_fits": 0,
    }
    assert all(row["params"]["n_bootstrap"] == 0 for row in stress.roster())
    assert sum(row["center"] for row in stress.roster()) == 2


def test_nullable_64bit_seeds_round_trip_without_float_coercion(tmp_path):
    seeds = [None, 7039943808006076389, 18446744073709551615]
    stress.export(
        tmp_path,
        {},
        [{"record_id": str(i), "contamination_seed": seed} for i, seed in enumerate(seeds)],
    )
    with (tmp_path / "input_index.csv").open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert [row["contamination_seed"] for row in rows] == ["", *map(str, seeds[1:])]


@pytest.mark.parametrize("index", range(7))
def test_production_contaminations_match_independent_equations_and_preserve_parent(config, index):
    x = np.random.default_rng(71).normal(size=512)
    x.setflags(write=False)
    meta = {"record_id": "p", "sha256": shared.array_hash(x), "input_seed": 1}
    parent = inputs.build_parent({"family": "fGn", "parameter": 0.75, "n": 512}, x, meta)
    condition = config["conditions"][index]
    child = inputs.apply_child(
        config, parent, meta, condition, build_default_contamination_registry()
    )
    expected = inputs.reference_values(x, condition, child.provenance.seed)
    np.testing.assert_allclose(child.values, expected, rtol=2e-14, atol=2e-14)
    assert shared.array_hash(parent.values) == meta["sha256"]
    assert child.truth.target_value == 0.75
    assert child.annotations["target_role"] == "latent_clean_recovery"
    assert child.provenance.created_at == ""
    assert not child.values.flags.writeable
    assert not np.shares_memory(child.values, parent.values)
    delta = child.values - x
    op, p = condition["operator"], condition["params"]
    if op == "constant_offset":
        np.testing.assert_allclose(delta, np.std(x) + 1e-12)
    elif op == "step_change":
        assert np.array_equal(child.values[:256], x[:256])
        np.testing.assert_allclose(delta[256:], np.std(x))
    elif op == "outliers":
        assert np.count_nonzero(delta) == 5
        np.testing.assert_allclose(np.abs(delta[delta != 0]), 8 * (np.std(x) + 1e-12))
    elif op in {"heavy_tail_noise", "polynomial_trend"}:
        np.testing.assert_allclose(np.std(delta), 0.5 * np.std(x), rtol=1e-10)
        if op == "polynomial_trend" and p["order"] == 2:
            assert not np.isclose(delta[0], delta[-1])  # t+t², not a pure quadratic.


def test_child_identity_excludes_labels_grid_order_and_summary_but_includes_inputs_and_version(
    config,
):
    parent = {"record_id": "p", "sha256": "a"}
    condition = config["conditions"][-1]
    original = inputs.child_identity(config, parent, condition, "0.1.0")
    changed = copy.deepcopy(config)
    changed["summary"]["seed"] += 1
    changed["conditions"].reverse()
    assert (
        inputs.child_identity(changed, parent, {**condition, "id": "renamed"}, "0.1.0") == original
    )
    assert inputs.child_identity(config, {**parent, "sha256": "b"}, condition, "0.1.0") != original
    assert inputs.child_identity(config, parent, condition, "0.2.0") != original
    assert (
        inputs.child_identity(
            config, parent, {**condition, "params": {"df": 3, "scale": 1}}, "0.1.0"
        )
        != original
    )


@pytest.mark.parametrize(
    "mutation", ["length", "duplicate", "step", "tail", "polynomial", "summary", "outliers"]
)
def test_invalid_scientific_designs_are_rejected(config, mutation):
    if mutation == "length":
        config["lengths"] = [256]
    elif mutation == "duplicate":
        config["conditions"].append({**config["conditions"][0], "id": "alias"})
    elif mutation == "step":
        config["conditions"][1]["params"]["position"] = 0.00001
    elif mutation == "tail":
        config["conditions"][-1]["params"]["df"] = 2
    elif mutation == "polynomial":
        config["conditions"][3]["params"]["order"] = 1.5
    elif mutation == "summary":
        config["summary"]["denominator_floor"] = float("nan")
    else:
        config["conditions"][2]["params"]["rate"] = 1.1
    with pytest.raises(ValueError):
        inputs.validate_config(config)


def test_materialization_is_idempotent_and_checks_values_even_with_updated_hash(
    config, source, tmp_path
):
    output = tmp_path / "materialized"
    output.mkdir()
    cell = shared.cells(config)[0]
    before = shared.file_hash(source / "inputs" / "fGn_0.5_n512.npz")
    a, metadata = inputs.materialize_cell(source, output, config, cell)
    path = output / "fGn_0.5_n512.npz"
    archive_hash = shared.file_hash(path)
    b, again = inputs.materialize_cell(source, output, config, cell)
    assert shared.file_hash(path) == archive_hash
    assert np.array_equal(a, b) and metadata == again
    assert shared.file_hash(source / "inputs" / path.name) == before

    def tamper(values, metadata):
        values[0, 1, 0] += 0.1
        metadata["records"][1]["sha256"] = shared.array_hash(values[0, 1])

    edit_npz(path, tamper)
    with pytest.raises(ValueError, match="equation replay"):
        inputs.materialize_cell(source, output, config, cell)


def test_materialization_checks_seed_provenance_and_upstream_integrity(config, source, tmp_path):
    output = tmp_path / "materialized"
    output.mkdir()
    cell = shared.cells(config)[0]
    inputs.materialize_cell(source, output, config, cell)
    path = output / "fGn_0.5_n512.npz"
    edit_npz(path, lambda values, meta: meta["records"][1]["provenance"].update(seed=12))
    with pytest.raises(ValueError, match="provenance mismatch"):
        inputs.materialize_cell(source, output, config, cell)
    edit_npz(
        source / "inputs" / path.name,
        lambda values, meta: meta["records"][0].update(sha256="corrupted"),
    )
    with pytest.raises(ValueError, match="parent hash"):
        inputs.parent_pool(source, config, cell)


def test_runner_resume_complete_summary_and_frozen_sources(config, source, tmp_path):
    config["conditions"] = config["conditions"][:2]
    resumed, whole = tmp_path / "resumed", tmp_path / "whole"
    assert stress.run(config, source, resumed, max_new_parents=1)["completed_parents"] == 1
    first = pd.read_csv(resumed / "record_checksums.csv").iloc[0].scientific_sha256
    with pytest.raises(ValueError, match="complete declared"):
        stress.summarize(config, resumed)
    assert stress.run(config, source, resumed)["new_parents"] == 1
    stress.run(config, source, whole)
    assert pd.read_csv(resumed / "record_checksums.csv").iloc[0].scientific_sha256 == first
    pd.testing.assert_frame_equal(
        pd.read_csv(resumed / "record_checksums.csv"), pd.read_csv(whole / "record_checksums.csv")
    )
    assert stress.run(config, source, resumed)["new_parents"] == 0
    stress.summarize(config, resumed)
    accounting = pd.read_csv(resumed / "parent_accounting.csv")
    assert accounting.parents_common_complete.eq(2).all()
    summary = pd.read_csv(resumed / "paired_summary.csv")
    centered_offset = summary[
        (summary.method.str.endswith("::centered"))
        & (summary.condition == "constant_offset_1sd")
        & (summary.metric == "absolute_error_inflation")
    ]
    np.testing.assert_allclose(centered_offset.value, 0, atol=1e-14)
    changed = copy.deepcopy(config)
    changed["global_seed"] += 1
    with pytest.raises(ValueError, match="Resume refused"):
        stress.run(changed, source, resumed)
    with sqlite3.connect(resumed / "checkpoint.sqlite") as db:
        db.execute("UPDATE completed SET sha256 = 'bad'")
    with pytest.raises(ValueError, match="payload hash"):
        stress.run(config, source, resumed)


def test_failures_remain_rows_and_estimators_receive_no_latent_truth(config, source):
    cell = shared.cells(config)[0]
    values, rows, _ = inputs.parent_pool(source, config, cell)
    meta = {**rows[0], "parent_id": rows[0]["record_id"], "condition": "clean"}

    class BrokenRegistry:
        def get(self, name):
            return lambda spec: self

        def fit(self, record):
            assert record.truth is None
            assert not record.values.flags.writeable
            raise RuntimeError("injected failure")

    result = stress.fit(BrokenRegistry(), cell, values[0], meta, stress.roster()[0])
    assert not result["valid"] and result["point"] is None
    assert result["failure_reason"] == "exception:RuntimeError:injected failure"


def test_pair_frame_masks_invalid_points_and_rejects_mismatched_truth():
    rows = [
        {
            "cell": "s",
            "parent_id": "p",
            "method": "m",
            "condition": c,
            "point": point,
            "valid": valid,
            "H_target": 0.5,
        }
        for c, point, valid in (("clean", 0.6, True), ("a", 0.7, True), ("b", 0.8, False))
    ]
    pairs = stress.pair_frame(pd.DataFrame(rows)).set_index("condition")
    assert pairs.loc["a", "stressed_error"] == pytest.approx(0.2)
    assert pd.isna(pairs.loc["b", "stressed_error"])
    assert pd.isna(pairs.loc["b", "signed_estimate_drift"])
    rows[-1]["H_target"] = 0.8
    with pytest.raises(ValueError, match="targets do not match"):
        stress.pair_frame(pd.DataFrame(rows))


def test_zero_outlier_rate_is_identity_and_child_is_not_a_step(config):
    x = np.arange(512, dtype=float)
    meta = {"record_id": "p", "sha256": shared.array_hash(x), "input_seed": 1}
    parent = inputs.build_parent({"family": "fGn", "parameter": 0.5, "n": 512}, x, meta)
    condition = {"id": "zero", "operator": "outliers", "params": {"rate": 0.0, "amplitude": 8.0}}
    child = inputs.apply_child(
        config, parent, meta, condition, build_default_contamination_registry()
    )
    assert np.array_equal(child.values, x)
    # A within-record step remains after sample centering, unlike a constant offset.
    condition = config["conditions"][1]
    step = inputs.apply_child(
        config,
        replace(parent, values=x.copy()),
        meta,
        condition,
        build_default_contamination_registry(),
    )
    assert not np.allclose(step.values - step.values.mean(), x - x.mean())
