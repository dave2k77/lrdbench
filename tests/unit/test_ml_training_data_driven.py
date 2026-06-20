from __future__ import annotations

import sys
import types
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from lrdbench.defaults import build_default_contamination_registry, build_default_generator_registry
from lrdbench.enums import BenchmarkMode, SourceType
from lrdbench.estimators import data_driven
from lrdbench.estimators.data_driven import (
    MLCNNEstimator,
    MLLSTMEstimator,
    MLRandomForestEstimator,
    MLSVREstimator,
    feature_vector,
    fixed_length_sequence,
    standardize_series,
    train_sklearn_model,
)
from lrdbench.manifest import manifest_from_mapping
from lrdbench.ml_training import prepare_data_driven_estimators, requested_data_driven_estimators
from lrdbench.runner import BenchmarkRunner
from lrdbench.schema import BenchmarkManifest, EstimatorSpec, SeriesRecord, TruthSpec

# Tests that monkeypatch ``torch_available`` to True still need torch actually
# installed (they import torch or build real models). Skip them when the optional
# ``nn`` extra is absent, e.g. on CI installing only ``.[test,dev]``.
requires_torch = pytest.mark.skipif(
    not data_driven.torch_available(),
    reason="torch not installed; install lrdbench[nn]",
)


class PredictConstant:
    def __init__(self, value: float) -> None:
        self.value = value
        self.fit_x_shape: tuple[int, ...] | None = None

    def fit(self, x: np.ndarray, y: np.ndarray) -> PredictConstant:
        self.fit_x_shape = tuple(x.shape)
        self.fit_y_shape = tuple(y.shape)
        return self

    def predict(self, x: np.ndarray) -> np.ndarray:
        return np.full(x.shape[0], self.value, dtype=float)


class FakeRandomForestRegressor(PredictConstant):
    def __init__(self, **kwargs: Any) -> None:
        super().__init__(0.73)
        self.kwargs = kwargs


class FakeSVR(PredictConstant):
    def __init__(self, **kwargs: Any) -> None:
        super().__init__(0.41)
        self.kwargs = kwargs


class FakeStandardScaler:
    pass


def fake_make_pipeline(*steps: Any) -> PredictConstant:
    model = PredictConstant(0.52)
    model.steps = steps  # type: ignore[attr-defined]
    return model


def _spec(name: str, params: dict[str, Any] | None = None) -> EstimatorSpec:
    return EstimatorSpec(
        name=name,
        family="data_driven",
        target_estimand="hurst_scaling_proxy",
        assumptions=(),
        supports_ci=False,
        supports_diagnostics=True,
        parameter_schema=params or {},
    )


def _record(values: np.ndarray, *, truth: float | None = None, record_id: str = "r0") -> SeriesRecord:
    truth_spec = None
    if truth is not None:
        truth_spec = TruthSpec(
            process_family="test",
            generating_params={},
            target_estimand="hurst_scaling_proxy",
            target_value=truth,
        )
    return SeriesRecord(
        record_id=record_id,
        values=values,
        time_axis=None,
        sampling_rate=None,
        source_type=SourceType.SYNTHETIC,
        source_name="test",
        truth=truth_spec,
    )


def _install_fake_sklearn(monkeypatch: pytest.MonkeyPatch) -> None:
    sklearn = types.ModuleType("sklearn")
    ensemble = types.ModuleType("sklearn.ensemble")
    pipeline = types.ModuleType("sklearn.pipeline")
    preprocessing = types.ModuleType("sklearn.preprocessing")
    svm = types.ModuleType("sklearn.svm")
    ensemble.RandomForestRegressor = FakeRandomForestRegressor  # type: ignore[attr-defined]
    pipeline.make_pipeline = fake_make_pipeline  # type: ignore[attr-defined]
    preprocessing.StandardScaler = FakeStandardScaler  # type: ignore[attr-defined]
    svm.SVR = FakeSVR  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "sklearn", sklearn)
    monkeypatch.setitem(sys.modules, "sklearn.ensemble", ensemble)
    monkeypatch.setitem(sys.modules, "sklearn.pipeline", pipeline)
    monkeypatch.setitem(sys.modules, "sklearn.preprocessing", preprocessing)
    monkeypatch.setitem(sys.modules, "sklearn.svm", svm)


