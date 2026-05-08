from __future__ import annotations

import hashlib
import importlib
import importlib.util
import os
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol

from lrdbench.interfaces import BaseEstimator
from lrdbench.registries import EstimatorRegistry

if TYPE_CHECKING:
    from lrdbench.schema import EstimatorSpec

"""Load external estimator plugins from Python packages.

Plugin loading is safe by default: import failures produce structured warnings rather than
crashes, so that a broken third-party estimator cannot prevent built-in estimators from running.

A plugin discovery entry point is a callable defined in a Python module:

    def _build_my_estimator(spec: EstimatorSpec) -> BaseEstimator:
        ...

    ENTRY_POINTS: dict[str, Callable[[EstimatorSpec], BaseEstimator]] = {
        "MyEstimator": _build_my_estimator,
    }

The module can be loaded by:

1. Absolute import string supplied via ``LRD_BENCH_ESTIMATOR_PLUGIN`` (colon-separated list).
2. A ``.py`` file path supplied via ``LRD_BENCH_ESTIMATOR_PLUGIN_PATH`` (colon-separated list).

Environment variables are evaluated in order, in the spirit of ``PYTHONPATH``, so that shell
or CI environments can inject plugins without touching source.

Example (import):
    export LRD_BENCH_ESTIMATOR_PLUGIN="my_pkg.lrd_estimators"

Example (file path):
    export LRD_BENCH_ESTIMATOR_PLUGIN_PATH="/home/user/custom_estimators.py"
"""


class _EstimatorBuilderFn(Protocol):
    def __call__(self, spec: EstimatorSpec) -> BaseEstimator: ...


class PluginDiscoveryResult:
    """Immutable record produced by a single plugin load attempt."""

    __slots__ = (
        "plugin_name",
        "module_name_or_path",
        "entry_point_name",
        "builder",
        "version",
        "status",
        "failure_reason",
        "source_hash",
    )

    def __init__(
        self,
        *,
        plugin_name: str,
        module_name_or_path: str,
        entry_point_name: str,
        builder: _EstimatorBuilderFn | None,
        status: str,
        version: str | None = None,
        failure_reason: str | None = None,
        source_hash: str | None = None,
    ) -> None:
        self.plugin_name = plugin_name
        self.module_name_or_path = module_name_or_path
        self.entry_point_name = entry_point_name
        self.builder = builder
        self.version = version
        self.status = status
        self.failure_reason = failure_reason
        self.source_hash = source_hash

    def __repr__(self) -> str:
        return (
            f"PluginDiscoveryResult({self.plugin_name!r}, {self.status}, "
            f"builder={'present' if self.builder is not None else 'None'})"
        )


def _file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _load_module_by_import(module_name: str) -> Any:
    """Import a module by dotted name, handling project-relative imports gracefully."""
    try:
        return importlib.import_module(module_name)
    except Exception:
        raise


