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
    train_sklearn_model,
)
from lrdbench.manifest import manifest_from_mapping
from lrdbench.ml_training import prepare_data_driven_estimators, requested_data_driven_estimators
from lrdbench.runner import BenchmarkRunner
from lrdbench.schema import BenchmarkManifest, EstimatorSpec, SeriesRecord, TruthSpec


class PredictConstant:
    def __init__(self, value: float) -> None:
        self.value = value
        self.fit_x_shape: tuple[int, ...] | None = None

    def fit(self, x: np.ndarray, y: np.ndarray) -> "PredictConstant":
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
