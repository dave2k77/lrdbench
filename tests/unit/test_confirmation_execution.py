from __future__ import annotations

import copy
import hashlib
import json

import numpy as np
import pytest
from benchmark_experiment.remediation import confirmation_analysis as analysis
from benchmark_experiment.remediation import confirmation_store as store
from benchmark_experiment.remediation import run_confirmation as engine
from benchmark_experiment.remediation import summarize_confirmation as reporting


def get(result, metric, method="Higuchi", condition="clean", contrast=""):
    i = next(
        i
        for i, r in enumerate(result.rows)
        if (r["metric"], r["method"], r["condition"], r["contrast"])
        == (metric, method, condition, contrast)
    )
    return result.rows[i], result.draws[i]


def point_result(values, *, key="cell", methods=None):
    return analysis.point_summaries(
        np.asarray(values, float),
        np.ones_like(values, dtype=float),
        target=0,
        methods=methods or ["Higuchi", "Higuchi::centered"],
        conditions=["clean", "step"] if np.asarray(values).shape[1] == 2 else ["clean"],
        draws=199,
        seed=17,
        key=key,
    )


def test_parent_count_matrix_matches_literal_joint_resampling():
    x = np.array([[1, 10, 9], [3, 20, 17], [5, 30, 25]], float)
    point, draws = analysis.joint_means(x, draws=35, seed=17, key="example")
    seed = int.from_bytes(
        hashlib.sha256(b"lrdbench-confirmation-summary-v1:17:example").digest()[:8], "little"
    )
    indices = np.random.default_rng(seed).integers(0, 3, (35, 3))
    np.testing.assert_allclose(draws, x[indices].mean(axis=1), rtol=1e-15, atol=1e-15)
    np.testing.assert_allclose(point, x.mean(axis=0))
    np.testing.assert_allclose(draws[:, 1] - draws[:, 0], draws[:, 2])


def test_clean_and_stress_mean_removal_are_paired_differences_of_correct_quantities():
    points = np.array([[[1, 0.5], [4, 1]], [[3, 1.5], [5, 2]]])
    result, support = point_result(points)
    assert support["parents_common_complete"] == 2
    row, _ = get(result, "mae_difference", contrast="geometric_mean_removal_clean")
    assert row["value"] == -1
    row, _ = get(result, "absolute_error_inflation", condition="step")
    assert row["value"] == 2.5
    row, _ = get(
        result,
        "error_inflation_difference",
        condition="step",
        contrast="geometric_mean_removal_stress",
    )
    assert row["value"] == -2
    row, _ = get(
        result,
        "absolute_drift_difference",
        condition="step",
        contrast="geometric_mean_removal_stress",
    )
    assert row["value"] == -2
    row, _ = get(result, "paired_mae_ratio", condition="step")
    assert row["value"] == 4.5 / 2
    assert row["value"] != np.mean([4 / 1, 5 / 3])


def test_absolute_drift_does_not_substitute_absolute_error_inflation():
    result, _ = point_result([[[-1, -1], [1, 1]], [[-2, -2], [2, 2]]])
    assert get(result, "absolute_error_inflation", condition="step")[0]["value"] == 0
    assert get(result, "absolute_estimate_drift", condition="step")[0]["value"] == 3


def test_missing_method_excludes_parent_from_all_error_comparisons_but_not_validity():
    result, support = point_result([[[1, 1], [2, 2]], [[3, 3], [4, np.nan]], [[5, 5], [6, 6]]])
    assert support["excluded_parent_indices"] == [1]
    assert len(support["missing_or_invalid"]) == 1
    for method in ["Higuchi", "Higuchi::centered"]:
        assert get(result, "mae", method)[0]["parents_used"] == 2
    row, _ = get(result, "validity", "Higuchi::centered", "step")
    assert row["value"] == 2 / 3 and row["denominator"] == 3
    row, _ = get(result, "validity_loss", "Higuchi::centered", "step")
    assert row["value"] == pytest.approx(1 / 3)