def _load_module_by_path(file_path: Path) -> Any:
    """Execute a .py file as a module using importlib.util so that absolute imports work."""
    spec = importlib.util.spec_from_file_location("_lrdbench_plugin_" + file_path.stem, file_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load spec for {file_path}")
    mod = importlib.util.module_from_spec(spec)
    # Avoid polluting sys.modules on failure, but we need it during exec for absolute imports.
    sys.modules[mod.__name__] = mod
    try:
        spec.loader.exec_module(mod)
    except Exception:
        sys.modules.pop(mod.__name__, None)
        raise
    return mod


def _load_entry_points(mod: Any) -> dict[str, _EstimatorBuilderFn] | None:
    """Return the ``ENTRY_POINTS`` dict from a module, or ``None`` if absent."""
    ep: Any | None = getattr(mod, "ENTRY_POINTS", None)
    if ep is None:
        return None
    if not isinstance(ep, dict):
        raise TypeError(f"ENTRY_POINTS must be a dict, got {type(ep).__name__}")
    return ep


def _plugin_results_from_entry_points(
    ep_dict: dict[str, _EstimatorBuilderFn],
    *,
    module_name_or_path: str,
    version: str | None,
    source_hash: str | None = None,
) -> tuple[PluginDiscoveryResult, ...]:
    results: list[PluginDiscoveryResult] = []
    for name, builder in ep_dict.items():
        if not isinstance(name, str) or not name.strip():
            results.append(
                PluginDiscoveryResult(
                    plugin_name=str(name),
                    module_name_or_path=module_name_or_path,
                    entry_point_name=str(name),
                    builder=None,
                    status="invalid_entry_point",
                    failure_reason="ENTRY_POINTS key must be a non-empty string",
                    source_hash=source_hash,
                )
            )
            continue
        if not callable(builder):
            results.append(
                PluginDiscoveryResult(
                    plugin_name=name,
                    module_name_or_path=module_name_or_path,
                    entry_point_name=name,
                    builder=None,
                    status="invalid_builder",
                    failure_reason="ENTRY_POINTS value is not callable",
                    source_hash=source_hash,
                )
            )
            continue
        results.append(
            PluginDiscoveryResult(
                plugin_name=name,
                module_name_or_path=module_name_or_path,
                entry_point_name=name,
                builder=builder,
                status="ok",
                version=version,
                source_hash=source_hash,
            )
        )
    return tuple(results)


def _extract_version(mod: Any) -> str | None:
    """Best-effort version extraction from ``__version__`` or ``VERSION``."""
    v = getattr(mod, "__version__", None)
    if v is None:
        v = getattr(mod, "VERSION", None)
    return str(v) if v is not None else None


def _register_plugins_into_registry(
    registry: EstimatorRegistry,
    results: Sequence[PluginDiscoveryResult],
) -> tuple[PluginDiscoveryResult, ...]:
    updated: list[PluginDiscoveryResult] = []
    for result in results:
        if result.status != "ok" or result.builder is None:
            updated.append(result)
            continue
        # Register under the plugin name, unless already registered (built-in wins).
        if result.plugin_name in registry.list():
            updated.append(
                PluginDiscoveryResult(
                    plugin_name=result.plugin_name,
                    module_name_or_path=result.module_name_or_path,
                    entry_point_name=result.entry_point_name,
                    builder=result.builder,
                    status="skipped_name_collision",
                    version=result.version,
                    failure_reason=None,
                    source_hash=result.source_hash,
                )
            )
            continue
        registry.register(result.plugin_name, result.builder)
        updated.append(result)
    return tuple(updated)


def discover_plugins_from_env() -> tuple[PluginDiscoveryResult, ...]:
    """Read ``LRD_BENCH_ESTIMATOR_PLUGIN`` and ``LRD_BENCH_ESTIMATOR_PLUGIN_PATH``
    and return all discovered (success or failure) results.
    """
    results: list[PluginDiscoveryResult] = []

    # 1. Import-style plugins
    raw_imports = (os.environ.get("LRD_BENCH_ESTIMATOR_PLUGIN") or "").strip()
    if raw_imports:
        for module_name in raw_imports.split(":"):
            module_name = module_name.strip()
            if not module_name:
                continue
            try:
                mod = _load_module_by_import(module_name)
            except Exception as exc:
                results.append(
                    PluginDiscoveryResult(
                        plugin_name="__unknown__",
                        module_name_or_path=module_name,
                        entry_point_name="__import__",
                        builder=None,
                        status="load_failed",
                        failure_reason=f"{type(exc).__name__}: {exc}",
                    )
                )
                continue
            try:
                ep_dict = _load_entry_points(mod)
            except Exception as exc:
                results.append(
                    PluginDiscoveryResult(
                        plugin_name="__unknown__",
                        module_name_or_path=module_name,
                        entry_point_name="ENTRY_POINTS",
                        builder=None,
                        status="invalid_entry_points",
                        failure_reason=f"{type(exc).__name__}: {exc}",
                    )
                )
                continue
            if ep_dict is None:
                results.append(
                    PluginDiscoveryResult(
                        plugin_name="__unknown__",
                        module_name_or_path=module_name,
                        entry_point_name="ENTRY_POINTS",
                        builder=None,
                        status="no_entry_points",
                        failure_reason="module does not define ENTRY_POINTS",
                    )
                )
                continue
            results.extend(
                _plugin_results_from_entry_points(
                    ep_dict,
                    module_name_or_path=module_name,
                    version=_extract_version(mod),
                )
            )

    # 2. File-path plugins
    raw_paths = (os.environ.get("LRD_BENCH_ESTIMATOR_PLUGIN_PATH") or "").strip()
    if raw_paths:
        for p_str in raw_paths.split(":"):
            p_str = p_str.strip()
            if not p_str:
                continue
            p = Path(p_str)
            if not p.is_file() or p.suffix != ".py":
                results.append(
                    PluginDiscoveryResult(
                        plugin_name="__unknown__",
                        module_name_or_path=str(p.resolve()),
                        entry_point_name="__file__",
                        builder=None,
                        status="load_failed",
                        failure_reason="path does not exist or is not a .py file",
                    )
                )
                continue
            try:
                mod = _load_module_by_path(p)
            except Exception as exc:
                results.append(
                    PluginDiscoveryResult(
                        plugin_name="__unknown__",
                        module_name_or_path=str(p.resolve()),
                        entry_point_name="__file__",
                        builder=None,
                        status="load_failed",
                        failure_reason=f"{type(exc).__name__}: {exc}",
                    )
                )
                continue
            resolved_path = str(p.resolve())
            try:
                ep_dict = _load_entry_points(mod)
            except Exception as exc:
                results.append(
                    PluginDiscoveryResult(
                        plugin_name="__unknown__",
                        module_name_or_path=resolved_path,
                        entry_point_name="ENTRY_POINTS",
                        builder=None,
                        status="invalid_entry_points",
                        failure_reason=f"{type(exc).__name__}: {exc}",
                    )
                )
                continue
            if ep_dict is None:
                results.append(
                    PluginDiscoveryResult(
                        plugin_name="__unknown__",
                        module_name_or_path=resolved_path,
                        entry_point_name="ENTRY_POINTS",
                        builder=None,
                        status="no_entry_points",
                        failure_reason="module does not define ENTRY_POINTS",
                    )
                )
                continue
            file_hash = _file_sha256(p)
            results.extend(
                _plugin_results_from_entry_points(
                    ep_dict,
                    module_name_or_path=resolved_path,
                    version=_extract_version(mod),
                    source_hash=file_hash,
                )
            )

    return tuple(results)


def build_estimator_registry_with_plugins(
    *,
    base_registry: EstimatorRegistry | None = None,
    plugin_results: Sequence[PluginDiscoveryResult] | None = None,
) -> tuple[EstimatorRegistry, tuple[PluginDiscoveryResult, ...]]:
    """Build an estimator registry, optionally including third-party plugins.

    Returns the combined registry alongside the final plugin discovery results.
    Built-in estimators take precedence when names collide.
    """
    from lrdbench.defaults import build_default_estimator_registry

    registry = base_registry or build_default_estimator_registry()
    if plugin_results is None:
        plugin_results = discover_plugins_from_env()
    final_results = _register_plugins_into_registry(registry, plugin_results)
    return registry, final_results
