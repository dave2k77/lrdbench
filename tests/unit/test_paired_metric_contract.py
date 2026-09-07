from __future__ import annotations

from dataclasses import replace

import numpy as np
import pytest

from lrdbench.enums import BenchmarkMode, SourceType
from lrdbench.evaluator import GroundTruthEvaluator
from lrdbench.metrics_catalog import metric_specs_from_manifest_entries
from lrdbench.schema import (
    BenchmarkManifest,
    EstimateResult,
    EstimatorSpec,
    MetricBundle,
    SeriesRecord,
    TruthSpec,
)
from lrdbench.validation import ManifestValidationError, validate_ratio_uncertainty


def _manifest(names: list[str], target: str = "hurst_scaling_proxy") -> BenchmarkManifest:
    return BenchmarkManifest(
        manifest_id="pairs",
        name="pairs",
        mode=BenchmarkMode.STRESS_TEST,
        source_spec={"type": "test"},
        metric_specs=metric_specs_from_manifest_entries(names),
        estimator_specs=(
            EstimatorSpec(
                name="Toy",
                family="test",
                target_estimand=target,
                assumptions=(),
                supports_ci=True,
                supports_diagnostics=True,
            ),
        ),
    )


def _pair(
    index: int,
    clean: float | None,
    stressed: float | None,
    *,
    n: int = 128,
    clean_bounds: tuple[float, float] | None = None,
    stress_bounds: tuple[float, float] | None = None,
):
    truth = TruthSpec(
        process_family="fGn",
        generating_params={"H": 0.5},
        target_estimand="hurst_scaling_proxy",
        target_value=0.5,
    )
    record = SeriesRecord(
        record_id=f"c{index}",
        values=np.zeros(n),
        time_axis=None,
        sampling_rate=None,
        source_type=SourceType.SYNTHETIC,
        source_name="test",
        truth=truth,
        annotations={"stress_role": "clean", "n": n},
    )
    stress = replace(
        record,
        record_id=f"s{index}",
        source_type=SourceType.CONTAMINATED,
        annotations={
            "stress_role": "contaminated",
            "clean_record_id": record.record_id,
            "contamination_operator": "step_change",
            "n": n,
        },
    )
    fits = []
    for r, value, bounds in ((record, clean, clean_bounds), (stress, stressed, stress_bounds)):
        fits.append(
            EstimateResult(
                record_id=r.record_id,
                estimator_name="Toy",
                point=value,
                valid=value is not None,
                ci_low=bounds[0] if bounds else None,
                ci_high=bounds[1] if bounds else None,
            )
        )
    return (record, stress), fits


def _global(bundle: MetricBundle, name: str):
    return next(
        r
        for r in bundle.aggregate
        if r.metric_name == name and r.stratum.get("level") == "balanced_global"
    )


def test_signed_absolute_error_and_ratio_metrics_match_hand_calculation() -> None:
    names = [
        "estimate_drift",
        "absolute_estimate_drift",
        "signed_estimate_drift",
        "absolute_error_inflation",
        "relative_degradation_ratio",
        "paired_mae_ratio",
    ]
    a, ea = _pair(1, 0.6, 0.7)
    b, eb = _pair(2, 0.9, 0.6)
    bundle = GroundTruthEvaluator().evaluate(_manifest(names), (*a, *b), (*ea, *eb))
    expected = {
        "estimate_drift": 0.2,
        "absolute_estimate_drift": 0.2,
        "signed_estimate_drift": -0.1,
        "absolute_error_inflation": -0.1,
        "relative_degradation_ratio": 1.125,
        "paired_mae_ratio": 0.6,
    }
    for metric, value in expected.items():
        row = _global(bundle, metric)
        assert row.value == pytest.approx(value)
        assert row.metadata["n_attempted"] == row.metadata["n_included"] == 2
        assert row.metadata["n_missing"] == 0
    assert _global(bundle, "paired_mae_ratio").metadata["denominator_mae"] == pytest.approx(0.25)
    assert all(r.value is None for r in bundle.per_series if r.metric_name == "paired_mae_ratio")


def test_balanced_ratio_averages_error_components_before_dividing() -> None:
    records, fits = [], []
    for i, clean, stress, n in ((1, 1.5, 2.5, 128), (2, 3.5, 6.5, 128), (3, 1.5, 1.5, 256)):
        r, e = _pair(i, clean, stress, n=n)
        records.extend(r)
        fits.extend(e)
    result = GroundTruthEvaluator().evaluate(_manifest(["paired_mae_ratio"]), records, fits)
    global_row = _global(result, "paired_mae_ratio")
    assert global_row.value == pytest.approx(
        5 / 3
    )  # Not mean stratum ratios 1.5, nor pooled ratio 1.8.
    assert global_row.metadata["n_strata_included"] == 2