def test_empty_common_support_retains_failure_accounting_and_unavailable_errors():
    result, support = point_result([[[1, np.nan]], [[np.nan, 2]]])
    row, samples = get(result, "mae")
    assert support["parents_common_complete"] == 0
    assert np.isnan(row["value"]) and np.isnan(samples).all()
    assert row["parents_attempted"] == 2 and row["parents_used"] == 0


def test_domain_ratios_use_weighted_maes_and_rmse_uses_weighted_mse():
    a, _ = point_result([[[1, 1], [2, 2]], [[1, 1], [2, 2]]], key="a")
    b, _ = point_result([[[9, 9], [9, 9]], [[9, 9], [9, 9]]], key="b")
    result = analysis.aggregate_groups(iter([a, b]))
    row, samples = get(result, "paired_mae_ratio", condition="step")
    assert row["value"] == 11 / 10
    np.testing.assert_allclose(samples, 11 / 10)
    assert row["domain_cells"] == 2
    assert get(result, "rmse")[0]["value"] == np.sqrt(41)


def test_domain_never_drops_or_renormalizes_an_empty_cell():
    a, _ = point_result([[[1, 1]], [[2, 2]]])
    b, _ = point_result([[[np.nan, np.nan]], [[np.nan, np.nan]]])
    result = analysis.aggregate_groups([a, b])
    row, samples = get(result, "mae")
    assert np.isnan(row["value"]) and np.isnan(samples).all()
    assert row["cell_weight"] == 0.5 and row["parents_attempted"] == 4


def interval_result():
    labels = [("Higuchi", "cbc_raw_basic"), ("Higuchi", "cbc_centered_basic")]
    low = np.array([[0, 0], [0, 0], [0, np.nan], [2, np.nan]], float)
    high = np.array([[1, 2], [1, 3], [1, np.nan], [3, np.nan]], float)
    return analysis.interval_summaries(
        low,
        high,
        np.isfinite(low),
        target=0.5,
        labels=labels,
        draws=199,
        seed=7,
        key="interval",
        model_boundary=[0, 1, 0, 0],
        model_available=[1, 1, 1, 0],
    )


def test_interval_coverage_keeps_unavailable_as_misses_and_distinguishes_conditional():
    result, support = interval_result()
    unconditional, _ = get(result, "unconditional_coverage", condition="cbc_centered_basic")
    conditional, _ = get(result, "conditional_coverage", condition="cbc_centered_basic")
    assert unconditional["value"] == 0.5 and unconditional["denominator"] == 4
    assert conditional["value"] == 1 and conditional["denominator"] == 2
    assert support["parents_attempted"] == 4 and len(support["intervals_unavailable"]) == 2


def test_paired_coverage_uses_all_parents_width_uses_explicit_common_support():
    result, _ = interval_result()
    condition = "cbc_centered_basic_minus_cbc_raw_basic"
    row, _ = get(result, "coverage_difference", condition=condition, contrast="interval_centering")
    assert row["value"] == -0.25 and row["parents_used"] == 4
    row, samples = get(
        result, "mean_width_difference", condition=condition, contrast="interval_centering"
    )
    assert row["value"] == 1.5 and row["parents_used"] == 2
    assert row["parents_excluded"] == 2
    assert np.isnan(samples).any() and np.isnan(row["ci_low"])
    assert row["invalid_draws"] == int(np.isnan(samples).sum())


@pytest.mark.parametrize("success", [0, 4])
def test_zero_and_all_event_cells_report_wilson_uncertainty_not_zero_mcse(success):
    labels = [("Higuchi", "cbc_raw_basic")]
    low = np.zeros((4, 1)) if success else np.ones((4, 1)) * 2
    result, _ = analysis.interval_summaries(
        low,
        low + 1,
        np.ones((4, 1), bool),
        target=0.5,
        labels=labels,
        draws=19,
        seed=1,
        key="boundary",
    )
    row, _ = get(result, "unconditional_coverage", condition="cbc_raw_basic")
    assert row["ci_high"] > row["ci_low"] and np.isnan(row["mcse"])
    assert row["successes"] == success and row["interval_method"] == "Wilson_95"


