from __future__ import annotations

import pickle
import time
from collections.abc import Mapping, Sequence
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np

from lrdbench.interfaces import BaseEstimator
from lrdbench.schema import EstimateResult, EstimatorSpec, SeriesRecord

DATA_DRIVEN_ESTIMATORS = frozenset({"MLRandomForest", "MLSVR", "MLCNN", "MLLSTM"})


def is_data_driven_estimator(name: str) -> bool:
    return name.split("::", 1)[0] in DATA_DRIVEN_ESTIMATORS


def _base_name(spec: EstimatorSpec) -> str:
    params = dict(spec.parameter_schema)
    return str(params.get("_base_estimator_name", spec.name)).split("::", 1)[0]


def _as_clean_1d(values: np.ndarray) -> np.ndarray:
    x = np.asarray(values, dtype=float).reshape(-1)
    if x.size == 0:
        return x
    finite = np.isfinite(x)
    if np.all(finite):
        return x
    if not np.any(finite):
        return np.asarray([], dtype=float)
    med = float(np.median(x[finite]))
    return np.where(finite, x, med)


def standardize_series(values: np.ndarray) -> np.ndarray:
    x = _as_clean_1d(values)
    if x.size == 0:
        return x
    x = x - float(np.mean(x))
    scale = float(np.std(x))
    if scale < 1e-12:
        return np.zeros_like(x, dtype=float)
    return x / scale


def fixed_length_sequence(values: np.ndarray, *, length: int) -> np.ndarray:
    x = standardize_series(values)
    if x.size == 0:
        return x
    target = int(length)
    if target < 8:
        raise ValueError("sequence_length must be >= 8")
    if x.size == target:
        return x.astype(np.float32)
    src = np.linspace(0.0, 1.0, num=x.size)
    dst = np.linspace(0.0, 1.0, num=target)
    return np.asarray(np.interp(dst, src, x), dtype=np.float32)


