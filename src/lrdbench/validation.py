from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from lrdbench.enums import BenchmarkMode
from lrdbench.schema import (
    BenchmarkManifest,
    EstimatorSpec,
    LeaderboardSpec,
    MetricSpec,
    SeriesRecord,
)


class ManifestValidationError(ValueError):
    pass


def _validate_execution_block(spec: Mapping[str, Any] | None) -> None:
    ex = dict(spec or {})
    allowed = frozenset({"max_workers", "estimate_cache_dir", "cache_read", "cache_write"})
    bad = set(ex) - allowed
    if bad:
        raise ManifestValidationError(f"unknown execution block keys: {sorted(bad)}")
    if "max_workers" in ex:
        mw = ex["max_workers"]
        if isinstance(mw, bool):
            raise ManifestValidationError(
                "execution.max_workers must be an integer >= 1 (YAML booleans are not allowed here)"
            )
        if isinstance(mw, int):
            mw_i = mw
        else:
            try:
                mw_i = int(mw)
            except (TypeError, ValueError) as exc:
                raise ManifestValidationError(
                    "execution.max_workers must be an integer >= 1"
                ) from exc
        if mw_i < 1:
            raise ManifestValidationError("execution.max_workers must be an integer >= 1")
    if "estimate_cache_dir" in ex:
        raw = ex["estimate_cache_dir"]
        if not isinstance(raw, str) or not raw.strip():
            raise ManifestValidationError("execution.estimate_cache_dir must be a non-empty string")
    for key in ("cache_read", "cache_write"):
        if key in ex and not isinstance(ex[key], bool):
            raise ManifestValidationError(f"execution.{key} must be a boolean")


def _validate_uncertainty_block(spec: Mapping[str, Any] | None) -> None:
    uq = dict(spec or {})
    allowed = frozenset(
        {
            "enabled",
            "n_bootstrap",
            "ci_levels",
            "seed",
            "metrics",
            "paired",
            "paired_metrics",
        }
    )
    bad = set(uq) - allowed
    if bad:
        raise ManifestValidationError(f"unknown uncertainty block keys: {sorted(bad)}")
    if "enabled" in uq and not isinstance(uq["enabled"], bool):
        raise ManifestValidationError("uncertainty.enabled must be a boolean")
    if "n_bootstrap" in uq:
        raw = uq["n_bootstrap"]
        if isinstance(raw, bool):
            raise ManifestValidationError("uncertainty.n_bootstrap must be an integer >= 1")
        try:
            n_boot = int(raw)
        except (TypeError, ValueError) as exc:
            raise ManifestValidationError(
                "uncertainty.n_bootstrap must be an integer >= 1"
            ) from exc
        if n_boot < 1:
            raise ManifestValidationError("uncertainty.n_bootstrap must be an integer >= 1")
    if "seed" in uq:
        raw_seed = uq["seed"]
        if isinstance(raw_seed, bool):
            raise ManifestValidationError("uncertainty.seed must be an integer")
        try:
            int(raw_seed)
        except (TypeError, ValueError) as exc:
            raise ManifestValidationError("uncertainty.seed must be an integer") from exc
    if "ci_levels" in uq:
        levels = uq["ci_levels"]
        if not isinstance(levels, list) or not levels:
            raise ManifestValidationError("uncertainty.ci_levels must be a non-empty list")
        for level in levels:
            if not (0.0 < float(level) < 1.0):
                raise ManifestValidationError(
                    f"uncertainty.ci_levels values must lie in (0,1), got {level!r}"
                )
    for key in ("metrics", "paired_metrics"):
        if key in uq:
            vals = uq[key]
            if not isinstance(vals, list) or not all(isinstance(x, str) for x in vals):
                raise ManifestValidationError(f"uncertainty.{key} must be a list of strings")
    if "paired" in uq and not isinstance(uq["paired"], bool):
        raise ManifestValidationError("uncertainty.paired must be a boolean")


