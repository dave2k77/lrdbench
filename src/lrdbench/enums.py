from __future__ import annotations

from enum import StrEnum


class BenchmarkMode(StrEnum):
    GROUND_TRUTH = "ground_truth"
    STRESS_TEST = "stress_test"
    OBSERVATIONAL = "observational"


class SourceType(StrEnum):
    SYNTHETIC = "synthetic"
    CONTAMINATED = "contaminated"
    OBSERVATIONAL = "observational"
    CUSTOM = "custom"


class OptimisationDirection(StrEnum):
    MINIMISE = "minimise"
    MAXIMISE = "maximise"
