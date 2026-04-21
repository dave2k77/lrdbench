from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from dataclasses import replace
from itertools import combinations
from math import sqrt
from typing import Any

import numpy as np

from lrdbench.enums import BenchmarkMode
from lrdbench.interfaces import BaseEvaluator
from lrdbench.metrics_catalog import METRIC_SPECS
from lrdbench.registries import EstimatorRegistry
from lrdbench.schema import (
    BenchmarkManifest,
    EstimateResult,
    EstimatorSpec,
    MetricBundle,
    MetricSpec,
    MetricValue,
    SeriesRecord,
)
from lrdbench.strata import stratum_from_record, stratum_key
from lrdbench.validation import (
    ManifestValidationError,
    validate_metric_admissibility,
    validate_truth_compatibility,
)

STRESS_PAIR_METRICS = frozenset(
    {
        "estimate_drift",
        "relative_degradation_ratio",
        "validity_collapse",
        "coverage_collapse",
    }
)

DISAGREEMENT_METRICS = frozenset(
    {
        "cross_estimator_dispersion",
        "pairwise_estimator_disagreement",
        "family_level_disagreement",
    }
)

SENSITIVITY_METRICS = frozenset(
    {
        "parameter_variant_sensitivity",
        "max_variant_drift",
    }
)


def _index_estimates(estimates: Sequence[EstimateResult]) -> dict[tuple[str, str], EstimateResult]:
    out: dict[tuple[str, str], EstimateResult] = {}
    for e in estimates:
        out[(e.record_id, e.estimator_name)] = e
    return out


def _ci_interval(est: EstimateResult, alpha: float) -> tuple[float, float] | None:
    for a, lo, hi in est.bootstrap_cis:
        if abs(float(a) - float(alpha)) < 1e-9:
            return (float(lo), float(hi))
    if est.ci_low is not None and est.ci_high is not None and abs(float(alpha) - 0.95) < 1e-9:
        return (float(est.ci_low), float(est.ci_high))
    return None


def _default_false_positive_threshold(target_estimand: str) -> float:
    if target_estimand == "long_memory_parameter":
        return 0.1
    return 0.6


def _default_false_positive_null_max(target_estimand: str) -> float:
    if target_estimand == "long_memory_parameter":
        return 0.0
    return 0.5


def _valid_point(est: EstimateResult | None) -> float | None:
    if est is None or not est.valid or est.point is None:
        return None
    return float(est.point)


def _population_std(vals: Sequence[float]) -> float:
    if not vals:
        return 0.0
    mean = sum(vals) / len(vals)
    return sqrt(sum((x - mean) ** 2 for x in vals) / len(vals))


def _mean_abs_pairwise(vals: Sequence[float]) -> float:
    pairs = list(combinations(vals, 2))
    if not pairs:
        return 0.0
    return float(sum(abs(a - b) for a, b in pairs) / len(pairs))


def _metric_aggregate_value(metric_name: str, vals: Sequence[float]) -> float:
    if metric_name == "rmse":
        return float((sum(vals) / len(vals)) ** 0.5)
    return float(sum(vals) / len(vals))


def _percentile_interval(samples: Sequence[float], level: float) -> tuple[float, float]:
    arr = np.asarray(samples, dtype=float)
    tail = (1.0 - float(level)) / 2.0
    return (float(np.quantile(arr, tail)), float(np.quantile(arr, 1.0 - tail)))


