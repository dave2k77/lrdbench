from __future__ import annotations

import hashlib

import numpy as np
import pandas as pd
import pytest
from benchmark_experiment.remediation.paired_summary import summarize_paired_errors


@pytest.fixture
def example():
    rows = []
    for stratum, parents, clean, stressed in (
        ("s1", ["a", "b"], [1, 3], [2, 3]),
        ("s2", ["c", "d", "e"], [4, 4, 4], [8, 8, 8]),
    ):
        for parent, c, s in zip(parents, clean, stressed, strict=True):
            for method, multiplier in (("A", 1), ("B", 2)):
                for condition, severity in (("mild", 1), ("severe", 3)):
                    rows.append(
                        {
                            "stratum": stratum,
                            "parent_id": parent,
                            "method": method,
                            "condition": condition,
                            "clean_error": c * multiplier,
                            "stressed_error": s * multiplier * severity,
                        }
                    )
    options = {
        "methods": ["A", "B"],
        "conditions": ["mild", "severe"],
        "parents_by_stratum": {"s1": ["a", "b"], "s2": ["c", "d", "e"]},
        "stratum_weights": {"s1": 0.2, "s2": 0.8},
        "draws": 99,
        "seed": 777,
    }
    return pd.DataFrame(rows), options


def test_paired_summary_uses_fixed_weights_and_ratio_of_maes(example):
    data, options = example
    summary, accounting, draws = summarize_paired_errors(data, **options)
    group = summary[(summary.method == "A") & (summary.condition == "mild")].set_index("metric")
    assert group.loc["absolute_error_inflation", "value"] == pytest.approx(6.9 - 3.6)
    assert group.loc["paired_mae_ratio", "value"] == pytest.approx(6.9 / 3.6)
    assert group.loc["paired_mae_ratio", "value"] != pytest.approx(0.2 * 1.25 + 0.8 * 2)
    assert group.clean_mae.eq(3.6).all()
    assert accounting.parents_common_complete.tolist() == [2] * 4 + [3] * 4
    assert len(draws) == 99 * 2 * 2 * 2


def test_each_bootstrap_draw_preserves_methods_and_descendants_together(example):
    data, options = example
    _, _, draws = summarize_paired_errors(data, **options)
    ratio = draws[draws.metric == "paired_mae_ratio"].pivot(
        index="draw", columns=["method", "condition"], values="value"
    )
    np.testing.assert_allclose(ratio["A", "mild"], ratio["B", "mild"], atol=1e-14)
    np.testing.assert_allclose(ratio["A", "severe"], 3 * ratio["A", "mild"], atol=1e-14)
    # Reference uses a complete single index draw, independent of chunking.
    key = b"lrdbench-paired-summary-v1:777:s1"
    rng = np.random.default_rng(int.from_bytes(hashlib.sha256(key).digest()[:8], "little"))
    indices = rng.integers(0, 2, size=(99, 2))
    c = 0.2 * np.array([1, 3])[indices].mean(axis=1) + 0.8 * 4
    s = 0.2 * np.array([2, 3])[indices].mean(axis=1) + 0.8 * 8
    np.testing.assert_allclose(ratio["A", "mild"], s / c, atol=1e-14)


def test_order_and_resampling_prefix_are_stable(example):
    data, options = example
    a = summarize_paired_errors(data, **options)
    reordered = {
        **options,
        "methods": ["B", "A"],
        "conditions": ["severe", "mild"],
        "parents_by_stratum": {"s2": ["e", "d", "c"], "s1": ["b", "a"]},
    }
    b = summarize_paired_errors(data.sample(frac=1, random_state=31), **reordered)
    for left, right in zip(a, b, strict=True):
        pd.testing.assert_frame_equal(left, right)
    longer = summarize_paired_errors(data, **{**options, "draws": 117})[2]
    pd.testing.assert_frame_equal(a[2], longer[longer.draw < 99].reset_index(drop=True))


