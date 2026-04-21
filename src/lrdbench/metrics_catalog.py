from __future__ import annotations

from dataclasses import replace
from typing import Any

from lrdbench.enums import BenchmarkMode, OptimisationDirection
from lrdbench.schema import MetricSpec

# Catalog per specification §2; nominal_levels filled from YAML where applicable.
METRIC_SPECS: dict[str, MetricSpec] = {
    "bias": MetricSpec(
        name="bias",
        symbol="bias",
        requires_truth=True,
        admissible_modes=(BenchmarkMode.GROUND_TRUTH, BenchmarkMode.STRESS_TEST),
        aggregation_rule="mean_over_stratum",
        optimisation_direction=OptimisationDirection.MINIMISE,
        unit=None,
    ),
    "mae": MetricSpec(
        name="mae",
        symbol="MAE",
        requires_truth=True,
        admissible_modes=(BenchmarkMode.GROUND_TRUTH, BenchmarkMode.STRESS_TEST),
        aggregation_rule="mean_over_stratum",
        optimisation_direction=OptimisationDirection.MINIMISE,
        unit=None,
    ),
    "rmse": MetricSpec(
        name="rmse",
        symbol="RMSE",
        requires_truth=True,
        admissible_modes=(BenchmarkMode.GROUND_TRUTH, BenchmarkMode.STRESS_TEST),
        aggregation_rule="mean_over_stratum",
        optimisation_direction=OptimisationDirection.MINIMISE,
        unit=None,
    ),
    "coverage": MetricSpec(
        name="coverage",
        symbol="Cov",
        requires_truth=True,
        admissible_modes=(BenchmarkMode.GROUND_TRUTH, BenchmarkMode.STRESS_TEST),
        aggregation_rule="mean_over_stratum",
        optimisation_direction=OptimisationDirection.MAXIMISE,
        unit="1",
    ),
    "coverage_error": MetricSpec(
        name="coverage_error",
        symbol="CErr",
        requires_truth=True,
        admissible_modes=(BenchmarkMode.GROUND_TRUTH, BenchmarkMode.STRESS_TEST),
        aggregation_rule="mean_over_stratum",
        optimisation_direction=OptimisationDirection.MINIMISE,
        unit="1",
    ),
    "ci_width": MetricSpec(
        name="ci_width",
        symbol="MW",
        requires_truth=False,
        admissible_modes=(
            BenchmarkMode.GROUND_TRUTH,
            BenchmarkMode.STRESS_TEST,
            BenchmarkMode.OBSERVATIONAL,
        ),
        aggregation_rule="mean_over_stratum",
        optimisation_direction=OptimisationDirection.MINIMISE,
        unit="1",
    ),
    "validity_rate": MetricSpec(
        name="validity_rate",
        symbol="VR",
        requires_truth=False,
        admissible_modes=(
            BenchmarkMode.GROUND_TRUTH,
            BenchmarkMode.STRESS_TEST,
            BenchmarkMode.OBSERVATIONAL,
        ),
        aggregation_rule="mean_over_stratum",
        optimisation_direction=OptimisationDirection.MAXIMISE,
        unit="1",
    ),
    "runtime": MetricSpec(
        name="runtime",
        symbol="RT",
        requires_truth=False,
        admissible_modes=(
            BenchmarkMode.GROUND_TRUTH,
            BenchmarkMode.STRESS_TEST,
            BenchmarkMode.OBSERVATIONAL,
        ),
        aggregation_rule="mean_over_stratum",
        optimisation_direction=OptimisationDirection.MINIMISE,
        unit="s",
    ),
    "instability": MetricSpec(
        name="instability",
        symbol="Instab",
        requires_truth=False,
        admissible_modes=(BenchmarkMode.OBSERVATIONAL,),
        aggregation_rule="mean_over_stratum",
        optimisation_direction=OptimisationDirection.MINIMISE,
        unit=None,
    ),
    "preprocessing_sensitivity": MetricSpec(
        name="preprocessing_sensitivity",
        symbol="PSens",
        requires_truth=False,
        admissible_modes=(BenchmarkMode.OBSERVATIONAL,),
        aggregation_rule="mean_over_stratum",
        optimisation_direction=OptimisationDirection.MINIMISE,
        unit=None,
    ),
    "estimate_drift": MetricSpec(
        name="estimate_drift",
        symbol="Drift",
        requires_truth=False,
        admissible_modes=(BenchmarkMode.STRESS_TEST,),
        aggregation_rule="mean_over_stratum",
        optimisation_direction=OptimisationDirection.MINIMISE,
        unit=None,
    ),
    "relative_degradation_ratio": MetricSpec(
        name="relative_degradation_ratio",
        symbol="RDR",
        requires_truth=True,
        admissible_modes=(BenchmarkMode.STRESS_TEST,),
        aggregation_rule="mean_over_stratum",
        optimisation_direction=OptimisationDirection.MINIMISE,
        unit="1",
    ),
    "validity_collapse": MetricSpec(
        name="validity_collapse",
        symbol="VCol",
        requires_truth=False,
        admissible_modes=(BenchmarkMode.STRESS_TEST,),
        aggregation_rule="mean_over_stratum",
        optimisation_direction=OptimisationDirection.MINIMISE,
        unit="1",
    ),
    "coverage_collapse": MetricSpec(
        name="coverage_collapse",
        symbol="CCol",
        requires_truth=True,
        admissible_modes=(BenchmarkMode.STRESS_TEST,),
        aggregation_rule="mean_over_stratum",
        optimisation_direction=OptimisationDirection.MINIMISE,
        unit="1",
    ),
    "false_positive_lrd_rate": MetricSpec(
        name="false_positive_lrd_rate",
        symbol="FPR",
        requires_truth=True,
        admissible_modes=(BenchmarkMode.GROUND_TRUTH, BenchmarkMode.STRESS_TEST),
        aggregation_rule="mean_over_stratum",
        optimisation_direction=OptimisationDirection.MINIMISE,
        unit="1",
        null_policy="skip_non_null_truth",
    ),
    "cross_estimator_dispersion": MetricSpec(
        name="cross_estimator_dispersion",
        symbol="XDisp",
        requires_truth=False,
        admissible_modes=(
            BenchmarkMode.GROUND_TRUTH,
            BenchmarkMode.STRESS_TEST,
            BenchmarkMode.OBSERVATIONAL,
        ),
        aggregation_rule="mean_over_stratum",
        optimisation_direction=OptimisationDirection.MINIMISE,
        unit=None,
    ),
    "pairwise_estimator_disagreement": MetricSpec(
        name="pairwise_estimator_disagreement",
        symbol="PairDis",
        requires_truth=False,
        admissible_modes=(
            BenchmarkMode.GROUND_TRUTH,
            BenchmarkMode.STRESS_TEST,
            BenchmarkMode.OBSERVATIONAL,
        ),
        aggregation_rule="mean_over_stratum",
        optimisation_direction=OptimisationDirection.MINIMISE,
        unit=None,
    ),
    "family_level_disagreement": MetricSpec(
        name="family_level_disagreement",
        symbol="FamDis",
        requires_truth=False,
        admissible_modes=(
            BenchmarkMode.GROUND_TRUTH,
            BenchmarkMode.STRESS_TEST,
            BenchmarkMode.OBSERVATIONAL,
        ),
        aggregation_rule="mean_over_stratum",
        optimisation_direction=OptimisationDirection.MINIMISE,
        unit=None,
    ),
    "parameter_variant_sensitivity": MetricSpec(
        name="parameter_variant_sensitivity",
        symbol="VarSens",
        requires_truth=False,
        admissible_modes=(
            BenchmarkMode.GROUND_TRUTH,
            BenchmarkMode.STRESS_TEST,
            BenchmarkMode.OBSERVATIONAL,
        ),
        aggregation_rule="mean_over_stratum",
        optimisation_direction=OptimisationDirection.MINIMISE,
        unit=None,
    ),
    "max_variant_drift": MetricSpec(
        name="max_variant_drift",
        symbol="MaxVarDrift",
        requires_truth=False,
        admissible_modes=(
            BenchmarkMode.GROUND_TRUTH,
            BenchmarkMode.STRESS_TEST,
            BenchmarkMode.OBSERVATIONAL,
        ),
        aggregation_rule="mean_over_stratum",
        optimisation_direction=OptimisationDirection.MINIMISE,
        unit=None,
    ),
}

