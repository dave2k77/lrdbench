"""Adversarial checks of the independent verification, not producer snapshots."""

from collections import Counter

import audit
import numpy as np
import pandas as pd
import pytest


def test_mixed_csv_types_preserve_exact_values_and_detect_changes():
    row = {
        "scope": "accuracy",
        "cell": "cell",
        "domain": "fGn",
        "interval_role": "none",
        "method": "M",
        "condition": "clean",
        "metric": "mae",
        "contrast": "",
        "value": 0.12345678901234567,
        "ci_low": "",
        "n": 512,
    }
    left, right = pd.DataFrame([row]), pd.DataFrame([row])
    right["value"] = right.value.map(repr)
    right["n"] = "512.0"
    audit.compare_exports(left, right)
    right["value"] = "0.123456789012345"
    with pytest.raises(AssertionError):
        audit.compare_exports(left, right)


def interval_fixture():
    low = np.full((4, 16), 0.3)
    high = np.full((4, 16), 0.7)
    available = np.ones((4, 16), bool)
    # One unavailable interval and one valid interval that misses the truth.
    available[0, 0] = False
    low[0, 0] = high[0, 0] = np.nan
    low[1, 0], high[1, 0] = 0.6, 0.9
    return {
        "low": low,
        "high": high,
        "available": available,
        "boundary": np.array([False, False, True, False]),
        "model": np.array([True, True, True, False]),
    }


def test_unavailable_intervals_stay_in_unconditional_denominator():
    expected = audit.interval_expected(interval_fixture(), {"cell": "fixture", "H_target": 0.5})
    base = ("GPH::narrow_band", "cbc_raw_percentile")
    unconditional = expected[*base, "unconditional_coverage", ""]
    conditional = expected[*base, "conditional_coverage", ""]
    assert unconditional["value"] == 0.5
    assert unconditional["denominator"] == 4
    assert conditional["value"] == 2 / 3
    assert conditional["denominator"] == 3


def test_width_difference_uses_common_availability_but_resamples_all_parents():
    data = interval_fixture()
    data["high"][:, 1] = [10, 0.8, 0.9, 1.0]
    expected = audit.interval_expected(data, {"cell": "fixture", "H_target": 0.5})
    key = (
        "GPH::narrow_band",
        "cbc_raw_basic_minus_cbc_raw_percentile",
        "mean_width_difference",
        "interval_construction",
    )
    assert expected[key]["parents_attempted"] == 4
    assert expected[key]["parents_used"] == 3
    # The huge first width is excluded from the common-available comparison.
    assert expected[key]["value"] == pytest.approx((0.2 + 0.2 + 0.3) / 3)


@pytest.mark.parametrize("successes", [0, 20])
def test_wilson_boundary_is_not_zero_uncertainty(successes):
    lo, hi = audit.wilson(successes, 20)
    assert hi - lo > 0.1
    assert lo >= -1e-15 and hi <= 1 + 1e-15


def test_literal_resampling_preserves_pairing():
    x = np.arange(12, dtype=float)
    samples = audit.sampled_means(np.column_stack([x, 10 + x]), "test")
    np.testing.assert_allclose(samples[:, 1] - samples[:, 0], 10)


def test_ratios_and_rmse_are_reconstructed_after_domain_weighting():
    def frame(clean, stress, mse):
        return pd.DataFrame(
            [
                {
                    "method": "M",
                    "condition": "clean",
                    "metric": "mae",
                    "contrast": "",
                    "value": clean,
                },
                {
                    "method": "M",
                    "condition": "stress",
                    "metric": "mae",
                    "contrast": "",
                    "value": stress,
                },
                {
                    "method": "M",
                    "condition": "stress",
                    "metric": "paired_mae_ratio",
                    "contrast": "",
                    "value": stress / clean,
                },
                {
                    "method": "M",
                    "condition": "clean",
                    "metric": "mse",
                    "contrast": "",
                    "value": mse,
                },
                {
                    "method": "M",
                    "condition": "clean",
                    "metric": "rmse",
                    "contrast": "",
                    "value": np.sqrt(mse),
                },
            ]
        )

    frames = [frame(1.0, 4.0, 1.0), frame(9.0, 18.0, 9.0)]
    matrices = [np.tile(f.value.to_numpy(), (audit.B, 1)) for f in frames]
    _, values, draws = audit.aggregate_expected(frames, matrices)
    assert values[2] == pytest.approx(2.2)  # Not the mean of 4 and 2.
    assert values[4] == pytest.approx(np.sqrt(5))  # Not the mean of 1 and 3.
    np.testing.assert_allclose(draws[:, 2], 2.2)


def test_domain_roster_mismatch_rejected():
    a = pd.DataFrame(
        [{"method": "M", "condition": "clean", "metric": "mae", "contrast": "", "value": 1.0}]
    )
    b = a.copy()
    b.loc[0, "method"] = "OTHER"
    with pytest.raises(AssertionError, match="domain roster"):
        audit.aggregate_expected([a, b], [np.ones((audit.B, 1))] * 2)


def test_nonfinite_bootstrap_position_makes_interval_unavailable():
    ci = {
        "method": "Higuchi",
        "candidate": "cbc_centered_basic",
        "pool": "cbc",
        "treatment": "centered",
        "point": 0.6,
    }
    distributions = np.full((9, audit.B), 0.5)
    distributions[4, 999] = np.nan
    assert audit.endpoints(ci, {"model": None}, distributions, 512) is None


def test_model_bootstrap_basic_uses_fitted_model_center():
    ci = {
        "method": "GHE",
        "candidate": "unknown_fgn_centered_basic",
        "pool": "fgn",
        "treatment": "centered",
        "point": 0.6,
    }
    distributions = np.tile(np.linspace(0.4, 0.8, audit.B), (9, 1))
    result = audit.endpoints(ci, {"model": {"H": 0.7}}, distributions, 512)
    np.testing.assert_allclose(result, [0.51, 0.89])


@pytest.mark.parametrize("corruption", ["value", "draw", "denominator", "support"])
def test_saved_summary_corruption_is_detected(tmp_path, corruption):
    samples = np.linspace(0.2, 0.8, audit.B)
    row = {
        "method": "M",
        "condition": "clean",
        "metric": "mae",
        "contrast": "",
        "value": 0.5,
        "ci_low": np.quantile(samples, 0.025),
        "ci_high": np.quantile(samples, 0.975),
        "mcse": 0.1,
        "bootstrap_se": samples.std(ddof=1),
        "parents_attempted": 4,
        "parents_used": 4,
        "parents_excluded": 0,
        "support": "all",
        "successes": "",
        "denominator": "",
        "requested_draws": audit.B,
        "used_draws": audit.B,
        "invalid_draws": 0,
        "interval_method": "joint_parent_percentile",
    }
    truth = {
        ("M", "clean", "mae", ""): {
            "value": 0.5,
            "samples": samples[audit.SELECTED].copy(),
            "parents_attempted": 4,
            "parents_used": 4,
            "parents_excluded": 0,
            "support": "all",
            "mcse": 0.1,
            "successes": None,
            "denominator": None,
        }
    }
    if corruption == "value":
        row["value"] = 0.6
    elif corruption == "draw":
        samples[0] = -10
    elif corruption == "denominator":
        row["parents_used"] = 3
    else:
        row["support"] = "only_successes"
    pd.DataFrame([row]).to_csv(tmp_path / "summary.csv", index=False)
    np.savez_compressed(tmp_path / "draws.npz", values=samples[:, None])
    with pytest.raises(AssertionError):
        audit.check_summary(tmp_path, truth, Counter())