def test_available_interval_with_invalid_endpoints_is_rejected():
    with pytest.raises(ValueError, match="ordered finite"):
        analysis.interval_summaries(
            [[1]],
            [[0]],
            [[True]],
            target=0.5,
            labels=[("Higuchi", "cbc_raw_basic")],
            draws=9,
            seed=1,
            key="x",
        )


def test_all_fifteen_planned_interval_contrasts_are_present():
    labels = [
        (method, candidate)
        for method in engine.intervals.METHODS
        for candidate in engine.intervals.CANDIDATES
    ]
    pairs = analysis.interval_pairs(labels)
    assert len(pairs) == 15
    assert sum(p[1] == "interval_centering" for p in pairs) == 6
    assert sum(p[1] == "interval_construction" for p in pairs) == 6
    assert sum(p[1] == "interval_model" for p in pairs) == 3


def populate_pending(output, name="chunk"):
    folder = store.begin(output, name)
    store.write_arrays(folder / "signals.npz", values=np.arange(8).reshape(2, 4))
    store.write_arrays(folder / "draws.npz", values=np.array([[1, np.nan, 3]]))
    store.write_points(
        folder / "points.jsonl.gz",
        [
            {
                "seed": 18446744073709551615,
                "point": 0.12345678901234567,
                "valid": False,
                "diagnostics": {"x": None},
                "text": "μ",
            }
        ],
    )
    store.write_json_gz(folder / "metadata.json.gz", {"seed": 18446744073709551615})
    return folder


def test_archive_roundtrip_preserves_large_seeds_nulls_unicode_and_aligned_nans(tmp_path):
    populate_pending(tmp_path)
    store.seal(tmp_path, "chunk", identity_sha="identity", counts={"parents": 2})
    folder = tmp_path / "chunks/chunk"
    row = next(store.read_points(folder))
    assert row["seed"] == 18446744073709551615 and row["text"] == "μ"
    assert row["diagnostics"] == {"x": None} and row["point"] == 0.12345678901234567
    with np.load(folder / "draws.npz", allow_pickle=False) as bundle:
        np.testing.assert_allclose(bundle["values"], [[1, np.nan, 3]], equal_nan=True)


@pytest.mark.parametrize("stage", ["before_commit", "after_commit"])
def test_interruptions_never_expose_partial_committed_chunks(tmp_path, stage):
    populate_pending(tmp_path)

    def interrupt(where, chunk_id):
        if where == stage:
            raise RuntimeError("injected interruption")

    with pytest.raises(RuntimeError, match="injected"):
        store.seal(tmp_path, "chunk", identity_sha="id", counts={"parents": 2}, fault=interrupt)
    folder = tmp_path / "chunks/chunk"
    if stage == "after_commit":
        assert store.verify(folder, "id")["counts"]["parents"] == 2
        with pytest.raises(ValueError, match="cannot be overwritten"):
            store.begin(tmp_path, "chunk")
    else:
        assert not folder.exists()
        populate_pending(tmp_path)
        assert len(list((tmp_path / "abandoned").iterdir())) == 1
        store.seal(tmp_path, "chunk", identity_sha="id", counts={"parents": 2})
        store.verify(folder, "id")


@pytest.mark.parametrize("mutation", ["payload", "identity", "missing"])
def test_corrupt_or_wrong_run_chunks_are_refused(tmp_path, mutation):
    populate_pending(tmp_path)
    store.seal(tmp_path, "chunk", identity_sha="id", counts={"parents": 2})
    folder = tmp_path / "chunks/chunk"
    if mutation == "payload":
        with (folder / "signals.npz").open("ab") as handle:
            handle.write(b"corrupt")
    if mutation == "missing":
        (folder / "signals.npz").rename(folder / "unexpected.npz")
    with pytest.raises(ValueError):
        store.verify(folder, "different" if mutation == "identity" else "id")


def test_archive_path_escape_is_rejected(tmp_path):
    with pytest.raises(ValueError, match="inside"):
        store.inside(tmp_path, tmp_path / "../outside")


