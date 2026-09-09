"""Declared estimands and joint-parent summaries for the frozen confirmation.

Inputs are aligned tensors, never pooled lists of successful fits. Point-error
contrasts condition on common complete support; coverage retains every attempt.
"""

from __future__ import annotations

import hashlib

import numpy as np
from scipy.stats import binomtest


def divide(a, b, floor=0):
    a, b = np.broadcast_arrays(np.asarray(a, float), np.asarray(b, float))
    result = np.full(a.shape, np.nan)
    np.divide(a, b, out=result, where=np.isfinite(b) & (b > floor))
    return result


def joint_means(values, *, draws, seed, key):
    """All columns share each sampled parent; batches bound working memory.

    Counting sampled indices and multiplying is algebraically equivalent to
    explicitly gathering the parent rows. It keeps memory independent of the
    number of features times parents times all requested resamples.
    """
    values = np.asarray(values, float)
    if values.ndim != 2 or not np.isfinite(values).all():
        raise ValueError("Joint primitive matrix must be finite and two-dimensional.")
    if type(draws) is not int or draws < 0:
        raise ValueError("Invalid summary draw count.")
    n, features = values.shape
    point = values.mean(axis=0) if n else np.full(features, np.nan)
    result = np.full((draws, features), np.nan)
    if n >= 2:
        payload = f"lrdbench-confirmation-summary-v1:{seed}:{key}".encode()
        rng = np.random.default_rng(int.from_bytes(hashlib.sha256(payload).digest()[:8], "little"))
        for start in range(0, draws, 16):
            end = min(start + 16, draws)
            indices = rng.integers(0, n, size=(end - start, n))
            weights = np.asarray([np.bincount(i, minlength=n) for i in indices], dtype=float)
            result[start:end] = (weights / n) @ values
    return point, result


def mcse(values):
    values = np.asarray(values, float)
    return float(values.std(ddof=1) / np.sqrt(len(values))) if len(values) >= 2 else np.nan


def wilson(success, attempted):
    if not 0 <= success <= attempted or attempted < 0:
        raise ValueError("Invalid binomial counts.")
    if attempted == 0:
        return np.nan, np.nan
    interval = binomtest(int(success), int(attempted)).proportion_ci(
        confidence_level=0.95, method="wilson"
    )
    return interval.low, interval.high


class Summary:
    def __init__(self, draws):
        self.requested = draws
        self.rows = []
        self.draws = []

    def add(
        self,
        method,
        condition,
        metric,
        value,
        samples,
        *,
        support,
        attempted,
        used,
        contrast="",
        standard_error=np.nan,
        successes=None,
        denominator=None,
        reason=None,
    ):
        samples = np.asarray(samples, float)
        if samples.shape != (self.requested,):
            raise ValueError("Every summary retains its full aligned draw vector.")
        valid = np.isfinite(samples)
        complete = bool(valid.all() and len(samples) >= 5 and np.isfinite(value))
        low, high = np.quantile(samples, [0.025, 0.975]) if complete else (np.nan, np.nan)
        interval_method = "joint_parent_percentile"
        if successes is not None:
            low, high = wilson(successes, denominator)
            interval_method = "Wilson_95"
            # Boundary frequencies have Wilson uncertainty; zero plug-in SE
            # is deliberately not presented as zero Monte Carlo uncertainty.
            standard_error = (
                np.sqrt(value * (1 - value) / denominator)
                if denominator and 0 < successes < denominator
                else np.nan
            )
        self.rows.append(
            {
                "method": method,
                "condition": condition,
                "metric": metric,
                "contrast": contrast,
                "value": value,
                "ci_low": low,
                "ci_high": high,
                "nominal": 0.95,
                "interval_method": interval_method,
                "mcse": standard_error,
                "bootstrap_se": samples.std(ddof=1) if complete else np.nan,
                "parents_attempted": attempted,
                "parents_used": used,
                "parents_excluded": attempted - used,
                "support": support,
                "successes": successes,
                "denominator": denominator,
                "requested_draws": self.requested,
                "used_draws": int(valid.sum()),
                "invalid_draws": int((~valid).sum()),
                "unavailable_reason": reason
                or (
                    "no_estimable_support"
                    if not np.isfinite(value)
                    else "incomplete_summary_draws"
                    if not complete and successes is None
                    else None
                ),
            }
        )
        self.draws.append(samples)

    def matrix(self):
        return np.column_stack(self.draws) if self.draws else np.empty((self.requested, 0))


