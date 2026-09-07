"""Joint parent bootstrap for research summaries of paired absolute errors.

This research helper is not wired into the public evaluator or CSV contract.
It requires an explicit design and reports performance conditional on common
complete parents across all declared methods and contamination conditions.
"""

from __future__ import annotations

import hashlib

import numpy as np
import pandas as pd


def summarize_paired_errors(
    pairs,
    *,
    methods,
    conditions,
    parents_by_stratum,
    stratum_weights,
    draws,
    seed,
    nominal=0.95,
    denominator_floor=1e-12,
):
    """Return summary, parent-accounting, and joint draw tables.

    Required columns: stratum, parent_id, method, condition, clean_error,
    stressed_error. Errors are nonnegative absolute errors against the same
    declared latent clean target. Missing rows/nonfinite errors are incomplete.
    The complete parent index is required, including parents with no result rows.
    A parent is retained only if every declared method-condition pair is finite.
    This common support is explicit; failures must also be reported separately.

    For each stratum, sample its retained parent IDs once per bootstrap draw and
    carry all methods/descendants together. Fixed stratum weights combine MAEs.
    Recompute the ratio of weighted MAEs inside every draw; never bootstrap
    per-record ratios or renormalize the weights after missingness.
    """
    required = {"stratum", "parent_id", "method", "condition", "clean_error", "stressed_error"}
    if not required <= set(pairs.columns):
        raise ValueError("Missing required paired-error columns")
    if any(pairs[key].isna().any() for key in required - {"clean_error", "stressed_error"}):
        raise ValueError("Design identifiers must not be missing")
    if (
        not methods
        or not conditions
        or len(set(methods)) != len(methods)
        or len(set(conditions)) != len(conditions)
    ):
        raise ValueError("Nonempty unique method and condition lists are required")
    methods, conditions = sorted(methods), sorted(conditions)
    if type(draws) is not int or draws < 0 or type(seed) is not int or seed < 0:
        raise ValueError("Draw count and seed must be nonnegative integers")
    if not 0 < nominal < 1 or not np.isfinite(denominator_floor) or denominator_floor < 0:
        raise ValueError("Invalid nominal level or denominator floor")
    if (
        not stratum_weights
        or any(not np.isfinite(w) or w <= 0 for w in stratum_weights.values())
        or not np.isclose(sum(stratum_weights.values()), 1, rtol=0, atol=1e-12)
    ):
        raise ValueError("Explicit positive stratum weights must sum to one")
    if set(parents_by_stratum) != set(stratum_weights) or set(pairs.stratum) - set(stratum_weights):
        raise ValueError(
            "Parent-index strata must match the fixed design; weights cannot be dropped"
        )
    all_parents = []
    for stratum, parents in parents_by_stratum.items():
        if not parents or len(set(parents)) != len(parents):
            raise ValueError("Every stratum requires a nonempty unique parent index")
        if set(pairs.loc[pairs.stratum == stratum, "parent_id"]) - set(parents):
            raise ValueError("Observed parents outside the declared parent index")
        all_parents.extend(parents)
    if len(set(all_parents)) != len(all_parents):
        raise ValueError("A parent cannot be independent in more than one stratum")
    if set(pairs.method) - set(methods) or set(pairs.condition) - set(conditions):
        raise ValueError("Rows outside the declared methods/conditions")
    keys = ["stratum", "parent_id", "method", "condition"]
    if pairs.duplicated(keys).any():
        raise ValueError("Duplicate parent-method-condition rows")
    if pairs.groupby("parent_id").stratum.nunique().gt(1).any():
        raise ValueError("A parent cannot be independent in more than one stratum")
    pairs = pairs.copy()
    for column in ("clean_error", "stressed_error"):
        pairs[column] = pd.to_numeric(pairs[column], errors="raise")
        finite = np.isfinite(pairs[column])
        if (pairs.loc[finite, column] < 0).any():
            raise ValueError("Absolute errors must be nonnegative")
        pairs.loc[~finite, column] = np.nan
    if pairs.groupby(["parent_id", "method"]).clean_error.nunique().gt(1).any():
        raise ValueError("A parent's clean error must agree across descendants")
    tensors, accounting = {}, []
    for stratum in sorted(stratum_weights):
        group = pairs[pairs.stratum == stratum]
        parents = sorted(parents_by_stratum[stratum])
        index = pd.MultiIndex.from_product(
            [parents, methods, conditions], names=["parent_id", "method", "condition"]
        )
        array = (
            group.set_index(["parent_id", "method", "condition"])[["clean_error", "stressed_error"]]
            .reindex(index)
            .to_numpy(float)
            .reshape(len(parents), len(methods), len(conditions), 2)
        )
        complete = np.isfinite(array).all(axis=(1, 2, 3))
        tensors[stratum] = array[complete]
        for method_index, method in enumerate(methods):
            for condition_index, condition in enumerate(conditions):
                available = np.isfinite(array[:, method_index, condition_index]).all(axis=1)
                accounting.append(
                    {
                        "stratum": stratum,
                        "method": method,
                        "condition": condition,
                        "weight": stratum_weights[stratum],
                        "parents_attempted": len(parents),
                        "pairs_available": int(available.sum()),
                        "pairs_missing": int((~available).sum()),
                        "parents_common_complete": int(complete.sum()),
                        "parents_excluded_from_common_support": int((~complete).sum()),
                    }
                )
    has_point = all(len(a) >= 1 for a in tensors.values())
    can_bootstrap = all(len(a) >= 2 for a in tensors.values())
    shape = (len(methods), len(conditions), 2)
    estimate = (
        sum(stratum_weights[s] * a.mean(axis=0) for s, a in tensors.items())
        if has_point
        else np.full(shape, np.nan)
    )
    combined = np.zeros((draws, *shape)) if can_bootstrap else np.empty((0, *shape))
    if can_bootstrap:
        for stratum, array in tensors.items():
            # Stable keyed streams: input/method/condition display order cannot
            # alter parent resampling. Different strata are sampled independently.
            key = f"lrdbench-paired-summary-v1:{seed}:{stratum}".encode()
            rng = np.random.default_rng(int.from_bytes(hashlib.sha256(key).digest()[:8], "little"))
            for start in range(0, draws, 8):
                end = min(start + 8, draws)
                indices = rng.integers(0, len(array), size=(end - start, len(array)))
                combined[start:end] += stratum_weights[stratum] * array[indices].mean(axis=1)
    summaries, draw_rows = [], []
    for i, method in enumerate(methods):
        for j, condition in enumerate(conditions):
            clean, stressed = estimate[i, j]
            clean_draws, stressed_draws = combined[:, i, j].T
            for metric in ("absolute_error_inflation", "paired_mae_ratio"):
                if metric == "absolute_error_inflation":
                    point = stressed - clean
                    values = stressed_draws - clean_draws
                else:
                    point = stressed / clean if clean > denominator_floor else np.nan
                    values = np.full(len(combined), np.nan)
                    np.divide(
                        stressed_draws,
                        clean_draws,
                        out=values,
                        where=clean_draws > denominator_floor,
                    )
                finite = np.isfinite(values)
                interval = (
                    np.quantile(values[finite], [(1 - nominal) / 2, (1 + nominal) / 2])
                    if finite.sum() >= 5 and np.isfinite(point)
                    else (np.nan, np.nan)
                )
                reason = (
                    "no_common_complete_parent_in_a_stratum"
                    if not has_point
                    else "denominator_at_or_below_floor"
                    if not np.isfinite(point)
                    else "bootstrap_disabled"
                    if draws == 0
                    else "fewer_than_two_common_parents_in_a_stratum"
                    if not can_bootstrap
                    else "insufficient_valid_draws"
                    if finite.sum() < 5
                    else None
                )
                summaries.append(
                    {
                        "method": method,
                        "condition": condition,
                        "metric": metric,
                        "value": point,
                        "clean_mae": clean,
                        "stressed_mae": stressed,
                        "ci_low": interval[0],
                        "ci_high": interval[1],
                        "nominal": nominal,
                        "bootstrap_se": float(np.std(values[finite], ddof=1))
                        if finite.sum() >= 2
                        else np.nan,
                        "requested_draws": draws,
                        "attempted_draws": len(values),
                        "used_draws": int(finite.sum()),
                        "invalid_draws": int((~finite).sum()),
                        "unavailable_reason": reason,
                        "support": "common_complete_parents_across_declared_methods_and_conditions",
                    }
                )
                draw_rows.extend(
                    {
                        "draw": k,
                        "method": method,
                        "condition": condition,
                        "metric": metric,
                        "value": value,
                        "clean_mae": clean_draws[k],
                        "stressed_mae": stressed_draws[k],
                    }
                    for k, value in enumerate(values)
                )
    return pd.DataFrame(summaries), pd.DataFrame(accounting), pd.DataFrame(draw_rows)