def test_zero_clean_error_stratum_remains_in_balanced_ratio() -> None:
    a, ea = _pair(1, 0.5, 2.5, n=128)
    b, eb = _pair(2, 2.5, 2.5, n=256)
    result = GroundTruthEvaluator().evaluate(_manifest(["paired_mae_ratio"]), (*a, *b), (*ea, *eb))
    assert _global(result, "paired_mae_ratio").value == 2.0
    per_stratum = [r for r in result.aggregate if r.stratum.get("n") == 128]
    assert per_stratum[0].value is None
    assert per_stratum[0].metadata["missing_reason"] == "near_zero_clean_mae"
    assert per_stratum[0].metadata["n_included"] == 1


def test_missing_and_invalid_pairs_are_counted_and_never_zero_filled() -> None:
    a, ea = _pair(1, 0.6, 0.7)
    b, eb = _pair(2, 0.6, None)
    c, ec = _pair(3, 0.6, 0.8)
    d, ed = _pair(4, 0.6, 0.9)
    manifest = _manifest(["absolute_estimate_drift", "paired_mae_ratio"])
    result = GroundTruthEvaluator().evaluate(manifest, (*a, *b, c[1], *d), (*ea, *eb, ec[1], ed[0]))
    for metric in ("absolute_estimate_drift", "paired_mae_ratio"):
        row = _global(result, metric)
        assert (
            row.metadata["n_attempted"],
            row.metadata["n_included"],
            row.metadata["n_missing"],
        ) == (4, 1, 3)
    assert _global(result, "absolute_estimate_drift").value == pytest.approx(0.1)
    missing = [
        r.metadata.get("missing_reason")
        for r in result.per_series
        if r.metric_name == "absolute_estimate_drift" and r.value is None
    ]
    assert set(missing) == {
        "invalid_point_pair",
        "missing_clean_estimate",
        "missing_stressed_estimate",
    }


def test_coverage_losses_and_net_loss_have_distinct_denominators_and_meanings() -> None:
    names = ["coverage_collapse", "coverage_loss_rate", "net_coverage_loss"]
    a, ea = _pair(1, 0.5, 0.7, clean_bounds=(0.4, 0.6), stress_bounds=(0.6, 0.8))
    b, eb = _pair(2, 0.7, 0.5, clean_bounds=(0.6, 0.8), stress_bounds=(0.4, 0.6))
    c, ec = _pair(3, 0.5, 0.7)
    result = GroundTruthEvaluator().evaluate(_manifest(names), (*a, *b, *c), (*ea, *eb, *ec))
    assert _global(result, "coverage_collapse").value == 0.5
    assert _global(result, "coverage_loss_rate").value == 0.5
    assert _global(result, "net_coverage_loss").value == 0.0
    for name in names:
        assert _global(result, name).metadata["n_missing"] == 1
        assert _global(result, name).metadata["n_included"] == 2


def test_paired_target_metrics_require_the_estimators_own_truth() -> None:
    a, estimates = _pair(1, 0.4, 0.5)
    manifest = _manifest(
        ["absolute_error_inflation", "paired_mae_ratio"], target="long_memory_parameter"
    )
    missing = GroundTruthEvaluator().evaluate(manifest, a, estimates)
    assert _global(missing, "absolute_error_inflation").value is None
    truth_d = TruthSpec(
        process_family="ARFIMA",
        generating_params={"d": 0.25},
        target_estimand="long_memory_parameter",
        target_value=0.25,
    )
    records = [replace(r, additional_truths=(truth_d,)) for r in a]
    result = GroundTruthEvaluator().evaluate(manifest, records, estimates)
    assert _global(result, "absolute_error_inflation").value == pytest.approx(0.1)
    assert _global(result, "paired_mae_ratio").value == pytest.approx(0.25 / 0.15)


@pytest.mark.parametrize(
    "uncertainty",
    [
        {"enabled": True},
        {"metrics": ["paired_mae_ratio"]},
        {"metrics": ["mae"], "paired": True, "paired_metrics": ["paired_mae_ratio"]},
    ],
)
def test_ratio_uncertainty_is_rejected_until_joint_resampling_exists(uncertainty: dict) -> None:
    with pytest.raises(ManifestValidationError, match="joint resampling"):
        validate_ratio_uncertainty({"paired_mae_ratio", "mae"}, uncertainty)


def test_explicitly_excluding_ratio_from_uncertainty_is_supported() -> None:
    validate_ratio_uncertainty({"paired_mae_ratio", "mae"}, {"metrics": ["mae"]})
    validate_ratio_uncertainty({"paired_mae_ratio"}, {"enabled": False})


def test_exceedance_alias_retains_threshold_rule_without_claiming_significance() -> None:
    records, estimates = _pair(1, 0.7, 0.5)
    result = GroundTruthEvaluator().evaluate(
        _manifest(["false_positive_lrd_rate", "persistence_exceedance_rate"]), records, estimates
    )
    old = _global(result, "false_positive_lrd_rate")
    new = _global(result, "persistence_exceedance_rate")
    assert old.value == new.value == 0.5
    assert all(r.metadata["calibrated_significance_test"] is False for r in result.per_series)
