from __future__ import annotations

import pytest

from lrdbench.failure_modes import (
    FAILURE_MODES,
    classify_failure_reason,
    failure_mode_codes,
    failure_mode_for_code,
)


def test_failure_mode_codes_are_stable_and_unique() -> None:
    codes = failure_mode_codes()
    assert codes == (
        "insufficient_signal",
        "estimator_exception",
        "missing_uncertainty",
        "invalid_fit",
    )
    assert len(codes) == len(set(codes))
    assert all(mode.label and mode.description for mode in FAILURE_MODES)


@pytest.mark.parametrize(
    ("reason", "expected"),
    [
        ("insufficient_signal_for_rs", "insufficient_signal"),
        ("insufficient_signal_for_wavelet_whittle", "insufficient_signal"),
        ("exception:ValueError:bad fit", "estimator_exception"),
        ("missing_uncertainty:0.95", "missing_uncertainty"),
        ("numerically_singular_fit", "invalid_fit"),
        (None, "invalid_fit"),
    ],
)
def test_classify_failure_reason(reason: str | None, expected: str) -> None:
    assert classify_failure_reason(reason) == expected


def test_failure_mode_lookup_returns_taxonomy_entry() -> None:
    mode = failure_mode_for_code("insufficient_signal")
    assert mode.label == "Insufficient signal"
    assert mode.reason_prefixes == ("insufficient_signal_for_",)
