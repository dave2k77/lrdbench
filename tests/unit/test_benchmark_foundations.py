from __future__ import annotations

from dataclasses import replace
from itertools import permutations

import numpy as np
import pytest

from lrdbench.bootstrap import bootstrap_statistic_distribution
from lrdbench.contaminations.level_shift import (
    ConstantOffsetContamination,
    LevelShiftContamination,
    StepChangeContamination,
)
from lrdbench.contaminations.outliers import OutliersContamination
from lrdbench.defaults import build_default_contamination_registry
from lrdbench.enums import BenchmarkMode, SourceType
from lrdbench.estimators._fit_utils import fit_with_block_bootstrap
from lrdbench.estimators.spectral import GPHEstimator
from lrdbench.estimators.temporal import RSEstimator
from lrdbench.evaluator import GroundTruthEvaluator, _ci_interval
from lrdbench.execution import estimate_cache_key
from lrdbench.leaderboard import WeightedRankLeaderboardBuilder
from lrdbench.metrics_catalog import METRIC_SPECS, metric_specs_from_manifest_entries
from lrdbench.runner import _stable_seed
from lrdbench.schema import (
    BenchmarkManifest,
    EstimateResult,
    EstimatorSpec,
    LeaderboardSpec,
    MetricBundle,
    MetricValue,
    ProvenanceRecord,
    SeriesRecord,
)


def _spec(name: str = "RS", **params: object) -> EstimatorSpec:
    return EstimatorSpec(
        name=name,
        family="temporal",
        target_estimand="hurst_scaling_proxy",
        assumptions=(),
        supports_ci=True,
        supports_diagnostics=True,
        parameter_schema=params,
    )


def _record() -> SeriesRecord:
    return SeriesRecord(
        record_id="clean",
        values=np.random.default_rng(42).normal(size=256),
        time_axis=None,
        sampling_rate=100.0,
        source_type=SourceType.SYNTHETIC,
        source_name="test",
    )


def _rank(
    values: dict[str, dict[str, float | None]],
    *,
    components: tuple[str, ...] = ("validity_rate",),
    tie: str = "best_primary_metric",
) -> dict[str, tuple[int, float]]:
    manifest = BenchmarkManifest(
        manifest_id="ranking",
        name="ranking",
        mode=BenchmarkMode.GROUND_TRUTH,
        source_spec={"type": "generator_grid"},
        estimator_specs=tuple(_spec(n) for n in values),
        metric_specs=tuple(METRIC_SPECS[c] for c in components),
        leaderboard_specs=(
            LeaderboardSpec(
                mode=BenchmarkMode.GROUND_TRUTH,
                component_metrics=components,
                weights=dict.fromkeys(components, 1 / len(components)),
                tie_break_rule=tie,
            ),
        ),
    )
    metrics = MetricBundle(
        per_series=(),
        aggregate=tuple(
            MetricValue(
                run_id="ranking",
                record_id=None,
                estimator_name=name,
                metric_name=metric,
                value=value,
                stratum={"level": "balanced_global"},
            )
            for name, entries in values.items()
            for metric, value in entries.items()
        ),
    )
    return {
        r.estimator_name: (r.rank, r.score)
        for r in WeightedRankLeaderboardBuilder().build(manifest, metrics)
    }


def test_equal_values_have_average_component_ranks_and_shared_competition_rank() -> None:
    for names in permutations(("Alpha", "Zulu", "Other")):
        result = _rank(
            {
                names[0]: {"validity_rate": 1},
                names[1]: {"validity_rate": 1},
                names[2]: {"validity_rate": 0.5},
            }
        )
        assert result[names[0]] == result[names[1]] == (1, 1.5)
        assert result[names[2]] == (3, 3)


@pytest.mark.parametrize("metric", ["mae", "validity_rate"])
@pytest.mark.parametrize("missing", [None, float("nan"), float("inf"), -float("inf")])
def test_missing_components_rank_worst_in_both_directions(
    metric: str, missing: float | None
) -> None:
    result = _rank({"A": {metric: missing}, "Z": {metric: 0.2}, "NoRows": {}}, components=(metric,))
    assert result["Z"] == (1, 1)
    assert result["A"] == result["NoRows"] == (2, 4)


def test_declared_primary_or_named_metric_breaks_equal_scores() -> None:
    values = {"Alpha": {"mae": 0.3, "validity_rate": 1}, "Zulu": {"mae": 0.1, "validity_rate": 0.5}}
    assert _rank(values, components=("mae", "validity_rate"))["Zulu"] == (1, 1.5)
    assert _rank(values, components=("mae", "validity_rate"), tie="validity_rate")["Alpha"] == (
        1,
        1.5,
    )
    result = _rank(values, components=("mae", "validity_rate"), tie="none")
    assert result["Alpha"] == result["Zulu"] == (1, 1.5)