def test_feature_vector_cleans_non_finite_values() -> None:
    x = np.sin(np.linspace(0.0, 10.0, 64))
    x[[3, 7, 11]] = [np.nan, np.inf, -np.inf]

    feats = feature_vector(x, max_lag=4)

    assert feats.shape == (33,)
    assert np.all(np.isfinite(feats))


def test_feature_vector_rejects_too_short_signal() -> None:
    assert feature_vector(np.arange(15, dtype=float)).size == 0


def test_fixed_length_sequence_handles_empty_constant_and_bad_length() -> None:
    assert fixed_length_sequence(np.asarray([], dtype=float), length=16).size == 0
    assert np.array_equal(fixed_length_sequence(np.ones(20), length=16), np.zeros(16, dtype=np.float32))
    with pytest.raises(ValueError, match="sequence_length"):
        fixed_length_sequence(np.arange(20, dtype=float), length=7)


def test_fixed_length_sequence_downsamples_by_block_mean_aggregation() -> None:
    # 16 -> 8 means factor 2: block means [0.5, 2.5, ..., 14.5], then standardised.
    out = fixed_length_sequence(np.arange(16, dtype=float), length=8)
    assert out.shape == (8,)
    expected = np.arange(16, dtype=float).reshape(8, 2).mean(axis=1)
    expected = (expected - expected.mean()) / expected.std()
    assert np.allclose(out, expected, atol=1e-5)


def test_fixed_length_sequence_factor_one_is_contiguous_crop() -> None:
    # length <= n < 2*length -> factor 1 -> crop of the leading `length` samples.
    x = np.linspace(0.0, 1.0, 30)
    out = fixed_length_sequence(x, length=16)
    expected = standardize_series(x[:16])
    assert out.shape == (16,)
    assert np.allclose(out, expected, atol=1e-5)


def test_fixed_length_sequence_upsamples_short_series_to_target_length() -> None:
    out = fixed_length_sequence(np.sin(np.linspace(0.0, 6.0, 40)), length=64)
    assert out.shape == (64,)
    assert np.all(np.isfinite(out))


@pytest.mark.statistical
def test_fixed_length_sequence_preserves_hurst_under_downsampling() -> None:
    gen = build_default_generator_registry().get("fGn")
    rec = gen.generate(
        record_id="hurst-preserve", params={"H": 0.8, "n": 8192}, seed=20260619, manifest_id="t"
    )
    full = np.asarray(rec.values, dtype=float)
    downsampled = fixed_length_sequence(full, length=512)  # factor 16 aggregation

    def aggregated_variance_hurst(x: np.ndarray) -> float:
        x = x - float(np.mean(x))
        scales = [2, 4, 8, 16, 32]
        variances = []
        for m in scales:
            trimmed = x[: x.size - (x.size % m)].reshape(-1, m).mean(axis=1)
            variances.append(float(np.var(trimmed)))
        slope = float(np.polyfit(np.log(scales), np.log(variances), 1)[0])
        return 1.0 + slope / 2.0

    h_full = aggregated_variance_hurst(full)
    h_down = aggregated_variance_hurst(downsampled)
    assert h_full > 0.65  # source genuinely carries long-range dependence
    # Block-mean downsampling keeps the scaling; linear interpolation would not.
    assert abs(h_full - h_down) < 0.2