def test_executor_plan_preserves_frozen_counts_and_separates_rehearsal():
    frozen = engine.load_lock()
    assert frozen["sha256"] == "b5b9399d284e3fae8135050aeac5c8bc0a02ab36b4f0a6d15041f55a497681bb"
    full = engine.chunk_plan(frozen)
    small = engine.cell_plan(frozen, True)
    assert sum(c["stop"] - c["start"] for c in full) == 66000
    assert len(full) == 2079
    assert sum(c["accuracy_parents"] for c in small) == 66
    assert sum(c["interval_parents"] for c in small) == 20
    assert sum(c["stress_parents"] for c in small) == 28
    assert (
        engine.design.data_config(frozen["design"]["protocol"], rehearsal=True)["seed_namespace"]
        != engine.design.data_config(frozen["design"]["protocol"])["seed_namespace"]
    )


def test_production_release_cannot_be_reused_after_runtime_change(tmp_path):
    (tmp_path / "evidence.json").write_text("{}", encoding="utf-8")
    release = {
        "status": "validated_for_fixed_confirmation",
        "runtime_sha256": "expected",
        "evidence_sha256": {"evidence.json": engine.shared.file_hash(tmp_path / "evidence.json")},
    }
    path = tmp_path / "release.json"
    path.write_text(json.dumps(release), encoding="utf-8")
    engine.check_release({"runtime_sha256": "expected"}, path)
    with pytest.raises(ValueError, match="exact sources"):
        engine.check_release({"runtime_sha256": "changed"}, path)


def test_runner_resume_preserves_committed_bytes_and_rejects_changed_identity(
    tmp_path, monkeypatch
):
    frozen = engine.load_lock()
    plan = engine.chunk_plan(frozen, True)[:2]
    monkeypatch.setattr(engine, "chunk_plan", lambda *args: plan)
    first = engine.run(tmp_path, rehearsal=True, max_new_chunks=1)
    assert not first["complete"] and first["confirmation_parents"] == 0
    before = {
        p.relative_to(tmp_path).as_posix(): (engine.shared.file_hash(p), p.stat().st_mtime_ns)
        for p in (tmp_path / "chunks").rglob("*")
        if p.is_file()
    }
    second = engine.run(tmp_path, rehearsal=True, max_new_chunks=0)
    assert first == second
    assert before == {
        p.relative_to(tmp_path).as_posix(): (engine.shared.file_hash(p), p.stat().st_mtime_ns)
        for p in (tmp_path / "chunks").rglob("*")
        if p.is_file()
    }
    with pytest.raises(ValueError, match="every declared chunk"):
        reporting.read_run(tmp_path)
    completed = engine.run(tmp_path, rehearsal=True)
    assert completed["complete"] and completed["counts"]["parents"] == 4
    original = engine.run_identity

    def changed(*args, **kwargs):
        value = copy.deepcopy(original(*args, **kwargs))
        value["environment"]["python"] = "changed"
        return value

    monkeypatch.setattr(engine, "run_identity", changed)
    with pytest.raises(ValueError, match="sources or environment changed"):
        engine.run(tmp_path, rehearsal=True)


def test_summary_roundtrip_keeps_labels_and_unavailable_draws(tmp_path):
    result, support = interval_result()
    reporting.write_group(tmp_path, result, support, {"scope": "test"})
    restored = reporting.read_group(tmp_path)
    np.testing.assert_allclose(restored.matrix(), result.matrix(), equal_nan=True)
    assert [(r["condition"], r["contrast"]) for r in restored.rows] == [
        (r["condition"], r["contrast"]) for r in result.rows
    ]


def test_real_interval_chunk_loads_all_attempts_and_model_boundary_flags(tmp_path, monkeypatch):
    frozen = engine.load_lock()
    spec = next(s for s in engine.chunk_plan(frozen, True) if s["cell"]["cell"] == "fGn_0.5_n512")
    monkeypatch.setattr(engine, "chunk_plan", lambda *args: [spec])
    completed = engine.run(tmp_path, rehearsal=True)
    assert completed["counts"]["interval_rows"] == 32
    assert completed["counts"]["statistic_attempts"] == 2 * 9 * 1999
    data = reporting.load_cell(tmp_path, spec["cell"], [spec], completed["run_identity_sha256"])
    assert data["available"].shape == (2, 16)
    assert data["model_available"].all() and data["available"].all()
    assert data["points"].shape == (2, 24, 21)