def test_missing_pair_and_wholly_missing_parent_are_counted_on_common_support(example):
    data, options = example
    options["parents_by_stratum"]["s2"].append("lost")
    data = data[~((data.parent_id == "a") & (data.method == "B") & (data.condition == "severe"))]
    summary, counts, _ = summarize_paired_errors(data, **options)
    assert counts[counts.stratum == "s2"].parents_attempted.eq(4).all()
    assert counts[counts.stratum == "s2"].pairs_missing.eq(1).all()
    assert counts[counts.stratum == "s1"].parents_common_complete.eq(1).all()
    assert counts.pairs_missing.sum() == 5
    assert summary.value.notna().all()
    assert summary.ci_low.isna().all()
    assert summary.attempted_draws.eq(0).all()
    assert summary.unavailable_reason.eq("fewer_than_two_common_parents_in_a_stratum").all()


def test_empty_common_stratum_is_not_removed_or_reweighted(example):
    data, options = example
    data.loc[(data.stratum == "s1") & (data.method == "B"), "stressed_error"] = np.nan
    summary, counts, draws = summarize_paired_errors(data, **options)
    assert summary.value.isna().all() and draws.empty
    assert summary.unavailable_reason.eq("no_common_complete_parent_in_a_stratum").all()
    assert counts[counts.stratum == "s1"].parents_common_complete.eq(0).all()


def test_zero_denominators_are_unavailable_draws_not_extreme_ratios():
    data = pd.DataFrame(
        {
            "stratum": "s",
            "parent_id": p,
            "method": "A",
            "condition": "c",
            "clean_error": c,
            "stressed_error": c + 1,
        }
        for p, c in (("a", 0), ("b", 2))
    )
    summary, _, draws = summarize_paired_errors(
        data,
        methods=["A"],
        conditions=["c"],
        parents_by_stratum={"s": ["a", "b"]},
        stratum_weights={"s": 1},
        draws=499,
        seed=23,
    )
    ratio = summary[summary.metric == "paired_mae_ratio"].iloc[0]
    assert ratio.invalid_draws > 0
    assert ratio.attempted_draws == ratio.used_draws + ratio.invalid_draws == 499
    assert np.isfinite(draws.value.dropna()).all()
    ratio_draws = draws[draws.metric == "paired_mae_ratio"]
    assert ratio_draws.value.isna().sum() == ratio.invalid_draws
    reference = np.quantile(ratio_draws.value.dropna(), [0.025, 0.975])
    np.testing.assert_allclose([ratio.ci_low, ratio.ci_high], reference)
    inflation = summary[summary.metric == "absolute_error_inflation"].iloc[0]
    assert inflation.bootstrap_se == 0  # Every paired difference is exactly one.


def test_bootstrap_can_be_disabled_without_losing_point_summary(example):
    data, options = example
    summary, _, draws = summarize_paired_errors(data, **{**options, "draws": 0})
    assert summary.value.notna().all() and draws.empty
    assert summary.unavailable_reason.eq("bootstrap_disabled").all()


@pytest.mark.parametrize(
    "damage",
    [
        "duplicate",
        "clean_disagrees",
        "negative_error",
        "unknown_parent",
        "bad_weight",
        "reused_parent",
    ],
)
def test_design_errors_fail_explicitly(example, damage):
    data, options = example
    if damage == "duplicate":
        data = pd.concat([data, data.iloc[[0]]])
    elif damage == "clean_disagrees":
        data.loc[0, "clean_error"] = 0
    elif damage == "negative_error":
        data.loc[0, "stressed_error"] = -1
    elif damage == "unknown_parent":
        data.loc[0, "parent_id"] = "unexpected"
    elif damage == "bad_weight":
        options["stratum_weights"]["s1"] = 0.4
    elif damage == "reused_parent":
        options["parents_by_stratum"]["s2"].append("a")
    with pytest.raises(ValueError):
        summarize_paired_errors(data, **options)