def test_sklearn_estimators_report_missing_dependency(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(data_driven, "sklearn_available", lambda: False)
    rec = _record(np.sin(np.linspace(0.0, 4.0, 64)))

    for estimator_cls in (MLRandomForestEstimator, MLSVREstimator):
        out = estimator_cls(_spec(estimator_cls.__name__, {"model_path": "missing.pkl"})).fit(rec)
        assert not out.valid
        assert out.point is None
        assert out.failure_reason == "missing_optional_dependency:scikit-learn:install lrdbench[ml]"


def test_torch_estimators_report_missing_dependency(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(data_driven, "torch_available", lambda: False)
    rec = _record(np.sin(np.linspace(0.0, 4.0, 64)))

    for estimator_cls in (MLCNNEstimator, MLLSTMEstimator):
        out = estimator_cls(_spec(estimator_cls.__name__, {"model_path": "missing.pt"})).fit(rec)
        assert not out.valid
        assert out.point is None
        assert out.failure_reason == "missing_optional_dependency:torch:install lrdbench[nn]"


def test_sklearn_estimator_requires_model_path(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(data_driven, "sklearn_available", lambda: True)

    out = MLRandomForestEstimator(_spec("MLRandomForest")).fit(_record(np.arange(32, dtype=float)))

    assert not out.valid
    assert out.failure_reason == "missing_trained_model_path"


def test_sklearn_estimator_loads_pickled_model_and_clips_prediction(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(data_driven, "sklearn_available", lambda: True)
    data_driven._cached_pickle.cache_clear()
    model_path = tmp_path / "model.pkl"
    data_driven._write_pickle(
        model_path,
        {"model": PredictConstant(1.3), "training_summary": {"n_training_records": 4}},
    )
    rec = _record(np.sin(np.linspace(0.0, 12.0, 128)))

    out = MLRandomForestEstimator(_spec("MLRandomForest", {"model_path": str(model_path)})).fit(rec)

    assert out.valid
    assert out.point == 1.0
    assert out.diagnostics["model_kind"] == "random_forest_regressor"
    assert out.diagnostics["training_summary"] == {"n_training_records": 4}


def test_sklearn_estimator_rejects_short_signal(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(data_driven, "sklearn_available", lambda: True)
    model_path = tmp_path / "model.pkl"
    data_driven._write_pickle(model_path, {"model": PredictConstant(0.5)})

    out = MLSVREstimator(_spec("MLSVR", {"model_path": str(model_path)})).fit(
        _record(np.arange(10, dtype=float))
    )

    assert not out.valid
    assert out.failure_reason == "insufficient_signal_for_data_driven_features"


def test_train_sklearn_model_writes_random_forest_bundle(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install_fake_sklearn(monkeypatch)
    artefact_path = tmp_path / "rf.pkl"
    records = [
        _record(np.sin(np.linspace(0.0, 4.0, 64)) + i, truth=0.4 + 0.1 * i, record_id=f"r{i}")
        for i in range(3)
    ]

    summary = train_sklearn_model(
        "MLRandomForest",
        records,
        params={"n_estimators": 5, "random_state": 2, "_validation_fraction": 0.34},
        artefact_path=artefact_path,
    )

    assert artefact_path.exists()
    assert summary["n_training_records"] == 3
    assert summary["n_fit_records"] == 2
    assert summary["n_validation_records"] == 1
    assert "validation_mae" in summary


def test_train_sklearn_model_writes_svr_bundle(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fake_sklearn(monkeypatch)
    records = [
        _record(np.cos(np.linspace(0.0, 5.0, 64)) + i, truth=0.3 + 0.05 * i, record_id=f"s{i}")
        for i in range(2)
    ]

    summary = train_sklearn_model("MLSVR", records, params={}, artefact_path=tmp_path / "svr.pkl")

    assert summary["n_training_records"] == 2
    assert summary["n_fit_records"] == 2
    assert summary["n_validation_records"] == 0


def test_train_sklearn_model_requires_two_valid_records(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fake_sklearn(monkeypatch)
    records = [_record(np.arange(64, dtype=float), truth=0.5)]

    with pytest.raises(ValueError, match="at least two"):
        train_sklearn_model("MLRandomForest", records, params={}, artefact_path=tmp_path / "rf.pkl")


def test_train_sklearn_model_rejects_unknown_estimator(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fake_sklearn(monkeypatch)
    records = [
        _record(np.sin(np.linspace(0.0, 4.0, 64)) + i, truth=0.4 + 0.1 * i, record_id=f"u{i}")
        for i in range(2)
    ]

    with pytest.raises(ValueError, match="unsupported sklearn"):
        train_sklearn_model("MLUnknown", records, params={}, artefact_path=tmp_path / "bad.pkl")


def test_requested_data_driven_estimators_deduplicates_base_names() -> None:
    specs = (
        _spec("MLRandomForest::fast", {"_base_estimator_name": "MLRandomForest"}),
        _spec("MLRandomForest::slow", {"_base_estimator_name": "MLRandomForest"}),
        _spec("RS"),
        _spec("MLCNN::tiny", {"_base_estimator_name": "MLCNN"}),
    )

    assert requested_data_driven_estimators(specs) == ("MLRandomForest", "MLCNN")


def test_prepare_data_driven_estimators_materializes_training_and_updates_specs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    manifest = manifest_from_mapping(
        {
            "manifest_id": "ml-train-test",
            "name": "ml train test",
            "mode": "ground_truth",
            "source": {
                "type": "generator_grid",
                "generators": [{"family": "fGn", "params": {"H": [0.5], "n": [32]}, "replicates": 1}],
            },
            "ml_training": {
                "enabled": True,
                "target_estimand": "hurst_scaling_proxy",
                "validation_fraction": 0.25,
                "source": {
                    "type": "generator_grid",
                    "generators": [
                        {"family": "fGn", "params": {"H": [0.4, 0.6], "n": [64]}, "replicates": 1}
                    ],
                },
                "contamination": {
                    "include_clean": True,
                    "operators": [{"name": "heavy_tail_noise", "params": {"scale": [0.1], "df": [5.0]}}],
                },
            },
            "estimators": [
                {
                    "name": "MLRandomForest::tiny",
                    "family": "data_driven",
                    "target_estimand": "hurst_scaling_proxy",
                    "params": {"_base_estimator_name": "MLRandomForest", "n_estimators": 3},
                }
            ],
            "metrics": ["mae"],
        }
    )

    def fake_train(
        estimator_name: str,
        records: list[SeriesRecord],
        *,
        params: dict[str, Any],
        artefact_path: Path,
    ) -> dict[str, Any]:
        assert estimator_name == "MLRandomForest"
        assert len(records) == 4
        assert {r.annotations["ml_training_role"] for r in records} == {"clean", "contaminated"}
        assert params["_validation_fraction"] == 0.25
        artefact_path.write_bytes(b"model")
        return {"n_training_records": len(records)}

    monkeypatch.setattr("lrdbench.ml_training.train_sklearn_model", fake_train)

    updated = prepare_data_driven_estimators(
        manifest,
        generators=build_default_generator_registry(),
        contaminations=build_default_contamination_registry(),
        run_id="run-1",
        artefact_root=tmp_path,
        global_seed=123,
    )

    params = dict(updated.estimator_specs[0].parameter_schema)
    assert Path(params["_trained_model_path"]).exists()
    summary_path = Path(params["_ml_training_summary_path"])
    assert summary_path.exists()
    assert "MLRandomForest" in summary_path.read_text(encoding="utf-8")


def test_prepare_data_driven_estimators_is_noop_when_training_disabled() -> None:
    manifest = BenchmarkManifest(
        manifest_id="noop",
        name="noop",
        mode=BenchmarkMode.GROUND_TRUTH,
        source_spec={},
        estimator_specs=(_spec("MLRandomForest", {"model_path": "pretrained.pkl"}),),
        ml_training_spec={"enabled": False},
    )

    assert prepare_data_driven_estimators(
        manifest,
        generators=build_default_generator_registry(),
        contaminations=build_default_contamination_registry(),
        run_id="run-noop",
        artefact_root=Path("reports"),
        global_seed=1,
    ) is manifest


def test_runner_invokes_data_driven_preparation(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []

    def fake_prepare(manifest: BenchmarkManifest, **kwargs: Any) -> BenchmarkManifest:
        calls.append(kwargs["run_id"])
        return manifest

    monkeypatch.setattr("lrdbench.runner.prepare_data_driven_estimators", fake_prepare)
    manifest = manifest_from_mapping(
        {
            "manifest_id": "runner-ml-hook",
            "name": "runner ml hook",
            "mode": "ground_truth",
            "source": {
                "type": "generator_grid",
                "generators": [{"family": "fGn", "params": {"H": [0.5], "n": [64]}, "replicates": 1}],
            },
            "estimators": [
                {
                    "name": "RS",
                    "family": "temporal",
                    "target_estimand": "hurst_scaling_proxy",
                    "params": {"n_bootstrap": 0},
                }
            ],
            "metrics": ["mae", "runtime"],
            "report": {"formats": ["csv"], "export_root": str(tmp_path)},
        }
    )

    output = BenchmarkRunner(discover_plugins=False).run(manifest, base_dir=tmp_path)

    assert calls == [output.run_id]
    assert output.result_store_path is not None


def test_feature_vector_spectral_bands_are_non_overlapping() -> None:
    for n in (16, 32, 64, 128, 256, 512, 1024):
        x = np.sin(np.linspace(0.0, 10.0, n))
        spec = np.abs(np.fft.rfft(x)) ** 2
        n_spec = spec.size
        end0 = max(2, n_spec // 32)
        end1 = max(end0 + 1, n_spec // 16)
        end2 = max(end1 + 1, n_spec // 8)
        end3 = max(end2 + 1, n_spec // 4)
        bands = [spec[1:end0].size, spec[end0:end1].size, spec[end1:end2].size, spec[end2:end3].size]
        assert all(b > 0 for b in bands), f"overlap/empty bands at n={n}: {bands}"


def test_sklearn_estimator_clips_to_training_bounds(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(data_driven, "sklearn_available", lambda: True)
    data_driven._cached_pickle.cache_clear()
    model_path = tmp_path / "model.pkl"
    data_driven._write_pickle(
        model_path,
        {
            "model": PredictConstant(1.3),
            "training_summary": {"n_training_records": 4, "target_min": 0.2, "target_max": 0.9},
            "max_lag": 16,
        },
    )
    rec = _record(np.sin(np.linspace(0.0, 12.0, 128)))

    out = MLRandomForestEstimator(_spec("MLRandomForest", {"model_path": str(model_path)})).fit(rec)

    assert out.valid
    assert out.point == 0.9  # clipped to training max


def test_sklearn_estimator_rejects_max_lag_mismatch(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(data_driven, "sklearn_available", lambda: True)
    data_driven._cached_pickle.cache_clear()
    model_path = tmp_path / "model.pkl"
    data_driven._write_pickle(
        model_path,
        {"model": PredictConstant(0.5), "training_summary": {"n_training_records": 4}, "max_lag": 16},
    )
    rec = _record(np.sin(np.linspace(0.0, 12.0, 128)))

    out = MLRandomForestEstimator(_spec("MLRandomForest", {"model_path": str(model_path), "max_lag": 32})).fit(rec)

    assert not out.valid
    assert "max_lag_mismatch" in out.failure_reason or "max_lag_mismatch" in (out.failure_reason or "")


@requires_torch
def test_train_torch_model_skips_empty_records(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(data_driven, "torch_available", lambda: True)
    records = [
        _record(np.asarray([], dtype=float), truth=0.5, record_id="empty"),
        _record(np.sin(np.linspace(0.0, 4.0, 64)), truth=0.5, record_id="ok"),
        _record(np.sin(np.linspace(0.0, 4.0, 64)) + 1, truth=0.6, record_id="ok2"),
    ]

    summary = data_driven.train_torch_model(
        "MLCNN", records, params={"sequence_length": 16}, artefact_path=tmp_path / "cnn.pt"
    )

    assert summary["n_training_records"] == 2


@requires_torch
def test_train_torch_model_rejects_too_short_sequence_length(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(data_driven, "torch_available", lambda: True)
    records = [
        _record(np.sin(np.linspace(0.0, 4.0, 64)), truth=0.5),
        _record(np.sin(np.linspace(0.0, 4.0, 64)) + 1, truth=0.6),
    ]

    with pytest.raises(ValueError, match="sequence_length must be >= 8"):
        data_driven.train_torch_model(
            "MLCNN", records, params={"sequence_length": 4}, artefact_path=tmp_path / "cnn.pt"
        )


@requires_torch
def test_lstm_regressor_mean_pools_and_dropout_present(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(data_driven, "torch_available", lambda: True)
    import torch
    import torch.nn as nn

    model = data_driven._build_torch_model("lstm", 64)
    # Variable sequence length should both yield (batch, 1) because of mean pooling
    assert model(torch.randn(2, 1, 64)).shape == (2, 1)
    assert model(torch.randn(2, 1, 32)).shape == (2, 1)

    # Default hidden_size=32 -> 4*32 == 128 for lstm.weight_ih_l0 first dim
    assert model.lstm.weight_ih_l0.shape[0] == 128

    # Dropout module present in head
    assert any(isinstance(m, nn.Dropout) for m in model.head.modules())


@requires_torch
def test_cnn_regressor_larger_defaults_and_dropout(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(data_driven, "torch_available", lambda: True)
    import torch.nn as nn

    model = data_driven._build_torch_model("cnn_1d", 64)
    # Defaults: conv1_channels=16, conv2_channels=32
    assert model.net[0].out_channels == 16
    assert model.net[4].out_channels == 32
    # Three Dropout layers in Conv path
    assert sum(1 for m in model.net.modules() if isinstance(m, nn.Dropout)) == 3


@requires_torch
def test_train_torch_model_saves_architecture_and_round_trips(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(data_driven, "torch_available", lambda: True)
    import torch

    records = [
        _record(np.sin(np.linspace(0.0, 4.0, 128)), truth=0.5, record_id="r0"),
        _record(np.sin(np.linspace(0.0, 4.0, 128)) + 1, truth=0.6, record_id="r1"),
        _record(np.sin(np.linspace(0.0, 4.0, 128)) + 2, truth=0.7, record_id="r2"),
    ]

    summary = data_driven.train_torch_model(
        "MLLSTM",
        records,
        params={"sequence_length": 32, "hidden_size": 64, "num_layers": 2, "dropout": 0.3},
        artefact_path=tmp_path / "lstm.pt",
    )

    assert summary["n_training_records"] == 3
    bundle = torch.load(tmp_path / "lstm.pt", map_location="cpu", weights_only=True)
    assert bundle["architecture"] == {"hidden_size": 64, "num_layers": 2, "dropout": 0.3}
    assert bundle["state_dict"]["lstm.weight_ih_l0"].shape[0] == 256  # 4 * 64

    rec = _record(np.sin(np.linspace(0.0, 4.0, 128)), record_id="infer")
    out = MLLSTMEstimator(_spec("MLLSTM", {"model_path": str(tmp_path / "lstm.pt")})).fit(rec)
    assert out.valid
    assert out.diagnostics.get("architecture") == {"hidden_size": 64, "num_layers": 2, "dropout": 0.3}
    assert isinstance(out.point, float)


@requires_torch
def test_lstm_rejects_zero_dropout_with_many_layers(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(data_driven, "torch_available", lambda: True)

    model = data_driven._build_torch_model("lstm", 64, cfg={"num_layers": 3, "dropout": 0.0})
    # _build_torch_model silently bumps dropout to 0.2 when num_layers > 1 and dropout == 0.0
    assert model.lstm.dropout > 0.0
    assert model.pool_dropout.p == 0.2


def test_sklearn_estimator_rejects_non_finite_prediction(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(data_driven, "sklearn_available", lambda: True)
    data_driven._cached_pickle.cache_clear()
    model_path = tmp_path / "model.pkl"
    data_driven._write_pickle(
        model_path,
        {"model": PredictConstant(np.nan), "training_summary": {"n_training_records": 4}},
    )
    rec = _record(np.sin(np.linspace(0.0, 12.0, 128)))

    out = MLRandomForestEstimator(_spec("MLRandomForest", {"model_path": str(model_path)})).fit(rec)

    assert not out.valid
    assert out.point is None
    assert out.failure_reason == "non_finite_prediction"


@requires_torch
def test_torch_estimator_rejects_non_finite_prediction(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(data_driven, "torch_available", lambda: True)
    import torch

    records = [
        _record(np.sin(np.linspace(0.0, 4.0, 64)), truth=0.5, record_id="r0"),
        _record(np.sin(np.linspace(0.0, 4.0, 64)) + 1, truth=0.6, record_id="r1"),
    ]
    model_path = tmp_path / "cnn.pt"
    data_driven.train_torch_model(
        "MLCNN", records, params={"sequence_length": 16}, artefact_path=model_path
    )
    # Corrupt every weight to NaN so the forward pass emits a non-finite prediction.
    bundle = torch.load(model_path, map_location="cpu", weights_only=True)
    bundle["state_dict"] = {
        k: torch.full_like(v, float("nan")) for k, v in bundle["state_dict"].items()
    }
    torch.save(bundle, model_path)
    data_driven._cached_torch_model.cache_clear()

    rec = _record(np.sin(np.linspace(0.0, 12.0, 128)), record_id="infer")
    out = MLCNNEstimator(_spec("MLCNN", {"model_path": str(model_path)})).fit(rec)

    assert not out.valid
    assert out.point is None
    assert out.failure_reason == "non_finite_prediction"


@requires_torch
def test_torch_model_is_cached_across_fits(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(data_driven, "torch_available", lambda: True)
    data_driven._cached_torch_model.cache_clear()
    records = [
        _record(np.sin(np.linspace(0.0, 4.0, 64)), truth=0.5, record_id="r0"),
        _record(np.sin(np.linspace(0.0, 4.0, 64)) + 1, truth=0.6, record_id="r1"),
    ]
    model_path = tmp_path / "lstm.pt"
    data_driven.train_torch_model(
        "MLLSTM", records, params={"sequence_length": 16}, artefact_path=model_path
    )

    est = MLLSTMEstimator(_spec("MLLSTM", {"model_path": str(model_path)}))
    rec = _record(np.sin(np.linspace(0.0, 12.0, 128)), record_id="infer")
    first = est.fit(rec)
    second = est.fit(rec)

    assert first.valid and second.valid
    assert first.point == second.point  # deterministic, same cached weights
    info = data_driven._cached_torch_model.cache_info()
    assert info.hits >= 1  # second fit reused the cached model