class GroundTruthEvaluator(BaseEvaluator):
    """Truth-backed metrics (ground truth + stress_test) and paired stress diagnostics."""

    def evaluate(
        self,
        manifest: BenchmarkManifest,
        records: Sequence[SeriesRecord],
        estimates: Sequence[EstimateResult],
    ) -> MetricBundle:
        if manifest.mode not in (BenchmarkMode.GROUND_TRUTH, BenchmarkMode.STRESS_TEST):
            raise ValueError(
                f"GroundTruthEvaluator does not support mode {manifest.mode.value!r}"
            )
        idx = _index_estimates(estimates)
        per_series: list[MetricValue] = []
        run_id = manifest.manifest_id

        for rec in records:
            for es in manifest.estimator_specs:
                est = idx.get((rec.record_id, es.name))
                if est is None:
                    continue
                try:
                    validate_truth_compatibility(es, rec)
                    compatible = True
                except ManifestValidationError:
                    compatible = False
                sk = stratum_key(rec)
                stratum_dict: dict[str, Any] = dict(stratum_from_record(rec))

                for ms in manifest.metric_specs:
                    validate_metric_admissibility(ms, manifest.mode, rec)
                    if ms.name in STRESS_PAIR_METRICS:
                        if manifest.mode is not BenchmarkMode.STRESS_TEST:
                            continue
                        if rec.annotations.get("stress_role") != "contaminated":
                            continue
                        for row in self._stress_pair_rows(
                            run_id=run_id,
                            record=rec,
                            estimator_spec=es,
                            est=est,
                            ms=ms,
                            stratum_dict=stratum_dict,
                            sk=sk,
                            idx=idx,
                        ):
                            per_series.append(row)
                        continue
                    if ms.name in ("bias", "mae", "rmse") and not compatible:
                        continue
                    if ms.name == "coverage_error":
                        continue
                    for row in self._per_series_rows(
                        run_id=run_id,
                        record=rec,
                        estimator_spec=es,
                        est=est,
                        ms=ms,
                        stratum_dict=stratum_dict,
                        sk=sk,
                        compatible=compatible,
                    ):
                        per_series.append(row)

            sk = stratum_key(rec)
            stratum_dict = dict(stratum_from_record(rec))
            for ms in manifest.metric_specs:
                if ms.name in DISAGREEMENT_METRICS or ms.name in SENSITIVITY_METRICS:
                    validate_metric_admissibility(ms, manifest.mode, rec)
            per_series.extend(
                self._estimator_disagreement_rows(
                    run_id=run_id,
                    record=rec,
                    metric_specs=manifest.metric_specs,
                    estimator_specs=manifest.estimator_specs,
                    idx=idx,
                    stratum_dict=stratum_dict,
                    sk=sk,
                )
            )
            per_series.extend(
                self._parameter_variant_sensitivity_rows(
                    run_id=run_id,
                    record=rec,
                    metric_specs=manifest.metric_specs,
                    estimator_specs=manifest.estimator_specs,
                    idx=idx,
                    stratum_dict=stratum_dict,
                    sk=sk,
                )
            )

        aggregate = self._aggregate(run_id, per_series, manifest)
        uncertainty = self._benchmark_uncertainty(run_id, per_series, aggregate, manifest)
        return MetricBundle(
            per_series=tuple(per_series),
            aggregate=tuple(aggregate),
            uncertainty=tuple(uncertainty),
            metadata={},
        )

    def _stress_pair_rows(
        self,
        *,
        run_id: str,
        record: SeriesRecord,
        estimator_spec: EstimatorSpec,
        est: EstimateResult,
        ms: MetricSpec,
        stratum_dict: dict[str, Any],
        sk: tuple[tuple[str, Any], ...],
        idx: dict[tuple[str, str], EstimateResult],
    ) -> list[MetricValue]:
        clean_id = record.annotations.get("clean_record_id")
        if not isinstance(clean_id, str):
            return []
        est0 = idx.get((clean_id, estimator_spec.name))
        if est0 is None:
            return []

        op = record.annotations.get("contamination_operator")
        meta_base: dict[str, Any] = {
            "stratum_key": sk,
            "contamination_operator": op,
            "clean_record_id": clean_id,
        }

        if ms.name == "estimate_drift":
            if not est.valid or not est0.valid or est.point is None or est0.point is None:
                return []
            v = abs(float(est.point) - float(est0.point))
            return [
                MetricValue(
                    run_id=run_id,
                    record_id=record.record_id,
                    estimator_name=estimator_spec.name,
                    metric_name=ms.name,
                    value=v,
                    stratum=stratum_dict,
                    metadata=meta_base,
                )
            ]

        if ms.name == "relative_degradation_ratio":
            truth = record.truth
            if truth is None or truth.target_value is None:
                return []
            if not est.valid or est.point is None or not est0.valid or est0.point is None:
                return []
            y = float(truth.target_value)
            mae_c = abs(float(est.point) - y)
            mae_0 = abs(float(est0.point) - y)
            if mae_0 < 1e-12:
                return []
            ratio = mae_c / mae_0
            return [
                MetricValue(
                    run_id=run_id,
                    record_id=record.record_id,
                    estimator_name=estimator_spec.name,
                    metric_name=ms.name,
                    value=ratio,
                    stratum=stratum_dict,
                    metadata=meta_base,
                )
            ]

        if ms.name == "validity_collapse":
            v = 1.0 if est0.valid and not est.valid else 0.0
            return [
                MetricValue(
                    run_id=run_id,
                    record_id=record.record_id,
                    estimator_name=estimator_spec.name,
                    metric_name=ms.name,
                    value=v,
                    stratum=stratum_dict,
                    metadata=meta_base,
                )
            ]

        if ms.name == "coverage_collapse":
            truth = record.truth
            if truth is None or truth.target_value is None:
                return []
            y_star = float(truth.target_value)
            rows: list[MetricValue] = []
            for alpha in ms.nominal_levels:
                b0 = _ci_interval(est0, alpha)
                b1 = _ci_interval(est, alpha)
                if b0 is None or b1 is None:
                    rows.append(
                        MetricValue(
                            run_id=run_id,
                            record_id=record.record_id,
                            estimator_name=estimator_spec.name,
                            metric_name=ms.name,
                            value=None,
                            stratum=stratum_dict,
                            metadata={**meta_base, "nominal": alpha, "missing_ci": True},
                        )
                    )
                    continue
                lo0, hi0 = b0
                lo1, hi1 = b1
                h0 = 1.0 if lo0 <= y_star <= hi0 else 0.0
                h1 = 1.0 if lo1 <= y_star <= hi1 else 0.0
                collapse = max(0.0, h0 - h1)
                rows.append(
                    MetricValue(
                        run_id=run_id,
                        record_id=record.record_id,
                        estimator_name=estimator_spec.name,
                        metric_name=ms.name,
                        value=collapse,
                        stratum=stratum_dict,
                        metadata={**meta_base, "nominal": alpha},
                    )
                )
            return rows

        return []

    def _per_series_rows(
        self,
        *,
        run_id: str,
        record: SeriesRecord,
        estimator_spec: EstimatorSpec,
        est: EstimateResult,
        ms: MetricSpec,
        stratum_dict: dict[str, Any],
        sk: tuple[tuple[str, Any], ...],
        compatible: bool,
    ) -> list[MetricValue]:
        truth = record.truth
        rows: list[MetricValue] = []
        meta_base: dict[str, Any] = {"stratum_key": sk}

        if ms.name == "validity_rate":
            v = 1.0 if est.valid else 0.0
            rows.append(
                MetricValue(
                    run_id=run_id,
                    record_id=record.record_id,
                    estimator_name=estimator_spec.name,
                    metric_name=ms.name,
                    value=v,
                    stratum=stratum_dict,
                    metadata=meta_base,
                )
            )
            return rows
        if ms.name == "runtime":
            rows.append(
                MetricValue(
                    run_id=run_id,
                    record_id=record.record_id,
                    estimator_name=estimator_spec.name,
                    metric_name=ms.name,
                    value=float(est.runtime_seconds or 0.0),
                    stratum=stratum_dict,
                    metadata=meta_base,
                )
            )
            return rows
        if ms.name in ("bias", "mae", "rmse"):
            if truth is None or truth.target_value is None:
                return rows
            if not est.valid or est.point is None:
                return rows
            if truth.target_estimand != estimator_spec.target_estimand:
                return rows
            y = float(truth.target_value)
            yhat = float(est.point)
            err = yhat - y
            if ms.name == "bias":
                val: float | None = err
            elif ms.name == "mae":
                val = abs(err)
            else:
                val = err**2
            rows.append(
                MetricValue(
                    run_id=run_id,
                    record_id=record.record_id,
                    estimator_name=estimator_spec.name,
                    metric_name=ms.name,
                    value=val,
                    stratum=stratum_dict,
                    metadata=meta_base,
                )
            )
            return rows

        if ms.name == "coverage":
            if not compatible or truth is None or truth.target_value is None:
                return rows
            y_star = float(truth.target_value)
            for alpha in ms.nominal_levels:
                bounds = _ci_interval(est, alpha)
                if bounds is None:
                    rows.append(
                        MetricValue(
                            run_id=run_id,
                            record_id=record.record_id,
                            estimator_name=estimator_spec.name,
                            metric_name=ms.name,
                            value=None,
                            stratum=stratum_dict,
                            metadata={**meta_base, "nominal": alpha, "missing_ci": True},
                        )
                    )
                    continue
                lo, hi = bounds
                hit = 1.0 if lo <= y_star <= hi else 0.0
                rows.append(
                    MetricValue(
                        run_id=run_id,
                        record_id=record.record_id,
                        estimator_name=estimator_spec.name,
                        metric_name=ms.name,
                        value=hit,
                        stratum=stratum_dict,
                        metadata={**meta_base, "nominal": alpha},
                    )
                )
            return rows

        if ms.name == "ci_width":
            for alpha in ms.nominal_levels:
                bounds = _ci_interval(est, alpha)
                if bounds is None:
                    rows.append(
                        MetricValue(
                            run_id=run_id,
                            record_id=record.record_id,
                            estimator_name=estimator_spec.name,
                            metric_name=ms.name,
                            value=None,
                            stratum=stratum_dict,
                            metadata={**meta_base, "nominal": alpha, "missing_ci": True},
                        )
                    )
                else:
                    lo, hi = bounds
                    rows.append(
                        MetricValue(
                            run_id=run_id,
                            record_id=record.record_id,
                            estimator_name=estimator_spec.name,
                            metric_name=ms.name,
                            value=float(hi - lo),
                            stratum=stratum_dict,
                            metadata={**meta_base, "nominal": alpha},
                        )
                    )
            return rows

        if ms.name == "false_positive_lrd_rate":
            if not compatible or truth is None or truth.target_value is None:
                return rows
            if not est.valid or est.point is None:
                return rows
            params = dict(ms.parameters)
            threshold = float(
                params.get(
                    "threshold",
                    _default_false_positive_threshold(estimator_spec.target_estimand),
                )
            )
            null_max = float(
                params.get(
                    "null_max",
                    _default_false_positive_null_max(estimator_spec.target_estimand),
                )
            )
            if float(truth.target_value) > null_max:
                return rows
            val = 1.0 if float(est.point) >= threshold else 0.0
            rows.append(
                MetricValue(
                    run_id=run_id,
                    record_id=record.record_id,
                    estimator_name=estimator_spec.name,
                    metric_name=ms.name,
                    value=val,
                    stratum=stratum_dict,
                    metadata={
                        **meta_base,
                        "threshold": threshold,
                        "null_max": null_max,
                        "truth_target_value": float(truth.target_value),
                    },
                )
            )
            return rows

        if ms.name == "instability":
            raw = est.diagnostics.get("bootstrap_point_std")
            if raw is None:
                return rows
            rows.append(
                MetricValue(
                    run_id=run_id,
                    record_id=record.record_id,
                    estimator_name=estimator_spec.name,
                    metric_name=ms.name,
                    value=float(raw),
                    stratum=stratum_dict,
                    metadata=meta_base,
                )
            )
            return rows

        if ms.name not in METRIC_SPECS:
            raise ValueError(f"unsupported metric: {ms.name}")
        return rows

    def _estimator_disagreement_rows(
        self,
        *,
        run_id: str,
        record: SeriesRecord,
        metric_specs: Sequence[MetricSpec],
        estimator_specs: Sequence[EstimatorSpec],
        idx: dict[tuple[str, str], EstimateResult],
        stratum_dict: dict[str, Any],
        sk: tuple[tuple[str, Any], ...],
    ) -> list[MetricValue]:
        requested = {m.name: m for m in metric_specs if m.name in DISAGREEMENT_METRICS}
        if not requested:
            return []

        valid: list[tuple[EstimatorSpec, float]] = []
        missing: list[str] = []
        for es in estimator_specs:
            point = _valid_point(idx.get((record.record_id, es.name)))
            if point is None:
                missing.append(es.name)
            else:
                valid.append((es, point))

        min_estimators = min(
            int(dict(ms.parameters).get("min_estimators", 2)) for ms in requested.values()
        )
        if len(valid) < min_estimators:
            return []

        rows: list[MetricValue] = []
        meta_base: dict[str, Any] = {
            "stratum_key": sk,
            "n_estimators": len(valid),
            "estimator_names": tuple(es.name for es, _ in valid),
            "estimator_families": tuple(es.family for es, _ in valid),
        }
        if missing:
            meta_base["missing_estimator_names"] = tuple(missing)

        if "cross_estimator_dispersion" in requested:
            points = [point for _, point in valid]
            rows.append(
                MetricValue(
                    run_id=run_id,
                    record_id=record.record_id,
                    estimator_name="__all_estimators__",
                    metric_name="cross_estimator_dispersion",
                    value=_population_std(points),
                    stratum=stratum_dict,
                    metadata={**meta_base, "center": sum(points) / len(points)},
                )
            )

        if "pairwise_estimator_disagreement" in requested:
            for (es_a, point_a), (es_b, point_b) in combinations(valid, 2):
                rows.append(
                    MetricValue(
                        run_id=run_id,
                        record_id=record.record_id,
                        estimator_name=f"{es_a.name}__vs__{es_b.name}",
                        metric_name="pairwise_estimator_disagreement",
                        value=abs(point_a - point_b),
                        stratum=stratum_dict,
                        metadata={
                            **meta_base,
                            "estimator_a": es_a.name,
                            "estimator_b": es_b.name,
                            "family_a": es_a.family,
                            "family_b": es_b.family,
                        },
                    )
                )

        if "family_level_disagreement" in requested:
            by_family: dict[str, list[tuple[EstimatorSpec, float]]] = defaultdict(list)
            for es, point in valid:
                by_family[es.family].append((es, point))

            for family, family_vals in by_family.items():
                if len(family_vals) < min_estimators:
                    continue
                rows.append(
                    MetricValue(
                        run_id=run_id,
                        record_id=record.record_id,
                        estimator_name=f"family:{family}",
                        metric_name="family_level_disagreement",
                        value=_mean_abs_pairwise([point for _, point in family_vals]),
                        stratum=stratum_dict,
                        metadata={
                            **meta_base,
                            "comparison_scope": "within_family",
                            "family": family,
                            "family_estimator_names": tuple(es.name for es, _ in family_vals),
                        },
                    )
                )

            for family_a, family_b in combinations(sorted(by_family), 2):
                vals_a = by_family[family_a]
                vals_b = by_family[family_b]
                disagreements = [
                    abs(point_a - point_b)
                    for _, point_a in vals_a
                    for _, point_b in vals_b
                ]
                rows.append(
                    MetricValue(
                        run_id=run_id,
                        record_id=record.record_id,
                        estimator_name=f"family:{family_a}__vs__{family_b}",
                        metric_name="family_level_disagreement",
                        value=float(sum(disagreements) / len(disagreements)),
                        stratum=stratum_dict,
                        metadata={
                            **meta_base,
                            "comparison_scope": "between_family",
                            "family_a": family_a,
                            "family_b": family_b,
                            "family_a_estimator_names": tuple(es.name for es, _ in vals_a),
                            "family_b_estimator_names": tuple(es.name for es, _ in vals_b),
                        },
                    )
                )

        return rows

    def _parameter_variant_sensitivity_rows(
        self,
        *,
        run_id: str,
        record: SeriesRecord,
        metric_specs: Sequence[MetricSpec],
        estimator_specs: Sequence[EstimatorSpec],
        idx: dict[tuple[str, str], EstimateResult],
        stratum_dict: dict[str, Any],
        sk: tuple[tuple[str, Any], ...],
    ) -> list[MetricValue]:
        requested = {m.name: m for m in metric_specs if m.name in SENSITIVITY_METRICS}
        if not requested:
            return []

        grouped: dict[str, list[tuple[EstimatorSpec, str, float]]] = defaultdict(list)
        for es in estimator_specs:
            params = dict(es.parameter_schema)
            base_name = params.get("_base_estimator_name")
            variant_name = params.get("_variant_name")
            if base_name is None or variant_name is None:
                continue
            point = _valid_point(idx.get((record.record_id, es.name)))
            if point is None:
                continue
            grouped[str(base_name)].append((es, str(variant_name), point))

        if not grouped:
            return []

        min_variants = min(
            int(dict(ms.parameters).get("min_variants", 2)) for ms in requested.values()
        )
        rows: list[MetricValue] = []
        for base_name, variants in sorted(grouped.items()):
            if len(variants) < min_variants:
                continue
            points = [point for _, _, point in variants]
            meta_base: dict[str, Any] = {
                "stratum_key": sk,
                "base_estimator_name": base_name,
                "n_variants": len(variants),
                "variant_estimator_names": tuple(es.name for es, _, _ in variants),
                "variant_names": tuple(name for _, name, _ in variants),
            }

            if "parameter_variant_sensitivity" in requested:
                rows.append(
                    MetricValue(
                        run_id=run_id,
                        record_id=record.record_id,
                        estimator_name=base_name,
                        metric_name="parameter_variant_sensitivity",
                        value=_population_std(points),
                        stratum=stratum_dict,
                        metadata={**meta_base, "center": sum(points) / len(points)},
                    )
                )

            if "max_variant_drift" in requested:
                drift = max(abs(a - b) for a, b in combinations(points, 2))
                rows.append(
                    MetricValue(
                        run_id=run_id,
                        record_id=record.record_id,
                        estimator_name=base_name,
                        metric_name="max_variant_drift",
                        value=float(drift),
                        stratum=stratum_dict,
                        metadata=meta_base,
                    )
                )

        return rows

    def _aggregate(
        self,
        run_id: str,
        per_series: list[MetricValue],
        manifest: BenchmarkManifest,
    ) -> list[MetricValue]:
        grouped: dict[tuple[str, str, Any, Any], list[float]] = defaultdict(list)
        meta_stratum: dict[tuple[str, str, Any, Any], dict[str, Any]] = {}
        for mv in per_series:
            if mv.value is None:
                continue
            sk_t = mv.metadata.get("stratum_key")
            if not isinstance(sk_t, tuple):
                continue
            gk = (mv.estimator_name, mv.metric_name, sk_t, mv.metadata.get("nominal"))
            grouped[gk].append(float(mv.value))
            meta_stratum[gk] = dict(mv.stratum)

        out: list[MetricValue] = []
        for gk, vals in grouped.items():
            ename, mname, sk_tuple, nom = gk
            if mname == "rmse":
                mse = float(sum(vals) / len(vals))
                agg = mse**0.5
            else:
                agg = float(sum(vals) / len(vals))
            meta: dict[str, Any] = {"aggregation": "mean_within_stratum", "stratum_key": sk_tuple}
            if nom is not None:
                meta["nominal"] = nom
            out.append(
                MetricValue(
                    run_id=run_id,
                    record_id=None,
                    estimator_name=ename,
                    metric_name=mname,
                    value=agg,
                    stratum=meta_stratum[gk],
                    metadata=meta,
                )
            )

        # Stratum-wise coverage error vs nominal confidence level (YAML `levels`, e.g. 0.95)
        want_cerr = any(m.name == "coverage_error" for m in manifest.metric_specs)
        if want_cerr:
            for mv in list(out):
                if mv.metric_name != "coverage" or mv.value is None:
                    continue
                nom = mv.metadata.get("nominal")
                if nom is None:
                    continue
                target = float(nom)
                cerr = abs(float(mv.value) - target)
                md = dict(mv.metadata)
                md["aggregation"] = "coverage_error_from_coverage"
                out.append(
                    MetricValue(
                        run_id=run_id,
                        record_id=None,
                        estimator_name=mv.estimator_name,
                        metric_name="coverage_error",
                        value=cerr,
                        stratum=dict(mv.stratum),
                        metadata=md,
                    )
                )

        by_key: dict[tuple[str, str, Any], list[float]] = defaultdict(list)
        for mv in out:
            if mv.value is None:
                continue
            key = (mv.estimator_name, mv.metric_name, mv.metadata.get("nominal"))
            by_key[key].append(float(mv.value))

        global_rows: list[MetricValue] = []
        for (ename, mname, nom), vals in by_key.items():
            gval = float(sum(vals) / len(vals))
            gmeta: dict[str, Any] = {"aggregation": "mean_over_strata", "n_strata": len(vals)}
            if nom is not None:
                gmeta["nominal"] = nom
            global_rows.append(
                MetricValue(
                    run_id=run_id,
                    record_id=None,
                    estimator_name=ename,
                    metric_name=mname,
                    value=gval,
                    stratum={"level": "balanced_global"},
                    metadata=gmeta,
                )
            )
        return out + global_rows

    def _benchmark_uncertainty(
        self,
        run_id: str,
        per_series: list[MetricValue],
        aggregate: list[MetricValue],
        manifest: BenchmarkManifest,
    ) -> list[MetricValue]:
        spec = dict(manifest.uncertainty_spec)
        if not spec or spec.get("enabled") is False:
            return []

        n_boot = int(spec.get("n_bootstrap", 200))
        levels = tuple(float(x) for x in spec.get("ci_levels", (0.95,)))
        seed = int(spec.get("seed", manifest.seed_spec.get("global_seed", 0)))
        rng = np.random.default_rng(seed)

        metric_filter = {str(x) for x in spec.get("metrics", ())}
        paired_filter = {str(x) for x in spec.get("paired_metrics", ())}

        rows: list[MetricValue] = []
        rows.extend(
            self._aggregate_bootstrap_uncertainty(
                run_id=run_id,
                per_series=per_series,
                aggregate=aggregate,
                rng=rng,
                n_boot=n_boot,
                levels=levels,
                metric_filter=metric_filter,
            )
        )
        if bool(spec.get("paired", False)):
            rows.extend(
                self._paired_difference_uncertainty(
                    run_id=run_id,
                    per_series=per_series,
                    rng=rng,
                    n_boot=n_boot,
                    levels=levels,
                    metric_filter=paired_filter or metric_filter,
                )
            )
        return rows

    def _aggregate_bootstrap_uncertainty(
        self,
        *,
        run_id: str,
        per_series: list[MetricValue],
        aggregate: list[MetricValue],
        rng: np.random.Generator,
        n_boot: int,
        levels: tuple[float, ...],
        metric_filter: set[str],
    ) -> list[MetricValue]:
        grouped: dict[tuple[str, str, Any, Any], list[float]] = defaultdict(list)
        strata: dict[tuple[str, str, Any, Any], dict[str, Any]] = {}
        for mv in per_series:
            if mv.value is None or mv.record_id is None:
                continue
            if metric_filter and mv.metric_name not in metric_filter:
                continue
            sk_t = mv.metadata.get("stratum_key")
            if not isinstance(sk_t, tuple):
                continue
            key = (mv.estimator_name, mv.metric_name, sk_t, mv.metadata.get("nominal"))
            grouped[key].append(float(mv.value))
            strata[key] = dict(mv.stratum)

        rows: list[MetricValue] = []
        for key, vals in grouped.items():
            if not vals:
                continue
            ename, metric_name, sk_t, nominal = key
            samples: list[float] = []
            values = np.asarray(vals, dtype=float)
            for _ in range(n_boot):
                idx = rng.integers(0, values.size, size=values.size)
                samples.append(_metric_aggregate_value(metric_name, values[idx].tolist()))
            point = _metric_aggregate_value(metric_name, vals)
            for level in levels:
                lo, hi = _percentile_interval(samples, level)
                metadata: dict[str, Any] = {
                    "uncertainty_type": "aggregate_bootstrap",
                    "aggregation": "bootstrap_within_stratum",
                    "stratum_key": sk_t,
                    "n_bootstrap": n_boot,
                    "n_observations": len(vals),
                    "nominal": level,
                    "ci_low": lo,
                    "ci_high": hi,
                }
                if nominal is not None:
                    metadata["metric_nominal"] = nominal
                rows.append(
                    MetricValue(
                        run_id=run_id,
                        record_id=None,
                        estimator_name=ename,
                        metric_name=metric_name,
                        value=point,
                        stratum=strata[key],
                        metadata=metadata,
                    )
                )

        global_grouped: dict[tuple[str, str, Any], list[MetricValue]] = defaultdict(list)
        for mv in aggregate:
            if mv.value is None:
                continue
            if metric_filter and mv.metric_name not in metric_filter:
                continue
            if mv.stratum.get("level") == "balanced_global":
                continue
            global_grouped[(mv.estimator_name, mv.metric_name, mv.metadata.get("nominal"))].append(mv)

        for (ename, metric_name, metric_nominal), mvs in global_grouped.items():
            values = np.asarray([float(mv.value) for mv in mvs], dtype=float)
            if values.size == 0:
                continue
            samples = []
            for _ in range(n_boot):
                idx = rng.integers(0, values.size, size=values.size)
                samples.append(float(np.mean(values[idx])))
            point = float(np.mean(values))
            for level in levels:
                lo, hi = _percentile_interval(samples, level)
                metadata = {
                    "uncertainty_type": "aggregate_bootstrap",
                    "aggregation": "bootstrap_over_strata",
                    "n_bootstrap": n_boot,
                    "n_strata": int(values.size),
                    "nominal": level,
                    "ci_low": lo,
                    "ci_high": hi,
                }
                if metric_nominal is not None:
                    metadata["metric_nominal"] = metric_nominal
                rows.append(
                    MetricValue(
                        run_id=run_id,
                        record_id=None,
                        estimator_name=ename,
                        metric_name=metric_name,
                        value=point,
                        stratum={"level": "balanced_global"},
                        metadata=metadata,
                    )
                )
        return rows

    def _paired_difference_uncertainty(
        self,
        *,
        run_id: str,
        per_series: list[MetricValue],
        rng: np.random.Generator,
        n_boot: int,
        levels: tuple[float, ...],
        metric_filter: set[str],
    ) -> list[MetricValue]:
        by_group: dict[tuple[str, Any, Any], dict[str, dict[str, MetricValue]]] = defaultdict(
            lambda: defaultdict(dict)
        )
        for mv in per_series:
            if mv.value is None or mv.record_id is None:
                continue
            if metric_filter and mv.metric_name not in metric_filter:
                continue
            sk_t = mv.metadata.get("stratum_key")
            if not isinstance(sk_t, tuple):
                continue
            by_group[(mv.metric_name, sk_t, mv.metadata.get("nominal"))][mv.record_id][
                mv.estimator_name
            ] = mv

        rows: list[MetricValue] = []
        for (metric_name, sk_t, metric_nominal), by_record in by_group.items():
            estimator_names = sorted(
                {
                    ename
                    for estimator_map in by_record.values()
                    for ename in estimator_map
                }
            )
            for est_a, est_b in combinations(estimator_names, 2):
                diffs: list[float] = []
                stratum: dict[str, Any] | None = None
                for estimator_map in by_record.values():
                    mv_a = estimator_map.get(est_a)
                    mv_b = estimator_map.get(est_b)
                    if mv_a is None or mv_b is None or mv_a.value is None or mv_b.value is None:
                        continue
                    diffs.append(float(mv_a.value) - float(mv_b.value))
                    stratum = dict(mv_a.stratum)
                if not diffs:
                    continue
                values = np.asarray(diffs, dtype=float)
                samples = []
                for _ in range(n_boot):
                    idx = rng.integers(0, values.size, size=values.size)
                    samples.append(float(np.mean(values[idx])))
                point = float(np.mean(values))
                for level in levels:
                    lo, hi = _percentile_interval(samples, level)
                    metadata = {
                        "uncertainty_type": "paired_bootstrap_difference",
                        "aggregation": "paired_bootstrap_within_stratum",
                        "stratum_key": sk_t,
                        "estimator_a": est_a,
                        "estimator_b": est_b,
                        "n_bootstrap": n_boot,
                        "n_pairs": int(values.size),
                        "nominal": level,
                        "ci_low": lo,
                        "ci_high": hi,
                    }
                    if metric_nominal is not None:
                        metadata["metric_nominal"] = metric_nominal
                    rows.append(
                        MetricValue(
                            run_id=run_id,
                            record_id=None,
                            estimator_name=f"{est_a}__minus__{est_b}",
                            metric_name=metric_name,
                            value=point,
                            stratum=stratum or {},
                            metadata=metadata,
                        )
                    )
        return rows