def point_summaries(
    points, runtimes, *, target, methods, conditions, draws, seed, key, floor=1e-12
):
    """Shape parents x conditions x methods; condition zero is clean.

    NaN encodes invalid/missing points. Report full validity separately from the
    common complete sample used for error and drift comparisons.
    """
    points, runtimes = np.asarray(points, float), np.asarray(runtimes, float)
    if (
        points.ndim != 3
        or points.shape != runtimes.shape
        or points.shape[1:] != (len(conditions), len(methods))
        or conditions[0] != "clean"
    ):
        raise ValueError("Misaligned point design.")
    if len(set(methods)) != len(methods) or len(set(conditions)) != len(conditions):
        raise ValueError("Duplicate design labels.")
    n, c, m = points.shape
    valid = np.isfinite(points)
    complete = valid.all(axis=(1, 2))
    retained = points[complete]
    errors = retained - target
    drift = retained - retained[:, :1, :]
    primitives = np.stack([errors, np.abs(errors), errors**2, drift, np.abs(drift)], axis=-1)
    means, samples = joint_means(
        primitives.reshape(len(retained), c * m * 5), draws=draws, seed=seed, key=f"{key}:common"
    )
    means, samples = means.reshape(c, m, 5), samples.reshape(draws, c, m, 5)
    all_values = np.stack(
        [
            valid,
            valid & ((points < 0) | (points > 1)),
            valid & (points >= 0.6),
            np.nan_to_num(runtimes, nan=0),
        ],
        axis=-1,
    )
    full, full_draws = joint_means(
        all_values.reshape(n, c * m * 4), draws=draws, seed=seed, key=f"{key}:all_attempts"
    )
    full, full_draws = full.reshape(c, m, 4), full_draws.reshape(draws, c, m, 4)
    output = Summary(draws)
    support = "common_complete_all_declared_methods_conditions"
    count = int(complete.sum())
    for j, condition in enumerate(conditions):
        for k, method in enumerate(methods):
            for metric, index in (("bias", 0), ("mae", 1), ("mse", 2)):
                output.add(
                    method,
                    condition,
                    metric,
                    means[j, k, index],
                    samples[:, j, k, index],
                    support=support,
                    attempted=n,
                    used=count,
                    standard_error=mcse(primitives[:, j, k, index]),
                )
            rmse = np.sqrt(means[j, k, 2])
            output.add(
                method,
                condition,
                "rmse",
                rmse,
                np.sqrt(samples[:, j, k, 2]),
                support=support,
                attempted=n,
                used=count,
                standard_error=mcse(primitives[:, j, k, 2]) / (2 * rmse) if rmse > 0 else np.nan,
            )
            for metric, ix, conditional in (
                ("validity", 0, False),
                ("outside_0_1", 1, True),
                ("H_ge_0p6_exceedance_diagnostic", 2, True),
            ):
                successes = int(all_values[:, j, k, ix].sum())
                denom = int(valid[:, j, k].sum()) if conditional else n
                value = successes / denom if denom else np.nan
                distribution = (
                    divide(full_draws[:, j, k, ix], full_draws[:, j, k, 0])
                    if conditional
                    else full_draws[:, j, k, ix]
                )
                output.add(
                    method,
                    condition,
                    metric,
                    value,
                    distribution,
                    support="method_valid_points" if conditional else "all_attempts",
                    attempted=n,
                    used=denom,
                    successes=successes,
                    denominator=denom,
                )
            runtime_valid = np.isfinite(runtimes[:, j, k])
            if runtime_valid.all():
                output.add(
                    method,
                    condition,
                    "mean_runtime_seconds",
                    full[j, k, 3],
                    full_draws[:, j, k, 3],
                    support="all_attempts",
                    attempted=n,
                    used=n,
                    standard_error=mcse(runtimes[:, j, k]),
                )
            if j:
                for metric, value, distribution, individual in (
                    (
                        "absolute_error_inflation",
                        means[j, k, 1] - means[0, k, 1],
                        samples[:, j, k, 1] - samples[:, 0, k, 1],
                        primitives[:, j, k, 1] - primitives[:, 0, k, 1],
                    ),
                    (
                        "signed_estimate_drift",
                        means[j, k, 3],
                        samples[:, j, k, 3],
                        primitives[:, j, k, 3],
                    ),
                    (
                        "absolute_estimate_drift",
                        means[j, k, 4],
                        samples[:, j, k, 4],
                        primitives[:, j, k, 4],
                    ),
                ):
                    output.add(
                        method,
                        condition,
                        metric,
                        value,
                        distribution,
                        support=support,
                        attempted=n,
                        used=count,
                        standard_error=mcse(individual),
                    )
                output.add(
                    method,
                    condition,
                    "paired_mae_ratio",
                    float(divide(means[j, k, 1], means[0, k, 1], floor)),
                    divide(samples[:, j, k, 1], samples[:, 0, k, 1], floor),
                    support=support,
                    attempted=n,
                    used=count,
                )
                loss = all_values[:, 0, k, 0] - all_values[:, j, k, 0]
                output.add(
                    method,
                    condition,
                    "validity_loss",
                    full[0, k, 0] - full[j, k, 0],
                    full_draws[:, 0, k, 0] - full_draws[:, j, k, 0],
                    support="all_attempts",
                    attempted=n,
                    used=n,
                    standard_error=mcse(loss),
                )
    for base in ("Higuchi", "GHE"):
        if base not in methods or base + "::centered" not in methods:
            continue
        raw, center = methods.index(base), methods.index(base + "::centered")
        output.add(
            base,
            "clean",
            "mae_difference",
            means[0, center, 1] - means[0, raw, 1],
            samples[:, 0, center, 1] - samples[:, 0, raw, 1],
            support=support,
            attempted=n,
            used=count,
            contrast="geometric_mean_removal_clean",
            standard_error=mcse(primitives[:, 0, center, 1] - primitives[:, 0, raw, 1]),
        )
        for j in range(1, c):
            point = (means[j, center, 1] - means[0, center, 1]) - (
                means[j, raw, 1] - means[0, raw, 1]
            )
            distribution = (samples[:, j, center, 1] - samples[:, 0, center, 1]) - (
                samples[:, j, raw, 1] - samples[:, 0, raw, 1]
            )
            individual = (primitives[:, j, center, 1] - primitives[:, 0, center, 1]) - (
                primitives[:, j, raw, 1] - primitives[:, 0, raw, 1]
            )
            output.add(
                base,
                conditions[j],
                "error_inflation_difference",
                point,
                distribution,
                support=support,
                attempted=n,
                used=count,
                contrast="geometric_mean_removal_stress",
                standard_error=mcse(individual),
            )
            output.add(
                base,
                conditions[j],
                "absolute_drift_difference",
                means[j, center, 4] - means[j, raw, 4],
                samples[:, j, center, 4] - samples[:, j, raw, 4],
                support=support,
                attempted=n,
                used=count,
                contrast="geometric_mean_removal_stress",
                standard_error=mcse(primitives[:, j, center, 4] - primitives[:, j, raw, 4]),
            )
    accounting = {
        "parents_attempted": n,
        "parents_common_complete": count,
        "complete_parent_indices": np.flatnonzero(complete).tolist(),
        "excluded_parent_indices": np.flatnonzero(~complete).tolist(),
        "missing_or_invalid": [
            {"parent_index": int(i), "condition": conditions[j], "method": methods[k]}
            for i, j, k in np.argwhere(~valid)
        ],
    }
    return output, accounting