def validate_truth_compatibility(estimator_spec: EstimatorSpec, record: SeriesRecord) -> None:
    if record.truth is None:
        return
    if estimator_spec.target_estimand != record.truth.target_estimand:
        raise ManifestValidationError(
            f"estimator {estimator_spec.name!r} targets {estimator_spec.target_estimand!r} "
            f"but record truth targets {record.truth.target_estimand!r}"
        )


def validate_metric_admissibility(
    metric_spec: MetricSpec,
    mode: BenchmarkMode,
    record: SeriesRecord | None = None,
) -> None:
    if mode not in metric_spec.admissible_modes:
        raise ManifestValidationError(
            f"metric {metric_spec.name!r} is not admissible in mode {mode.value!r}"
        )
    if metric_spec.requires_truth and mode is BenchmarkMode.OBSERVATIONAL:
        raise ManifestValidationError(
            f"metric {metric_spec.name!r} requires truth and cannot be used in observational mode"
        )
    if metric_spec.requires_truth and record is not None and record.truth is None:
        raise ManifestValidationError(
            f"metric {metric_spec.name!r} requires truth but record {record.record_id!r} has none"
        )


def validate_manifest(manifest: BenchmarkManifest, *, strict_unknown_keys: bool = True) -> None:
    data = manifest.raw_yaml or {}
    if strict_unknown_keys:
        allowed = {
            "manifest_id",
            "name",
            "description",
            "mode",
            "source",
            "contamination",
            "segmentation",
            "preprocessing",
            "estimators",
            "metrics",
            "leaderboards",
            "report",
            "execution",
            "uncertainty",
            "seeds",
            "validation",
        }
        bad = set(data) - allowed
        if bad:
            raise ManifestValidationError(f"unknown top-level manifest keys: {sorted(bad)}")

    # MV1
    if not manifest.manifest_id or not manifest.name:
        raise ManifestValidationError("manifest_id and name are required")
    if not manifest.estimator_specs:
        raise ManifestValidationError("at least one estimator is required")
    if not manifest.metric_specs:
        raise ManifestValidationError("at least one metric is required")

    # MV2 / MV3
    if manifest.mode is BenchmarkMode.STRESS_TEST and not manifest.contamination_spec:
        raise ManifestValidationError("stress_test mode requires a non-empty contamination block")
    if manifest.mode is BenchmarkMode.STRESS_TEST:
        ops = manifest.contamination_spec.get("operators")
        if not ops:
            raise ManifestValidationError(
                "stress_test mode requires contamination.operators with at least one operator entry"
            )
    if manifest.mode is BenchmarkMode.GROUND_TRUTH and manifest.contamination_spec:
        raise ManifestValidationError(
            "ground_truth mode must not declare contamination unless explicitly permitted"
        )
    if manifest.mode is BenchmarkMode.OBSERVATIONAL and manifest.contamination_spec:
        raise ManifestValidationError(
            "observational mode must not declare a contamination block in this release"
        )

    # MV4
    if manifest.mode is BenchmarkMode.OBSERVATIONAL:
        src = manifest.source_spec
        if src.get("type") == "generator_grid":
            raise ManifestValidationError(
                "observational mode cannot use synthetic generator_grid source"
            )
        allowed_obs_sources = frozenset({"csv_series_index", "inline_table"})
        st = src.get("type")
        if st not in allowed_obs_sources:
            raise ManifestValidationError(
                f"observational source.type must be one of {sorted(allowed_obs_sources)}, got {st!r}"
            )
        series = src.get("series")
        if not isinstance(series, list) or len(series) == 0:
            raise ManifestValidationError("observational source requires a non-empty series list")

    # MV5
    for e in manifest.estimator_specs:
        if not e.target_estimand:
            raise ManifestValidationError(f"estimator {e.name!r} must declare target_estimand")

    # MV5b (Phase 5 execution)
    _validate_execution_block(manifest.execution_spec)
    _validate_uncertainty_block(manifest.uncertainty_spec)

    # MV6
    metric_names = {x.name for x in manifest.metric_specs}
    if "coverage_error" in metric_names and "coverage" not in metric_names:
        raise ManifestValidationError(
            "coverage_error requires a coverage metric in the metrics block"
        )
    if "coverage_collapse" in metric_names and "coverage" not in metric_names:
        raise ManifestValidationError(
            "coverage_collapse requires a coverage metric in the metrics block"
        )
    if "relative_degradation_ratio" in metric_names and "mae" not in metric_names:
        raise ManifestValidationError(
            "relative_degradation_ratio requires an mae metric in the metrics block"
        )
    for m in manifest.metric_specs:
        validate_metric_admissibility(m, manifest.mode)
        for a in m.nominal_levels:
            if not (0.0 < float(a) < 1.0):
                raise ManifestValidationError(
                    f"nominal level for metric {m.name!r} must lie in (0,1), got {a!r}"
                )

    # MV7 / MV8 leaderboards
    for lb in manifest.leaderboard_specs:
        if lb.mode is not manifest.mode:
            raise ManifestValidationError(
                f"leaderboard {lb.component_metrics!r} mode {lb.mode.value!r} "
                f"does not match manifest mode {manifest.mode.value!r}"
            )
        wsum = sum(lb.weights.values())
        if abs(wsum - 1.0) > 1e-6:
            raise ManifestValidationError(f"leaderboard weights must sum to 1, got {wsum}")
        for comp in lb.component_metrics:
            if comp == "coverage_error":
                if "coverage" not in metric_names:
                    raise ManifestValidationError("coverage_error requires coverage metric")
                continue
            if comp not in metric_names:
                raise ManifestValidationError(
                    f"leaderboard component {comp!r} is not declared in metrics block"
                )


