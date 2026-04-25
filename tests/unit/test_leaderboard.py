from __future__ import annotations

from lrdbench.enums import BenchmarkMode, OptimisationDirection
from lrdbench.leaderboard import WeightedRankLeaderboardBuilder
from lrdbench.schema import (
    BenchmarkManifest,
    EstimatorSpec,
    LeaderboardSpec,
    MetricBundle,
    MetricSpec,
    MetricValue,
)


def _estimator(name: str) -> EstimatorSpec:
    return EstimatorSpec(
        name=name,
        family="time_domain",
        target_estimand="hurst_scaling_proxy",
        assumptions=(),
        supports_ci=False,
        supports_diagnostics=False,
    )


def test_leaderboard_ignores_synthetic_aggregate_metric_rows() -> None:
    manifest = BenchmarkManifest(
        manifest_id="lb",
        name="leaderboard",
        mode=BenchmarkMode.GROUND_TRUTH,
        source_spec={"type": "generator_grid"},
        estimator_specs=(_estimator("A"), _estimator("B")),
        metric_specs=(
            MetricSpec(
                name="mae",
                symbol="MAE",
                requires_truth=True,
                admissible_modes=(BenchmarkMode.GROUND_TRUTH,),
                aggregation_rule="mean",
                optimisation_direction=OptimisationDirection.MINIMISE,
            ),
            MetricSpec(
                name="cross_estimator_dispersion",
                symbol="XDisp",
                requires_truth=False,
                admissible_modes=(BenchmarkMode.GROUND_TRUTH,),
                aggregation_rule="mean",
                optimisation_direction=OptimisationDirection.MINIMISE,
            ),
        ),
        leaderboard_specs=(
            LeaderboardSpec(
                mode=BenchmarkMode.GROUND_TRUTH,
                component_metrics=("mae", "cross_estimator_dispersion"),
                weights={"mae": 0.8, "cross_estimator_dispersion": 0.2},
                name="overall",
            ),
        ),
    )
    bundle = MetricBundle(
        per_series=(),
        aggregate=(
            MetricValue(
                run_id="lb",
                record_id=None,
                estimator_name="A",
                metric_name="mae",
                value=0.2,
                stratum={"level": "balanced_global"},
            ),
            MetricValue(
                run_id="lb",
                record_id=None,
                estimator_name="B",
                metric_name="mae",
                value=0.1,
                stratum={"level": "balanced_global"},
            ),
            MetricValue(
                run_id="lb",
                record_id=None,
                estimator_name="__all_estimators__",
                metric_name="cross_estimator_dispersion",
                value=0.01,
                stratum={"level": "balanced_global"},
            ),
        ),
    )

    rows = WeightedRankLeaderboardBuilder().build(manifest, bundle)

    assert [row.estimator_name for row in rows] == ["B", "A"]
    assert "__all_estimators__" not in {row.estimator_name for row in rows}
