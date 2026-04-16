from __future__ import annotations

from lrdbench.contaminations import (
    HeavyTailNoiseContamination,
    LevelShiftContamination,
    OutliersContamination,
    PolynomialTrendContamination,
)
from lrdbench.estimators.gph import GPHEstimator
from lrdbench.estimators.rs import RSEstimator
from lrdbench.generators.arfima import ARFIMAGenerator
from lrdbench.generators.fbm import FBMGenerator
from lrdbench.generators.fgn import FGNGenerator
from lrdbench.interfaces import BaseEstimator
from lrdbench.registries import ContaminationRegistry, EstimatorRegistry, GeneratorRegistry
from lrdbench.schema import EstimatorSpec


def build_default_generator_registry() -> GeneratorRegistry:
    reg = GeneratorRegistry()
    reg.register("fGn", FGNGenerator())
    reg.register("fBm", FBMGenerator())
    reg.register("ARFIMA", ARFIMAGenerator())
    return reg


def build_default_contamination_registry() -> ContaminationRegistry:
    reg = ContaminationRegistry()
    reg.register("polynomial_trend", PolynomialTrendContamination())
    reg.register("outliers", OutliersContamination())
    reg.register("level_shift", LevelShiftContamination())
    reg.register("heavy_tail_noise", HeavyTailNoiseContamination())
    return reg


def build_default_estimator_registry() -> EstimatorRegistry:
    reg = EstimatorRegistry()

    def rs_builder(spec: EstimatorSpec) -> BaseEstimator:
        return RSEstimator(spec)

    def gph_builder(spec: EstimatorSpec) -> BaseEstimator:
        return GPHEstimator(spec)

    reg.register("RS", rs_builder)
    reg.register("GPH", gph_builder)
    return reg
