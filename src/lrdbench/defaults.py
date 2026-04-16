from __future__ import annotations

from lrdbench.contaminations import (
    HeavyTailNoiseContamination,
    LevelShiftContamination,
    OutliersContamination,
    PolynomialTrendContamination,
)
from lrdbench.estimators.geometric import GHEEstimator, HiguchiEstimator
from lrdbench.estimators.spectral import (
    GPHEstimator,
    ModifiedLocalWhittleEstimator,
    PeriodogramRegressionEstimator,
    WhittleMLEEstimator,
)
from lrdbench.estimators.temporal import DFAEstimator, DMAEstimator, RSEstimator
from lrdbench.estimators.wavelet import (
    WaveletAbryVeitchEstimator,
    WaveletBardetEstimator,
    WaveletJensenEstimator,
    WaveletOLSEstimator,
    WaveletWhittleEstimator,
)
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

    def dfa_builder(spec: EstimatorSpec) -> BaseEstimator:
        return DFAEstimator(spec)

    def dma_builder(spec: EstimatorSpec) -> BaseEstimator:
        return DMAEstimator(spec)

    def higuchi_builder(spec: EstimatorSpec) -> BaseEstimator:
        return HiguchiEstimator(spec)

    def ghe_builder(spec: EstimatorSpec) -> BaseEstimator:
        return GHEEstimator(spec)

    def periodogram_builder(spec: EstimatorSpec) -> BaseEstimator:
        return PeriodogramRegressionEstimator(spec)

    def whittle_builder(spec: EstimatorSpec) -> BaseEstimator:
        return WhittleMLEEstimator(spec)

    def mlw_builder(spec: EstimatorSpec) -> BaseEstimator:
        return ModifiedLocalWhittleEstimator(spec)

    def w_av_builder(spec: EstimatorSpec) -> BaseEstimator:
        return WaveletAbryVeitchEstimator(spec)

    def w_bardet_builder(spec: EstimatorSpec) -> BaseEstimator:
        return WaveletBardetEstimator(spec)

    def w_ols_builder(spec: EstimatorSpec) -> BaseEstimator:
        return WaveletOLSEstimator(spec)

    def w_jensen_builder(spec: EstimatorSpec) -> BaseEstimator:
        return WaveletJensenEstimator(spec)

    def w_whittle_builder(spec: EstimatorSpec) -> BaseEstimator:
        return WaveletWhittleEstimator(spec)

    reg.register("RS", rs_builder)
    reg.register("GPH", gph_builder)
    reg.register("DFA", dfa_builder)
    reg.register("DMA", dma_builder)
    reg.register("Higuchi", higuchi_builder)
    reg.register("GHE", ghe_builder)
    reg.register("Periodogram", periodogram_builder)
    reg.register("WhittleMLE", whittle_builder)
    reg.register("ModifiedLocalWhittle", mlw_builder)
    reg.register("WaveletAbryVeitch", w_av_builder)
    reg.register("WaveletBardet", w_bardet_builder)
    reg.register("WaveletOLS", w_ols_builder)
    reg.register("WaveletJensen", w_jensen_builder)
    reg.register("WaveletWhittle", w_whittle_builder)
    return reg
