"""Explicit paired stress metrics with denominators and missing-pair accounting."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import numpy as np

from lrdbench.schema import EstimateResult, EstimatorSpec, MetricSpec, MetricValue, SeriesRecord
from lrdbench.validation import truth_for

STRESS_PAIR_METRICS = frozenset(
    {
        "estimate_drift",
        "absolute_estimate_drift",
        "signed_estimate_drift",
        "absolute_error_inflation",
        "relative_degradation_ratio",
        "paired_mae_ratio",
        "validity_collapse",
        "coverage_collapse",
        "coverage_loss_rate",
        "net_coverage_loss",
    }
)
INTERVAL_PAIR_METRICS = frozenset({"coverage_collapse", "coverage_loss_rate", "net_coverage_loss"})


def stress_pair_rows(
    *,
    run_id: str,
    record: SeriesRecord,
    estimator_spec: EstimatorSpec,
    est: EstimateResult | None,
    clean_estimate: EstimateResult | None,
    ms: MetricSpec,
    stratum: dict[str, Any],
    stratum_key: tuple[tuple[str, Any], ...],
    interval: Callable[[EstimateResult, float], tuple[float, float] | None],
) -> list[MetricValue]:
    metadata: dict[str, Any] = {
        "stratum_key": stratum_key,
        "contamination_operator": record.annotations.get("contamination_operator"),
        "clean_record_id": record.annotations.get("clean_record_id"),
    }

    def row(value: float | None, **extras: Any) -> MetricValue:
        return MetricValue(
            run_id=run_id,
            record_id=record.record_id,
            estimator_name=estimator_spec.name,
            metric_name=ms.name,
            value=value,
            stratum=stratum,
            metadata={**metadata, **extras},
        )

    def missing(reason: str) -> list[MetricValue]:
        if ms.name in INTERVAL_PAIR_METRICS:
            return [
                row(None, nominal=a, pair_available=False, missing_reason=reason)
                for a in ms.nominal_levels
            ]
        return [row(None, pair_available=False, missing_reason=reason)]

    if est is None:
        return missing("missing_stressed_estimate")
    if clean_estimate is None:
        return missing("missing_clean_estimate")
    if ms.name == "validity_collapse":
        return [row(float(clean_estimate.valid and not est.valid), pair_available=True)]
    if any(
        not e.valid or e.point is None or not np.isfinite(e.point) for e in (clean_estimate, est)
    ):
        return missing("invalid_point_pair")
    assert est.point is not None and clean_estimate.point is not None
    difference = float(est.point - clean_estimate.point)
    if ms.name in {"estimate_drift", "absolute_estimate_drift", "signed_estimate_drift"}:
        return [
            row(
                difference if ms.name == "signed_estimate_drift" else abs(difference),
                pair_available=True,
            )
        ]

    truth = truth_for(record, estimator_spec.target_estimand)
    if truth is None or truth.target_value is None or not np.isfinite(truth.target_value):
        return missing("missing_target_truth")
    target = float(truth.target_value)
    metadata["target_estimand"] = estimator_spec.target_estimand
    metadata["target_interpretation"] = "retained_latent_clean_target"
    if ms.name in INTERVAL_PAIR_METRICS:
        rows = []
        for nominal in ms.nominal_levels:
            clean_bounds, stressed_bounds = (
                interval(clean_estimate, nominal),
                interval(est, nominal),
            )
            if clean_bounds is None or stressed_bounds is None:
                rows.append(
                    row(
                        None,
                        nominal=nominal,
                        pair_available=False,
                        missing_ci=True,
                        missing_reason="missing_interval_pair",
                    )
                )
                continue
            clean_hit = float(clean_bounds[0] <= target <= clean_bounds[1])
            stressed_hit = float(stressed_bounds[0] <= target <= stressed_bounds[1])
            loss = clean_hit - stressed_hit
            rows.append(
                row(
                    loss if ms.name == "net_coverage_loss" else max(0.0, loss),
                    nominal=nominal,
                    pair_available=True,
                    clean_covered=clean_hit,
                    stressed_covered=stressed_hit,
                )
            )
        return rows

    clean_error = abs(float(clean_estimate.point) - target)
    stressed_error = abs(float(est.point) - target)
    metadata.update(clean_absolute_error=clean_error, stressed_absolute_error=stressed_error)
    if ms.name == "absolute_error_inflation":
        return [row(stressed_error - clean_error, pair_available=True)]
    if ms.name == "relative_degradation_ratio":
        if clean_error < 1e-12:
            return [row(None, pair_available=True, missing_reason="near_zero_clean_error")]
        return [row(stressed_error / clean_error, pair_available=True)]
    if ms.name == "paired_mae_ratio":
        # No per-record ratio: these components are aggregated before division.
        return [row(None, pair_available=True, aggregation_components=True)]
    raise ValueError(f"unsupported paired metric: {ms.name}")


def aggregate_paired_mae_ratio(
    run_id: str, rows: list[MetricValue], epsilon: float
) -> list[MetricValue]:
    """Equal-weight available stratum mean errors, then divide; retain zero-error strata."""
    grouped: dict[tuple[str, str], list[MetricValue]] = {}
    for row in rows:
        grouped.setdefault((row.estimator_name, repr(row.metadata["stratum_key"])), []).append(row)
    output: list[MetricValue] = []

    def aggregate(
        estimator: str,
        numerator: float | None,
        denominator: float | None,
        stratum: dict[str, Any],
        metadata: dict[str, Any],
    ) -> MetricValue:
        reason = (
            "no_valid_pairs"
            if numerator is None
            else "near_zero_clean_mae"
            if denominator is None or denominator <= epsilon
            else None
        )
        value = (
            numerator / denominator
            if numerator is not None and denominator is not None and denominator > epsilon
            else None
        )
        return MetricValue(
            run_id=run_id,
            record_id=None,
            estimator_name=estimator,
            metric_name="paired_mae_ratio",
            value=value,
            stratum=stratum,
            metadata={
                **metadata,
                "numerator_mae": numerator,
                "denominator_mae": denominator,
                "denominator_epsilon": epsilon,
                "missing_reason": reason,
            },
        )

    for (estimator, _), group in grouped.items():
        valid = [r for r in group if r.metadata.get("aggregation_components")]
        numerator = (
            float(np.mean([r.metadata["stressed_absolute_error"] for r in valid]))
            if valid
            else None
        )
        denominator = (
            float(np.mean([r.metadata["clean_absolute_error"] for r in valid])) if valid else None
        )
        output.append(
            aggregate(
                estimator,
                numerator,
                denominator,
                dict(group[0].stratum),
                {
                    "aggregation": "ratio_of_paired_stratum_maes",
                    "stratum_key": group[0].metadata["stratum_key"],
                    "n_attempted": len(group),
                    "n_included": len(valid),
                    "n_missing": len(group) - len(valid),
                },
            )
        )
    for estimator in sorted({r.estimator_name for r in output}):
        strata = [r for r in output if r.estimator_name == estimator]
        valid_strata = [r for r in strata if r.metadata["numerator_mae"] is not None]
        numerator = (
            float(np.mean([r.metadata["numerator_mae"] for r in valid_strata]))
            if valid_strata
            else None
        )
        denominator = (
            float(np.mean([r.metadata["denominator_mae"] for r in valid_strata]))
            if valid_strata
            else None
        )
        output.append(
            aggregate(
                estimator,
                numerator,
                denominator,
                {"level": "balanced_global"},
                {
                    "aggregation": "ratio_of_equal_weight_available_stratum_maes",
                    "n_strata_attempted": len(strata),
                    "n_strata_included": len(valid_strata),
                    "n_attempted": sum(r.metadata["n_attempted"] for r in strata),
                    "n_included": sum(r.metadata["n_included"] for r in strata),
                    "n_missing": sum(r.metadata["n_missing"] for r in strata),
                },
            )
        )
    return output