_LEVEL_METRICS = frozenset({"coverage", "ci_width", "coverage_error", "coverage_collapse"})


def _default_nominal_levels(spec: MetricSpec) -> MetricSpec:
    if spec.name in _LEVEL_METRICS and not spec.nominal_levels:
        return replace(spec, nominal_levels=(0.95,))
    return spec


def metric_specs_from_manifest_entries(entries: list[Any]) -> tuple[MetricSpec, ...]:
    out: list[MetricSpec] = []
    for raw in entries:
        if isinstance(raw, str):
            key = raw
            if key not in METRIC_SPECS:
                raise ValueError(f"unknown metric: {key!r}")
            out.append(_default_nominal_levels(METRIC_SPECS[key]))
        elif isinstance(raw, dict):
            key = str(raw["name"])
            if key not in METRIC_SPECS:
                raise ValueError(f"unknown metric: {key!r}")
            base = METRIC_SPECS[key]
            levels_raw = raw.get("levels")
            params = {
                str(k): v
                for k, v in raw.items()
                if k not in {"name", "levels"}
            }
            if params:
                base = replace(base, parameters=params)
            if levels_raw is not None:
                levels = tuple(float(x) for x in levels_raw)
                out.append(replace(base, nominal_levels=levels))
            else:
                out.append(_default_nominal_levels(base))
        else:
            raise TypeError(f"invalid metric entry: {raw!r}")
    return tuple(out)


def resolve_metric_specs(names: list[str]) -> tuple[MetricSpec, ...]:
    """Backward-compatible resolver for string-only metric lists."""
    return metric_specs_from_manifest_entries(list(names))