def feature_vector(values: np.ndarray, *, max_lag: int = 16) -> np.ndarray:
    x = standardize_series(values)
    n = x.size
    if n < 16:
        return np.asarray([], dtype=np.float32)

    dx = np.diff(x)
    abs_x = np.abs(x)
    qs = np.quantile(x, [0.01, 0.05, 0.25, 0.5, 0.75, 0.95, 0.99])
    base = [
        float(n),
        float(np.mean(x)),
        float(np.std(x)),
        float(np.mean(abs_x)),
        float(np.std(abs_x)),
        float(np.mean(dx)) if dx.size else 0.0,
        float(np.std(dx)) if dx.size else 0.0,
        float(np.mean(np.abs(dx))) if dx.size else 0.0,
    ]
    feats: list[float] = [*base, *(float(q) for q in qs)]

    denom = float(np.dot(x, x))
    for lag in range(1, int(max_lag) + 1):
        if lag >= n or denom < 1e-12:
            feats.append(0.0)
        else:
            feats.append(float(np.dot(x[:-lag], x[lag:]) / denom))

    for block in (8, 16, 32, 64, 128):
        if n < block * 2:
            feats.extend([0.0, 0.0])
            continue
        trimmed = x[: n - (n % block)]
        blocks = trimmed.reshape(-1, block)
        means = np.mean(blocks, axis=1)
        variances = np.var(blocks, axis=1)
        feats.extend([float(np.var(means)), float(np.mean(variances))])

    spec = np.abs(np.fft.rfft(x)) ** 2
    n_spec = spec.size
    if n_spec > 4 and float(np.sum(spec)) > 1e-12:
        total = float(np.sum(spec))
        end0 = max(2, n_spec // 32)
        end1 = max(end0 + 1, n_spec // 16)
        end2 = max(end1 + 1, n_spec // 8)
        end3 = max(end2 + 1, n_spec // 4)
        bands = (
            spec[1:end0],
            spec[end0:end1],
            spec[end1:end2],
            spec[end2:end3],
        )
        feats.extend(float(np.sum(b) / total) if b.size else 0.0 for b in bands)
    else:
        feats.extend([0.0, 0.0, 0.0, 0.0])

    arr = np.asarray(feats, dtype=np.float32)
    return np.nan_to_num(arr, nan=0.0, posinf=0.0, neginf=0.0)


def sklearn_available() -> bool:
    try:
        import sklearn  # noqa: F401
    except ImportError:
        return False
    return True


def torch_available() -> bool:
    try:
        import torch  # noqa: F401
    except ImportError:
        return False
    return True


def _load_pickle(path: str | Path) -> Any:
    with Path(path).open("rb") as f:
        return pickle.load(f)


@lru_cache(maxsize=32)
def _cached_pickle(path: str) -> Any:
    return _load_pickle(path)


def _write_pickle(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("wb") as f:
        pickle.dump(obj, f, protocol=pickle.HIGHEST_PROTOCOL)
    tmp.replace(path)


def _dependency_failure(
    record: SeriesRecord,
    spec: EstimatorSpec,
    *,
    version: str,
    package: str,
    extra: str,
    t0: float,
) -> EstimateResult:
    return EstimateResult(
        record_id=record.record_id,
        estimator_name=spec.name,
        point=None,
        runtime_seconds=time.perf_counter() - t0,
        valid=False,
        failure_reason=f"missing_optional_dependency:{package}:install lrdbench[{extra}]",
        estimator_version=version,
    )


class _SklearnEstimator(BaseEstimator):
    VERSION = "0.1.0"
    MODEL_KIND = ""

    def __init__(self, spec: EstimatorSpec) -> None:
        self._spec = spec

    @property
    def spec(self) -> EstimatorSpec:
        return self._spec

    def fit(self, record: SeriesRecord) -> EstimateResult:
        t0 = time.perf_counter()
        if not sklearn_available():
            return _dependency_failure(
                record, self._spec, version=self.VERSION, package="scikit-learn", extra="ml", t0=t0
            )
        params = dict(self._spec.parameter_schema)
        model_path = params.get("_trained_model_path") or params.get("model_path")
        if not model_path:
            return EstimateResult(
                record_id=record.record_id,
                estimator_name=self._spec.name,
                point=None,
                runtime_seconds=time.perf_counter() - t0,
                valid=False,
                failure_reason="missing_trained_model_path",
                estimator_version=self.VERSION,
            )
        try:
            x = feature_vector(record.values, max_lag=int(params.get("max_lag", 16)))
            if x.size == 0:
                return EstimateResult(
                    record_id=record.record_id,
                    estimator_name=self._spec.name,
                    point=None,
                    runtime_seconds=time.perf_counter() - t0,
                    valid=False,
                    failure_reason="insufficient_signal_for_data_driven_features",
                    estimator_version=self.VERSION,
                )
            bundle = _cached_pickle(str(model_path))
            trained_max_lag = bundle.get("max_lag")
            requested_max_lag = int(params.get("max_lag", 16))
            if trained_max_lag is not None and int(trained_max_lag) != requested_max_lag:
                return EstimateResult(
                    record_id=record.record_id,
                    estimator_name=self._spec.name,
                    point=None,
                    runtime_seconds=time.perf_counter() - t0,
                    valid=False,
                    failure_reason=f"max_lag_mismatch:trained={trained_max_lag}:requested={requested_max_lag}",
                    estimator_version=self.VERSION,
                )
            model = bundle["model"]
            training_summary = dict(bundle.get("training_summary", {}))
            target_min = float(training_summary.get("target_min", 0.0))
            target_max = float(training_summary.get("target_max", 1.0))
            point = float(np.asarray(model.predict(x.reshape(1, -1))).reshape(-1)[0])
            point = float(np.clip(point, target_min, target_max))
            return EstimateResult(
                record_id=record.record_id,
                estimator_name=self._spec.name,
                point=point,
                runtime_seconds=time.perf_counter() - t0,
                valid=True,
                diagnostics={
                    "model_kind": self.MODEL_KIND,
                    "model_path": str(model_path),
                    "feature_version": "0.1.0",
                    "training_summary": training_summary,
                },
                estimator_version=self.VERSION,
            )
        except Exception as exc:  # noqa: BLE001
            return EstimateResult(
                record_id=record.record_id,
                estimator_name=self._spec.name,
                point=None,
                runtime_seconds=time.perf_counter() - t0,
                valid=False,
                failure_reason=f"exception:{type(exc).__name__}:{exc}",
                estimator_version=self.VERSION,
            )


class MLRandomForestEstimator(_SklearnEstimator):
    MODEL_KIND = "random_forest_regressor"


class MLSVREstimator(_SklearnEstimator):
    MODEL_KIND = "support_vector_regressor"


class _TorchSequenceEstimator(BaseEstimator):
    VERSION = "0.1.0"
    MODEL_KIND = ""

    def __init__(self, spec: EstimatorSpec) -> None:
        self._spec = spec

    @property
    def spec(self) -> EstimatorSpec:
        return self._spec

    def fit(self, record: SeriesRecord) -> EstimateResult:
        t0 = time.perf_counter()
        if not torch_available():
            return _dependency_failure(
                record, self._spec, version=self.VERSION, package="torch", extra="nn", t0=t0
            )
        import torch

        params = dict(self._spec.parameter_schema)
        model_path = params.get("_trained_model_path") or params.get("model_path")
        if not model_path:
            return EstimateResult(
                record_id=record.record_id,
                estimator_name=self._spec.name,
                point=None,
                runtime_seconds=time.perf_counter() - t0,
                valid=False,
                failure_reason="missing_trained_model_path",
                estimator_version=self.VERSION,
            )
        try:
            bundle = torch.load(str(model_path), map_location="cpu", weights_only=True)
            seq_len = int(bundle["sequence_length"])
            arch_cfg = dict(bundle.get("architecture", {}))
            model = _build_torch_model(str(bundle["model_kind"]), seq_len, cfg=arch_cfg)
            model.load_state_dict(bundle["state_dict"])
            model.eval()
            x = fixed_length_sequence(record.values, length=seq_len)
            if x.size == 0:
                return EstimateResult(
                    record_id=record.record_id,
                    estimator_name=self._spec.name,
                    point=None,
                    runtime_seconds=time.perf_counter() - t0,
                    valid=False,
                    failure_reason="insufficient_signal_for_data_driven_sequence",
                    estimator_version=self.VERSION,
                )
            training_summary = dict(bundle.get("training_summary", {}))
            target_min = float(training_summary.get("target_min", 0.0))
            target_max = float(training_summary.get("target_max", 1.0))
            with torch.no_grad():
                xt = torch.as_tensor(x.reshape(1, 1, -1), dtype=torch.float32)
                pred = model(xt).reshape(-1)[0].item()
            point = float(np.clip(pred, target_min, target_max))
            return EstimateResult(
                record_id=record.record_id,
                estimator_name=self._spec.name,
                point=point,
                runtime_seconds=time.perf_counter() - t0,
                valid=True,
                diagnostics={
                    "model_kind": self.MODEL_KIND,
                    "model_path": str(model_path),
                    "sequence_length": seq_len,
                    "architecture": arch_cfg,
                    "training_summary": training_summary,
                },
                estimator_version=self.VERSION,
            )
        except Exception as exc:  # noqa: BLE001
            return EstimateResult(
                record_id=record.record_id,
                estimator_name=self._spec.name,
                point=None,
                runtime_seconds=time.perf_counter() - t0,
                valid=False,
                failure_reason=f"exception:{type(exc).__name__}:{exc}",
                estimator_version=self.VERSION,
            )


class MLCNNEstimator(_TorchSequenceEstimator):
    MODEL_KIND = "cnn_1d"


class MLLSTMEstimator(_TorchSequenceEstimator):
    MODEL_KIND = "lstm"


def _build_torch_model(
    kind: str, sequence_length: int, *, cfg: Mapping[str, Any] | None = None
) -> Any:
    from torch import nn

    _cfg = dict(cfg) if cfg else {}

    if kind == "cnn_1d":
        c1 = int(_cfg.get("conv1_channels", 16))
        c2 = int(_cfg.get("conv2_channels", 32))
        dropout = float(_cfg.get("dropout", 0.2))

        class CNNRegressor(nn.Module):
            def __init__(self) -> None:
                super().__init__()
                self.net = nn.Sequential(
                    nn.Conv1d(1, c1, kernel_size=7, padding=3),
                    nn.ReLU(),
                    nn.Dropout(dropout),
                    nn.AvgPool1d(2),
                    nn.Conv1d(c1, c2, kernel_size=5, padding=2),
                    nn.ReLU(),
                    nn.Dropout(dropout),
                    nn.AdaptiveAvgPool1d(8),
                    nn.Flatten(),
                    nn.Linear(c2 * 8, 32),
                    nn.ReLU(),
                    nn.Dropout(dropout),
                    nn.Linear(32, 1),
                )

            def forward(self, x: Any) -> Any:
                return self.net(x)

        return CNNRegressor()

    if kind == "lstm":
        hidden_size = int(_cfg.get("hidden_size", 32))
        num_layers = int(_cfg.get("num_layers", 1))
        dropout = float(_cfg.get("dropout", 0.2))
        if num_layers > 1 and dropout == 0.0:
            dropout = 0.2

        class LSTMRegressor(nn.Module):
            def __init__(self) -> None:
                super().__init__()
                self.lstm = nn.LSTM(
                    input_size=1,
                    hidden_size=hidden_size,
                    num_layers=num_layers,
                    batch_first=True,
                    dropout=dropout if num_layers > 1 else 0.0,
                )
                self.pool_dropout = nn.Dropout(dropout)
                self.head = nn.Sequential(
                    nn.Linear(hidden_size, hidden_size),
                    nn.ReLU(),
                    nn.Dropout(dropout),
                    nn.Linear(hidden_size, 1),
                )

            def forward(self, x: Any) -> Any:
                xt = x.transpose(1, 2)
                out, _ = self.lstm(xt)
                pooled = self.pool_dropout(out.mean(dim=1))
                return self.head(pooled)

        return LSTMRegressor()

    raise ValueError(f"unknown torch model kind: {kind!r} for length {sequence_length}")


def train_sklearn_model(
    estimator_name: str,
    records: Sequence[SeriesRecord],
    *,
    params: Mapping[str, Any],
    artefact_path: Path,
) -> Mapping[str, Any]:
    if not sklearn_available():
        raise ImportError("scikit-learn is required for RF/SVR data-driven baselines")
    from sklearn.ensemble import RandomForestRegressor
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler
    from sklearn.svm import SVR

    max_lag = int(params.get("max_lag", 16))
    rows: list[np.ndarray] = []
    y: list[float] = []
    for rec in records:
        if rec.truth is None or rec.truth.target_value is None:
            continue
        feats = feature_vector(rec.values, max_lag=max_lag)
        if feats.size == 0:
            continue
        rows.append(feats)
        y.append(float(rec.truth.target_value))
    if len(rows) < 2:
        raise ValueError("data-driven training requires at least two valid training records")
    xmat = np.vstack(rows)
    yarr = np.asarray(y, dtype=float)
    rng = np.random.default_rng(int(params.get("random_state", 0)))
    order = rng.permutation(yarr.size)
    validation_fraction = float(params.get("_validation_fraction", 0.0))
    n_val = int(round(yarr.size * validation_fraction))
    n_val = min(max(0, n_val), yarr.size - 1)
    val_idx = order[:n_val]
    train_idx = order[n_val:]
    if estimator_name == "MLRandomForest":
        model = RandomForestRegressor(
            n_estimators=int(params.get("n_estimators", 100)),
            max_depth=int(params["max_depth"]) if params.get("max_depth") is not None else None,
            min_samples_leaf=int(params.get("min_samples_leaf", 1)),
            random_state=int(params.get("random_state", 0)),
            n_jobs=int(params.get("n_jobs", 1)),
        )
    elif estimator_name == "MLSVR":
        model = make_pipeline(
            StandardScaler(),
            SVR(
                C=float(params.get("C", 10.0)),
                epsilon=float(params.get("epsilon", 0.03)),
                kernel=str(params.get("kernel", "rbf")),
                gamma=params.get("gamma", "scale"),
            ),
        )
    else:
        raise ValueError(f"unsupported sklearn data-driven estimator: {estimator_name!r}")
    model.fit(xmat[train_idx], yarr[train_idx])
    pred = np.asarray(model.predict(xmat[train_idx]), dtype=float)
    summary = {
        "n_training_records": int(len(yarr)),
        "n_fit_records": int(train_idx.size),
        "n_validation_records": int(val_idx.size),
        "train_mae": float(np.mean(np.abs(pred - yarr[train_idx]))),
        "target_min": float(np.min(yarr)),
        "target_max": float(np.max(yarr)),
    }
    if val_idx.size:
        val_pred = np.asarray(model.predict(xmat[val_idx]), dtype=float)
        summary["validation_mae"] = float(np.mean(np.abs(val_pred - yarr[val_idx])))
    _write_pickle(
        artefact_path,
        {
            "model": model,
            "training_summary": summary,
            "max_lag": int(max_lag),
        },
    )
    return summary


def train_torch_model(
    estimator_name: str,
    records: Sequence[SeriesRecord],
    *,
    params: Mapping[str, Any],
    artefact_path: Path,
) -> Mapping[str, Any]:
    if not torch_available():
        raise ImportError("torch is required for CNN/LSTM data-driven baselines")
    import torch
    from torch import nn
    from torch.utils.data import DataLoader, TensorDataset

    sequence_length = int(params.get("sequence_length", 256))
    if sequence_length < 8:
        raise ValueError(f"sequence_length must be >= 8, got {sequence_length}")
    torch.manual_seed(int(params.get("random_state", 0)))
    xs: list[np.ndarray] = []
    ys: list[float] = []
    for rec in records:
        if rec.truth is None or rec.truth.target_value is None:
            continue
        try:
            seq = fixed_length_sequence(rec.values, length=sequence_length)
        except Exception:
            continue
        if seq.size == 0:
            continue
        xs.append(seq)
        ys.append(float(rec.truth.target_value))
    if len(xs) < 2:
        raise ValueError("data-driven training requires at least two valid training records")

    x = torch.as_tensor(np.asarray(xs, dtype=np.float32)[:, None, :], dtype=torch.float32)
    y = torch.as_tensor(np.asarray(ys, dtype=np.float32)[:, None], dtype=torch.float32)
    rng = np.random.default_rng(int(params.get("random_state", 0)))
    order = rng.permutation(len(xs))
    validation_fraction = float(params.get("_validation_fraction", 0.0))
    n_val = int(round(len(xs) * validation_fraction))
    n_val = min(max(0, n_val), len(xs) - 1)
    val_idx = order[:n_val]
    train_idx = order[n_val:]
    kind = "cnn_1d" if estimator_name == "MLCNN" else "lstm"
    arch_cfg = {
        k: params[k]
        for k in ("conv1_channels", "conv2_channels", "hidden_size", "num_layers", "dropout")
        if k in params
    }
    model = _build_torch_model(kind, sequence_length, cfg=arch_cfg)
    opt = torch.optim.Adam(
        model.parameters(),
        lr=float(params.get("learning_rate", 0.001)),
        weight_decay=float(params.get("weight_decay", 1e-4)),
    )
    loss_fn = nn.MSELoss()
    loader = DataLoader(
        TensorDataset(x[train_idx], y[train_idx]),
        batch_size=int(params.get("batch_size", 16)),
        shuffle=True,
    )
    epochs = int(params.get("epochs", 8))
    model.train()
    for _ in range(max(1, epochs)):
        for xb, yb in loader:
            opt.zero_grad()
            loss = loss_fn(model(xb), yb)
            loss.backward()
            opt.step()
    model.eval()
    with torch.no_grad():
        pred = model(x[train_idx]).detach().numpy().reshape(-1)
    y_np = y.numpy().reshape(-1)
    summary = {
        "n_training_records": int(y_np.size),
        "n_fit_records": int(train_idx.size),
        "n_validation_records": int(val_idx.size),
        "train_mae": float(np.mean(np.abs(pred - y_np[train_idx]))),
        "target_min": float(np.min(y_np)),
        "target_max": float(np.max(y_np)),
        "epochs": int(max(1, epochs)),
    }
    if val_idx.size:
        with torch.no_grad():
            val_pred = model(x[val_idx]).detach().numpy().reshape(-1)
        summary["validation_mae"] = float(np.mean(np.abs(val_pred - y_np[val_idx])))
    artefact_path.parent.mkdir(parents=True, exist_ok=True)
    torch.save(
        {
            "model_kind": kind,
            "sequence_length": sequence_length,
            "architecture": arch_cfg,
            "state_dict": model.state_dict(),
            "training_summary": summary,
        },
        str(artefact_path),
    )
    return summary
