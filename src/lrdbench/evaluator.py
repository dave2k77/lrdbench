from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from dataclasses import replace
from typing import Any

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

        aggregate = self._aggregate(run_id, per_series, manifest)
        return MetricBundle(per_series=tuple(per_series), aggregate=tuple(aggregate), metadata={})

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

        aggregate = self._aggregate(run_id, per_series, manifest)
        return MetricBundle(per_series=tuple(per_series), aggregate=tuple(aggregate), metadata={})

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