def test_bootstrap_accounts_for_each_invalid_value_and_exception() -> None:
    draws = iter([0.1, None, float("nan"), float("inf"), ValueError("injected"), 0.9])

    def statistic(x: np.ndarray) -> float | None:
        value = next(draws)
        if isinstance(value, Exception):
            raise value
        return value

    diag: dict[str, object] = {}
    result = bootstrap_statistic_distribution(
        np.arange(8.0), np.random.default_rng(1), statistic, n_boot=6, block_len=2, diagnostics=diag
    )
    np.testing.assert_array_equal(result, [0.1, 0.9])
    assert diag == {
        "bootstrap_replicates_attempted": 6,
        "bootstrap_replicates_used": 2,
        "bootstrap_replicates_invalid": 3,
        "bootstrap_replicates_failed": 1,
        "bootstrap_failure_reasons": {"none": 1, "nonfinite": 2, "exception:ValueError": 1},
    }


def test_zero_bootstrap_does_not_call_statistic_and_negative_count_is_rejected() -> None:
    def never(x: np.ndarray) -> float:
        raise AssertionError("must not be called")

    assert (
        bootstrap_statistic_distribution(
            np.arange(8.0), np.random.default_rng(1), never, n_boot=0, block_len=2
        ).size
        == 0
    )
    with pytest.raises(ValueError, match="nonnegative"):
        bootstrap_statistic_distribution(
            np.arange(8.0), np.random.default_rng(1), never, n_boot=-1, block_len=2
        )


def test_bootstrap_warns_if_failures_have_no_diagnostics_sink() -> None:
    with pytest.warns(RuntimeWarning, match="2 invalid"):
        bootstrap_statistic_distribution(
            np.arange(8.0), np.random.default_rng(1), lambda x: None, n_boot=2, block_len=2
        )


def test_valid_point_survives_bootstrap_failures_with_unavailable_interval() -> None:
    record = _record()

    def statistic(x: np.ndarray) -> float:
        if x is record.values:
            return 0.6
        raise ValueError("injected bootstrap failure")

    result = fit_with_block_bootstrap(
        record,
        _spec(n_bootstrap=8),
        statistic=statistic,
        estimator_version="test",
        failure_reason="point failed",
    )
    assert result.valid and result.point == 0.6
    assert result.bootstrap_cis == () and result.ci_low is None and result.ci_high is None
    assert result.diagnostics["bootstrap_replicates_attempted"] == 8
    assert result.diagnostics["bootstrap_replicates_failed"] == 8
    assert result.diagnostics["ci_unavailable_reason"] == "insufficient_replicates"
    assert result.warnings == ("bootstrap_draws_discarded",)


@pytest.mark.parametrize("name", ["RS", "GPH", "shared"])
@pytest.mark.parametrize("draws", [0, 8])
def test_all_bootstrap_paths_honour_zero_and_keep_nominal_levels(name: str, draws: int) -> None:
    spec = _spec(name, n_bootstrap=draws, ci_levels=[0.8])
    if name == "shared":
        result = fit_with_block_bootstrap(
            _record(),
            spec,
            statistic=lambda x: float(np.mean(x)),
            estimator_version="test",
            failure_reason="failed",
        )
    else:
        result = (RSEstimator(spec) if name == "RS" else GPHEstimator(spec)).fit(_record())
    assert result.valid
    assert result.diagnostics["bootstrap_replicates_attempted"] == draws
    assert result.diagnostics["bootstrap_replicates_used"] == draws
    assert result.ci_low is None and result.ci_high is None
    assert _ci_interval(result, 0.95) is None
    assert (_ci_interval(result, 0.8) is not None) == (draws > 0)


def test_interval_lookup_rejects_wrong_nominal_nonfinite_reversed_and_failed_fits() -> None:
    native = EstimateResult(record_id="r", estimator_name="RS", point=0.6, ci_low=0.4, ci_high=0.8)
    assert _ci_interval(native, 0.95) == (0.4, 0.8)
    assert _ci_interval(replace(native, bootstrap_cis=((0.8, 0.4, 0.8),)), 0.95) is None
    for invalid in (
        replace(native, valid=False),
        replace(native, point=float("nan")),
        replace(native, ci_low=0.9),
        replace(native, ci_high=float("inf")),
    ):
        assert _ci_interval(invalid, 0.95) is None


