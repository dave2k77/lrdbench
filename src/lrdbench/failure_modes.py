from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FailureMode:
    code: str
    label: str
    description: str
    reason_prefixes: tuple[str, ...] = ()


FAILURE_MODES: tuple[FailureMode, ...] = (
    FailureMode(
        code="insufficient_signal",
        label="Insufficient signal",
        description="Estimator input is too short, degenerate, or otherwise lacks usable scale support.",
        reason_prefixes=("insufficient_signal_for_",),
    ),
    FailureMode(
        code="estimator_exception",
        label="Estimator exception",
        description="Estimator raised an exception that was captured as an invalid estimate.",
        reason_prefixes=("exception:",),
    ),
    FailureMode(
        code="missing_uncertainty",
        label="Missing uncertainty",
        description="Estimator produced a point estimate but did not produce requested intervals.",
        reason_prefixes=("missing_uncertainty",),
    ),
    FailureMode(
        code="invalid_fit",
        label="Invalid fit",
        description="Estimator returned no admissible point estimate for reasons not covered above.",
        reason_prefixes=(),
    ),
)

_BY_CODE = {mode.code: mode for mode in FAILURE_MODES}


def failure_mode_codes() -> tuple[str, ...]:
    return tuple(mode.code for mode in FAILURE_MODES)


def classify_failure_reason(reason: str | None) -> str:
    if reason is None or not reason:
        return "invalid_fit"
    for mode in FAILURE_MODES:
        if any(reason.startswith(prefix) for prefix in mode.reason_prefixes):
            return mode.code
    return "invalid_fit"


def failure_mode_for_code(code: str) -> FailureMode:
    return _BY_CODE[code]
