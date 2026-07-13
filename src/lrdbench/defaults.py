from __future__ import annotations

from lrdbench.contaminations import (
    HeavyTailNoiseContamination,
    LevelShiftContamination,
    OutliersContamination,
    PolynomialTrendContamination,
)
from lrdbench.estimators.data_driven import (
    MLCNNEstimator,
    MLLSTMEstimator,
    MLRandomForestEstimator,
    MLSVREstimator,
)
from lrdbench.estimators.discrimination import ThresholdHurstDiscriminator
from lrdbench.estimators.geometric import GHEEstimator, HiguchiEstimator
from lrdbench.estimators.spectral import (
    GPHEstimator,
    ModifiedLocalWhittleEstimator,
    PeriodogramBetaEstimator,
    PeriodogramRegressionEstimator,
    WhittleMLEEstimator,
)
from lrdbench.estimators.temporal import (
    AbsoluteMomentEstimator,
    DFAEstimator,
    DMAEstimator,
    RSEstimator,
    VarianceEstimator,
    VarianceResidualEstimator,
)
from lrdbench.estimators.timescale import ACFDecayEstimator
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
from lrdbench.generators.fou import FOUGenerator
from lrdbench.generators.mrw import MRWGenerator
from lrdbench.generators.multitimescale import MultiTimescaleGenerator
from lrdbench.generators.nonstationary_lrd import NonstationaryLRDGenerator
from lrdbench.interfaces import BaseEstimator
from lrdbench.preprocessing import (
    OracleDriftPreprocessing,
    OracleGainPreprocessing,
    OracleStateZScorePreprocessing,
    PolynomialDetrendPreprocessing,
    RollingZScorePreprocessing,
)
from lrdbench.registries import (
    ContaminationRegistry,
    EstimatorRegistry,
    GeneratorRegistry,
    PreprocessingRegistry,
)
from lrdbench.schema import EstimatorSpec


def build_default_generator_registry() -> GeneratorRegistry:
    reg = GeneratorRegistry()
    reg.register("fGn", FGNGenerator())
    reg.register("fBm", FBMGenerator())
    reg.register("ARFIMA", ARFIMAGenerator())
    reg.register("MRW", MRWGenerator())
    reg.register("fOU", FOUGenerator())
    reg.register("multi_timescale", MultiTimescaleGenerator())
    reg.register("NonstationaryLRD", NonstationaryLRDGenerator())
    return reg


def build_default_contamination_registry() -> ContaminationRegistry:
    reg = ContaminationRegistry()
    reg.register("polynomial_trend", PolynomialTrendContamination())
    reg.register("outliers", OutliersContamination())
    reg.register("level_shift", LevelShiftContamination())
    reg.register("heavy_tail_noise", HeavyTailNoiseContamination())
    return reg


def build_default_preprocessing_registry() -> PreprocessingRegistry:
    reg = PreprocessingRegistry()
    reg.register("rolling_zscore", RollingZScorePreprocessing())
    reg.register("polynomial_detrend", PolynomialDetrendPreprocessing())
    reg.register("oracle_gain", OracleGainPreprocessing())
    reg.register("oracle_drift", OracleDriftPreprocessing())
    reg.register("oracle_state_zscore", OracleStateZScorePreprocessing())
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

    def absolute_moment_builder(spec: EstimatorSpec) -> BaseEstimator:
        return AbsoluteMomentEstimator(spec)

    def variance_builder(spec: EstimatorSpec) -> BaseEstimator:
        return VarianceEstimator(spec)

    def variance_residual_builder(spec: EstimatorSpec) -> BaseEstimator:
        return VarianceResidualEstimator(spec)

    def higuchi_builder(spec: EstimatorSpec) -> BaseEstimator:
        return HiguchiEstimator(spec)

    def ghe_builder(spec: EstimatorSpec) -> BaseEstimator:
        return GHEEstimator(spec)

    def periodogram_builder(spec: EstimatorSpec) -> BaseEstimator:
        return PeriodogramRegressionEstimator(spec)

    def periodogram_beta_builder(spec: EstimatorSpec) -> BaseEstimator:
        return PeriodogramBetaEstimator(spec)

    def acf_decay_builder(spec: EstimatorSpec) -> BaseEstimator:
        return ACFDecayEstimator(spec)

    def threshold_hurst_discriminator_builder(spec: EstimatorSpec) -> BaseEstimator:
        return ThresholdHurstDiscriminator(spec)

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

    def ml_rf_builder(spec: EstimatorSpec) -> BaseEstimator:
        return MLRandomForestEstimator(spec)

    def ml_svr_builder(spec: EstimatorSpec) -> BaseEstimator:
        return MLSVREstimator(spec)

    def ml_cnn_builder(spec: EstimatorSpec) -> BaseEstimator:
        return MLCNNEstimator(spec)

    def ml_lstm_builder(spec: EstimatorSpec) -> BaseEstimator:
        return MLLSTMEstimator(spec)

    reg.register("RS", rs_builder)
    reg.register("GPH", gph_builder)
    reg.register("DFA", dfa_builder)
    reg.register("DMA", dma_builder)
    reg.register("AbsoluteMoment", absolute_moment_builder)
    reg.register("Variance", variance_builder)
    reg.register("VarianceResidual", variance_residual_builder)
    reg.register("Higuchi", higuchi_builder)
    reg.register("GHE", ghe_builder)
    reg.register("Periodogram", periodogram_builder)
    reg.register("PeriodogramBeta", periodogram_beta_builder)
    reg.register("ACFDecay", acf_decay_builder)
    reg.register("ThresholdHurstDiscriminator", threshold_hurst_discriminator_builder)
    reg.register("WhittleMLE", whittle_builder)
    reg.register("ModifiedLocalWhittle", mlw_builder)
    reg.register("WaveletAbryVeitch", w_av_builder)
    reg.register("WaveletBardet", w_bardet_builder)
    reg.register("WaveletOLS", w_ols_builder)
    reg.register("WaveletJensen", w_jensen_builder)
    reg.register("WaveletWhittle", w_whittle_builder)
    reg.register("MLRandomForest", ml_rf_builder)
    reg.register("MLSVR", ml_svr_builder)
    reg.register("MLCNN", ml_cnn_builder)
    reg.register("MLLSTM", ml_lstm_builder)
    return reg