def test_bootstrap_seed_is_part_of_estimate_cache_key() -> None:
    record = _record()
    provenance = ProvenanceRecord(
        record_id="clean", parent_id=None, manifest_id="test", created_at="test", seed=1
    )
    a = replace(record, provenance=provenance)
    b = replace(record, provenance=replace(provenance, seed=2))
    assert estimate_cache_key(a, _spec()) != estimate_cache_key(b, _spec())


@pytest.mark.parametrize("position", [0.25, 0.5, 0.75])
@pytest.mark.parametrize("shift", [-1.0, 0.0, 2.0])
def test_step_has_exact_onset_amplitude_and_provenance(position: float, shift: float) -> None:
    record = _record()
    original = record.values.copy()
    out = StepChangeContamination().apply(
        record,
        params={"shift": shift, "position": position},
        seed=1,
        manifest_id="m",
        new_record_id="step",
    )
    index = int(position * len(original))
    np.testing.assert_array_equal(out.values[:index], original[:index])
    np.testing.assert_allclose(
        out.values[index:] - original[index:], shift * np.std(original), atol=1e-14
    )
    np.testing.assert_array_equal(record.values, original)
    assert out.annotations["clean_record_id"] == "clean"
    assert out.contamination_history[-1].name == "step_change"
    assert out.contamination_history[-1].params["position"] == position


@pytest.mark.parametrize("position", [0, 1, -0.2, float("nan"), 0.00001])
def test_step_rejects_empty_segments(position: float) -> None:
    with pytest.raises(ValueError):
        StepChangeContamination().apply(
            _record(),
            params={"shift": 1, "position": position},
            seed=1,
            manifest_id="m",
            new_record_id="step",
        )


def test_constant_offset_keeps_legacy_values_and_new_name() -> None:
    kwargs = {"params": {"shift": 1.0}, "seed": 1, "manifest_id": "m", "new_record_id": "offset"}
    record = _record()
    legacy = LevelShiftContamination().apply(record, **kwargs)
    explicit = ConstantOffsetContamination().apply(record, **kwargs)
    np.testing.assert_array_equal(legacy.values, explicit.values)
    assert explicit.contamination_history[-1].name == "constant_offset"
    registry = build_default_contamination_registry()
    assert registry.get("step_change").name == "step_change"
    assert registry.get("constant_offset").name == "constant_offset"


def test_zero_outlier_rate_is_identity() -> None:
    record = _record()
    out = OutliersContamination().apply(
        record, params={"rate": 0, "amplitude": 100}, seed=1, manifest_id="m", new_record_id="zero"
    )
    np.testing.assert_array_equal(out.values, record.values)


def test_ci_availability_counts_failed_points_and_missing_intervals() -> None:
    records = tuple(replace(_record(), record_id=str(i)) for i in range(4))
    manifest = BenchmarkManifest(
        manifest_id="availability",
        name="availability",
        mode=BenchmarkMode.GROUND_TRUTH,
        source_spec={"type": "test"},
        estimator_specs=(_spec(),),
        metric_specs=metric_specs_from_manifest_entries(
            [{"name": "ci_availability", "levels": [0.8, 0.95]}]
        ),
    )
    estimates = (
        EstimateResult(
            record_id="0",
            estimator_name="RS",
            point=0.5,
            bootstrap_cis=((0.8, 0.3, 0.7), (0.95, 0.2, 0.8)),
        ),
        EstimateResult(
            record_id="1", estimator_name="RS", point=0.5, bootstrap_cis=((0.8, 0.3, 0.7),)
        ),
        EstimateResult(record_id="2", estimator_name="RS", point=0.5),
        EstimateResult(record_id="3", estimator_name="RS", point=None, valid=False),
    )
    result = GroundTruthEvaluator().evaluate(manifest, records, estimates)
    assert len(result.per_series) == 8
    global_rows = {
        m.metadata["nominal"]: m.value
        for m in result.aggregate
        if m.stratum.get("level") == "balanced_global"
    }
    assert global_rows == {0.8: 0.5, 0.95: 0.25}


def test_global_seed_changes_stream_and_identical_inputs_reproduce_it() -> None:
    assert _stable_seed(1, "suite", "fGn", 0) == _stable_seed(1, "suite", "fGn", 0)
    assert _stable_seed(1, "suite", "fGn", 0) != _stable_seed(2, "suite", "fGn", 0)
    assert _stable_seed(1, "suite", "fGn", 0) != _stable_seed(1, "suite", "fGn", 1)