def interval_pairs(labels):
    index = {tuple(label): i for i, label in enumerate(labels)}
    pairs = []
    for method in sorted({label[0] for label in labels}):
        comparisons = (
            [
                ("interval_centering", f"cbc_raw_{construction}", f"cbc_centered_{construction}")
                for construction in ("percentile", "basic")
            ]
            + [
                ("interval_construction", f"cbc_{treatment}_percentile", f"cbc_{treatment}_basic")
                for treatment in ("raw", "centered")
            ]
            + [("interval_model", "cbc_centered_basic", "unknown_fgn_centered_basic")]
        )
        for contrast, a, b in comparisons:
            if (method, a) in index and (method, b) in index:
                pairs.append((method, contrast, a, b, index[method, a], index[method, b]))
    return pairs


def interval_summaries(
    low,
    high,
    available,
    *,
    target,
    labels,
    draws,
    seed,
    key,
    model_boundary=None,
    model_available=None,
):
    low, high, available = (
        np.asarray(low, float),
        np.asarray(high, float),
        np.asarray(available, bool),
    )
    if (
        low.shape != high.shape
        or low.shape != available.shape
        or low.ndim != 2
        or low.shape[1] != len(labels)
        or len({tuple(v) for v in labels}) != len(labels)
    ):
        raise ValueError("Misaligned interval design.")
    if (available & (~np.isfinite(low) | ~np.isfinite(high) | (low > high))).any():
        raise ValueError("Available intervals require ordered finite endpoints.")
    n, m = low.shape
    covered = available & (low <= target) & (target <= high)
    widths = np.where(available, high - low, 0)
    pairs = interval_pairs(labels)
    columns = [covered.astype(float), available.astype(float), widths]
    for _, _, _, _, a, b in pairs:
        common = available[:, a] & available[:, b]
        columns += [
            common[:, None].astype(float),
            np.where(common, widths[:, b] - widths[:, a], 0)[:, None],
        ]
    if model_boundary is not None:
        model_boundary, model_available = (
            np.asarray(model_boundary, bool),
            np.asarray(model_available, bool),
        )
        if (
            model_boundary.shape != (n,)
            or model_available.shape != (n,)
            or (model_boundary & ~model_available).any()
        ):
            raise ValueError("Invalid model fit/boundary ledger.")
        columns += [model_boundary[:, None].astype(float), model_available[:, None].astype(float)]
    means, samples = joint_means(
        np.concatenate(columns, axis=1), draws=draws, seed=seed, key=f"{key}:all_interval_attempts"
    )
    out = Summary(draws)
    for j, (method, candidate) in enumerate(labels):
        success, avail = int(covered[:, j].sum()), int(available[:, j].sum())
        for metric, value, distribution, numerator, denom in (
            ("unconditional_coverage", means[j], samples[:, j], success, n),
            ("availability", means[m + j], samples[:, m + j], avail, n),
            (
                "conditional_coverage",
                float(divide(means[j], means[m + j])),
                divide(samples[:, j], samples[:, m + j]),
                success,
                avail,
            ),
        ):
            out.add(
                method,
                candidate,
                metric,
                value,
                distribution,
                support="available_intervals"
                if metric == "conditional_coverage"
                else "all_attempts_unavailable_is_miss",
                attempted=n,
                used=denom,
                successes=numerator,
                denominator=denom,
            )
        width = float(divide(means[2 * m + j], means[m + j]))
        out.add(
            method,
            candidate,
            "mean_width",
            width,
            divide(samples[:, 2 * m + j], samples[:, m + j]),
            support="available_intervals",
            attempted=n,
            used=avail,
            standard_error=mcse(widths[available[:, j], j]),
        )
        out.add(
            method,
            candidate,
            "median_width",
            np.median(widths[available[:, j], j]) if avail else np.nan,
            np.full(draws, np.nan),
            support="available_intervals",
            attempted=n,
            used=avail,
            reason="descriptive_median_no_bootstrap_interval_declared",
        )
    for k, (method, contrast, a_label, b_label, a, b) in enumerate(pairs):
        condition = f"{b_label}_minus_{a_label}"
        individual = covered[:, b].astype(float) - covered[:, a].astype(float)
        out.add(
            method,
            condition,
            "coverage_difference",
            means[b] - means[a],
            samples[:, b] - samples[:, a],
            support="all_attempts_unavailable_is_miss",
            attempted=n,
            used=n,
            contrast=contrast,
            standard_error=mcse(individual),
        )
        cidx, widx = 3 * m + 2 * k, 3 * m + 2 * k + 1
        common = available[:, a] & available[:, b]
        out.add(
            method,
            condition,
            "mean_width_difference",
            float(divide(means[widx], means[cidx])),
            divide(samples[:, widx], samples[:, cidx]),
            support="pair_common_available_intervals_resample_all_attempts_then_condition",
            attempted=n,
            used=int(common.sum()),
            contrast=contrast,
            standard_error=mcse((widths[:, b] - widths[:, a])[common]),
        )
    if model_boundary is not None:
        for metric, flags, ix in (
            ("model_boundary_rate_all_attempts", model_boundary, -2),
            ("model_fit_availability", model_available, -1),
        ):
            out.add(
                "unknown_mean_fGn_ML",
                "clean",
                metric,
                means[ix],
                samples[:, ix],
                support="all_model_attempts",
                attempted=n,
                used=n,
                successes=int(flags.sum()),
                denominator=n,
            )
    return out, {
        "parents_attempted": n,
        "intervals_unavailable": [
            {"parent_index": int(i), "method": labels[j][0], "candidate": labels[j][1]}
            for i, j in np.argwhere(~available)
        ],
        "model_failures": np.flatnonzero(~model_available).tolist()
        if model_available is not None
        else None,
        "model_boundary_hits": np.flatnonzero(model_boundary).tolist()
        if model_boundary is not None
        else None,
        "coverage_denominator": "all_attempted_parents_in_this_cell",
    }


