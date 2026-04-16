"""Phase 5: parallel estimator fits and optional on-disk estimate cache.

Cache files are pickles of ``EstimateResult``; only load caches from trusted
directories you control (same trust model as arbitrary pickle files).
"""

from __future__ import annotations

import hashlib
import json
import pickle
from collections.abc import Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

import numpy as np

from lrdbench.interfaces import BaseEstimator
from lrdbench.registries import EstimatorRegistry
from lrdbench.schema import EstimateResult, EstimatorSpec, SeriesRecord


def collect_fit_jobs(
    records: Sequence[SeriesRecord],
    estimator_specs: Sequence[EstimatorSpec],
) -> list[tuple[int, SeriesRecord, EstimatorSpec]]:
    jobs: list[tuple[int, SeriesRecord, EstimatorSpec]] = []
    k = 0
    for rec in records:
        for espec in estimator_specs:
            jobs.append((k, rec, espec))
            k += 1
    return jobs


def estimate_cache_key(record: SeriesRecord, espec: EstimatorSpec) -> str:
    vh = hashlib.sha256(np.asarray(record.values, dtype=float).tobytes()).hexdigest()
    ev = str(espec.version or "")
    ps = json.dumps(dict(espec.parameter_schema), sort_keys=True, default=str)
    raw = f"{record.record_id}|{espec.name}|{ev}|{ps}|{vh}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


def _cache_file(cache_root: Path, record: SeriesRecord, espec: EstimatorSpec) -> Path:
    return cache_root / f"estimate_{estimate_cache_key(record, espec)}.pkl"


def _try_load_estimate_cache(
    path: Path, *, record_id: str, estimator_name: str
) -> EstimateResult | None:
    if not path.is_file():
        return None
    try:
        with path.open("rb") as f:
            obj = pickle.load(f)
    except (OSError, pickle.PickleError, EOFError):
        return None
    if not isinstance(obj, EstimateResult):
        return None
    if obj.record_id != record_id or obj.estimator_name != estimator_name:
        return None
    return obj


def _write_estimate_cache(path: Path, est: EstimateResult) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("wb") as f:
        pickle.dump(est, f, protocol=pickle.HIGHEST_PROTOCOL)
    tmp.replace(path)


def _parse_max_workers(raw: Any) -> int:
    if raw is None:
        return 1
    if isinstance(raw, bool):
        raise ValueError("execution.max_workers must be an integer >= 1")
    if isinstance(raw, int):
        mw = raw
    else:
        try:
            mw = int(raw)
        except (TypeError, ValueError) as exc:
            raise ValueError("execution.max_workers must be an integer >= 1") from exc
    if mw < 1:
        raise ValueError("execution.max_workers must be an integer >= 1")
    return mw


def _parse_cache_dir(raw: Any, *, cwd: Path) -> Path | None:
    if raw is None or raw == "":
        return None
    p = Path(str(raw))
    if not p.is_absolute():
        p = (cwd / p).resolve()
    return p


def _parse_bool(raw: Any, *, default: bool) -> bool:
    if raw is None:
        return default
    if isinstance(raw, bool):
        return raw
    raise TypeError(f"expected bool, got {type(raw).__name__}")


def _fit_one(
    job: tuple[int, SeriesRecord, EstimatorSpec],
    *,
    estimators: EstimatorRegistry,
    cache_root: Path | None,
    cache_read: bool,
    cache_write: bool,
) -> tuple[int, EstimateResult]:
    idx, record, espec = job
    cpath = _cache_file(cache_root, record, espec) if cache_root is not None else None
    if cache_read and cpath is not None:
        hit = _try_load_estimate_cache(
            cpath, record_id=record.record_id, estimator_name=espec.name
        )
        if hit is not None:
            return idx, hit
    builder = estimators.get(espec.name)
    est_obj: BaseEstimator = builder(espec)
    est = est_obj.fit(record)
    if cache_write and cpath is not None:
        _write_estimate_cache(cpath, est)
    return idx, est


def run_fit_jobs(
    jobs: Sequence[tuple[int, SeriesRecord, EstimatorSpec]],
    *,
    estimators: EstimatorRegistry,
    execution_spec: Mapping[str, Any],
    cwd: Path | None = None,
) -> list[EstimateResult]:
    """Run all (record, estimator) fits, optionally in parallel and/or with disk cache."""
    if not jobs:
        return []
    root = cwd or Path.cwd()
    ex = dict(execution_spec)
    max_workers = _parse_max_workers(ex.get("max_workers"))
    cache_root = _parse_cache_dir(ex.get("estimate_cache_dir"), cwd=root)
    cache_read = _parse_bool(ex.get("cache_read"), default=True)
    cache_write = _parse_bool(ex.get("cache_write"), default=True)

    n = len(jobs)
    workers = max(1, min(max_workers, n))

    if workers == 1:
        out: list[EstimateResult] = []
        for job in jobs:
            _, est = _fit_one(
                job,
                estimators=estimators,
                cache_root=cache_root,
                cache_read=cache_read,
                cache_write=cache_write,
            )
            out.append(est)
        return out

    slots: list[EstimateResult | None] = [None] * n
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [
            pool.submit(
                _fit_one,
                job,
                estimators=estimators,
                cache_root=cache_root,
                cache_read=cache_read,
                cache_write=cache_write,
            )
            for job in jobs
        ]
        for fut in as_completed(futures):
            idx, est = fut.result()
            slots[idx] = est
    resolved: list[EstimateResult] = []
    for i in range(n):
        slot = slots[i]
        if slot is None:
            raise RuntimeError("internal error: parallel fit did not populate all slots")
        resolved.append(slot)
    return resolved