class ObservationalEvaluator(GroundTruthEvaluator):
    """Observational metrics (no truth): runtime, CI width, instability, scale sensitivity proxy."""

    def __init__(self, estimators: EstimatorRegistry) -> None:
        self._estimator_registry = estimators

    def evaluate(
        self,
        manifest: BenchmarkManifest,
        records: Sequence[SeriesRecord],
        estimates: Sequence[EstimateResult],
    ) -> MetricBundle:
        if manifest.mode is not BenchmarkMode.OBSERVATIONAL:
            raise ValueError(
                f"ObservationalEvaluator does not support mode {manifest.mode.value!r}"
            )
        idx = _index_estimates(estimates)
        per_series: list[MetricValue] = []
        run_id = manifest.manifest_id

        for rec in records:
            for es in manifest.estimator_specs:
                est = idx.get((rec.record_id, es.name))
                if est is None:
                    continue
                validate_truth_compatibility(es, rec)
                compatible = True
                sk = stratum_key(rec)
                stratum_dict: dict[str, Any] = dict(stratum_from_record(rec))

                for ms in manifest.metric_specs:
                    validate_metric_admissibility(ms, manifest.mode, rec)
                    if ms.name in STRESS_PAIR_METRICS:
                        continue
                    if ms.name == "preprocessing_sensitivity":
                        for row in self._preprocessing_sensitivity_rows(
                            run_id=run_id,
                            manifest=manifest,
                            record=rec,
                            estimator_spec=es,
                            est=est,
                            ms=ms,
                            stratum_dict=stratum_dict,
                            sk=sk,
                        ):
                            per_series.append(row)
                        continue
                    if ms.name == "coverage_error":
                        continue
                    for row in self._per_series_rows(
                        run_id=run_id,
                        record=rec,
                        estimator_spec=es,
                        est=est,
                        ms=ms,
                        stratum_dict=stratum_dict,
                        sk=sk,
                        compatible=compatible,
                    ):
                        per_series.append(row)

            sk = stratum_key(rec)
            stratum_dict = dict(stratum_from_record(rec))
            for ms in manifest.metric_specs:
                if ms.name in DISAGREEMENT_METRICS or ms.name in SENSITIVITY_METRICS:
                    validate_metric_admissibility(ms, manifest.mode, rec)
            per_series.extend(
                self._estimator_disagreement_rows(
                    run_id=run_id,
                    record=rec,
                    metric_specs=manifest.metric_specs,
                    estimator_specs=manifest.estimator_specs,
                    idx=idx,
                    stratum_dict=stratum_dict,
                    sk=sk,
                )
            )
            per_series.extend(
                self._parameter_variant_sensitivity_rows(
                    run_id=run_id,
                    record=rec,
                    metric_specs=manifest.metric_specs,
                    estimator_specs=manifest.estimator_specs,
                    idx=idx,
                    stratum_dict=stratum_dict,
                    sk=sk,
                )
            )

        aggregate = self._aggregate(run_id, per_series, manifest)
        uncertainty = self._benchmark_uncertainty(run_id, per_series, aggregate, manifest)
        return MetricBundle(
            per_series=tuple(per_series),
            aggregate=tuple(aggregate),
            uncertainty=tuple(uncertainty),
            metadata={},
        )

    def _preprocessing_sensitivity_rows(
        self,
        *,
        run_id: str,
        manifest: BenchmarkManifest,
        record: SeriesRecord,
        estimator_spec: EstimatorSpec,
        est: EstimateResult,
        ms: MetricSpec,
        stratum_dict: dict[str, Any],
        sk: tuple[tuple[str, Any], ...],
    ) -> list[MetricValue]:
        meta_base: dict[str, Any] = {"stratum_key": sk}
        if not est.valid or est.point is None:
            return []
        eps = float(dict(manifest.preprocessing_spec).get("sensitivity_eps", 1e-4))
        builder = self._estimator_registry.get(estimator_spec.name)
        scaled = replace(record, values=record.values * (1.0 + eps))
        est2 = builder(estimator_spec).fit(scaled)
        if not est2.valid or est2.point is None:
            return [
                MetricValue(
                    run_id=run_id,
                    record_id=record.record_id,
                    estimator_name=estimator_spec.name,
                    metric_name=ms.name,
                    value=None,
                    stratum=stratum_dict,
                    metadata={**meta_base, "missing_alt": True, "sensitivity_eps": eps},
                )
            ]
        sens = abs(float(est2.point) - float(est.point)) / max(eps, 1e-12)
        return [
            MetricValue(
                run_id=run_id,
                record_id=record.record_id,
                estimator_name=estimator_spec.name,
                metric_name=ms.name,
                value=sens,
                stratum=stratum_dict,
                metadata={**meta_base, "sensitivity_eps": eps},
            )
        ]