def estimator_spec_from_mapping(m: Mapping[str, Any]) -> EstimatorSpec:
    assumptions_raw = m.get("assumptions", ())
    if isinstance(assumptions_raw, str):
        assumptions: tuple[str, ...] = (assumptions_raw,)
    else:
        assumptions = tuple(str(x) for x in assumptions_raw)
    cites_raw = m.get("reference_citations", ())
    cites = tuple(str(x) for x in cites_raw) if cites_raw else ()
    return EstimatorSpec(
        name=str(m["name"]),
        family=str(m.get("family", "unknown")),
        target_estimand=str(m["target_estimand"]),
        assumptions=assumptions,
        supports_ci=bool(m.get("supports_ci", False)),
        supports_diagnostics=bool(m.get("supports_diagnostics", False)),
        input_requirements=dict(m.get("input_requirements", {})),
        parameter_schema=dict(m.get("params", {})),
        reference_citations=cites,
        version=m.get("version"),
    )


def leaderboard_spec_from_mapping(m: Mapping[str, Any]) -> LeaderboardSpec:
    weights = {str(k): float(v) for k, v in m["weights"].items()}
    return LeaderboardSpec(
        mode=BenchmarkMode(str(m["mode"])),
        component_metrics=tuple(str(x) for x in m["component_metrics"]),
        weights=weights,
        ranking_rule=str(m.get("ranking_rule", "weighted_rank")),
        tie_break_rule=str(m.get("tie_break_rule", "best_primary_metric")),
        name=str(m["name"]) if m.get("name") is not None else None,
    )


def report_spec_from_mapping(m: Mapping[str, Any]) -> Any:
    from lrdbench.schema import ReportSpec

    lbs_raw = m.get("leaderboards", [])
    lbs = tuple(leaderboard_spec_from_mapping(x) for x in lbs_raw)
    return ReportSpec(
        formats=tuple(str(x) for x in m.get("formats", ("html", "csv"))),
        leaderboards=lbs,
        figure_set=tuple(str(x) for x in m.get("figure_set", ())),
        table_set=tuple(str(x) for x in m.get("table_set", ())),
        include_raw_exports=bool(m.get("include_raw_exports", True)),
        include_provenance=bool(m.get("include_provenance", True)),
        include_environment=bool(m.get("include_environment", True)),
        export_root=str(m.get("export_root", "reports")),
        naming_policy=str(m.get("naming_policy", "deterministic")),
        compression_policy=m.get("compression_policy"),
    )