def aggregate_groups(groups, *, floor=1e-12):
    """Fixed equal cell weights; empty cells propagate, never renormalize.

    Domain RMSE and MAE ratios are reconstructed from weighted primitive means.
    A median of cell medians is deliberately not reported as a pooled median.
    """
    count = 0
    for group in groups:
        group_keys = [(r["method"], r["condition"], r["metric"], r["contrast"]) for r in group.rows]
        if count == 0:
            keys, template, requested = group_keys, group.rows, group.requested
            values = np.zeros(len(keys))
            samples = np.zeros((requested, len(keys)))
            attempted, used = np.zeros(len(keys), int), np.zeros(len(keys), int)
        elif group_keys != keys or group.requested != requested:
            raise ValueError("Domain cells must have the same declared estimand roster.")
        values += np.asarray([r["value"] for r in group.rows])
        samples += group.matrix()
        attempted += np.asarray([r["parents_attempted"] for r in group.rows], int)
        used += np.asarray([r["parents_used"] for r in group.rows], int)
        count += 1
    if count == 0:
        raise ValueError("Every domain needs its complete declared cell list.")
    values /= count
    samples /= count
    lookup = {key: i for i, key in enumerate(keys)}
    for i, (method, condition, metric, contrast) in enumerate(keys):
        if metric == "paired_mae_ratio":
            numerator, denominator = (
                lookup[method, condition, "mae", contrast],
                lookup[method, "clean", "mae", contrast],
            )
            values[i] = divide(values[numerator], values[denominator], floor)
            samples[:, i] = divide(samples[:, numerator], samples[:, denominator], floor)
        if metric == "rmse":
            ix = lookup[method, condition, "mse", contrast]
            values[i], samples[:, i] = np.sqrt(values[ix]), np.sqrt(samples[:, ix])
    out = Summary(requested)
    for i, row in enumerate(template):
        if row["metric"] == "median_width":
            continue
        out.add(
            row["method"],
            row["condition"],
            row["metric"],
            values[i],
            samples[:, i],
            support="fixed_equal_cell_weights__" + row["support"],
            attempted=int(attempted[i]),
            used=int(used[i]),
            contrast=row["contrast"],
        )
        out.rows[-1]["domain_cells"] = count
        out.rows[-1]["cell_weight"] = 1 / count
    return out
