from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from lrdbench.plugin_loader import (
    PluginDiscoveryResult,
    _extract_version,
    _load_entry_points,
    _load_module_by_path,
    build_estimator_registry_with_plugins,
    discover_plugins_from_env,
)

GOOD_PLUGIN = '''
from lrdbench.interfaces import BaseEstimator
from lrdbench.schema import EstimateResult, EstimatorSpec, SeriesRecord

__version__ = "2.0.0"

def _build_demo(spec: EstimatorSpec) -> BaseEstimator:
    class DemoEstimator(BaseEstimator):
        @property
        def spec(self) -> EstimatorSpec:
            return spec

        def fit(self, record: SeriesRecord) -> EstimateResult:
            return EstimateResult(
                record_id=record.record_id,
                estimator_name=spec.name,
                point=0.5,
                valid=True,
                estimator_version="2.0.0",
            )

    return DemoEstimator()

ENTRY_POINTS = {
    "DemoEstimator": _build_demo,
}
'''

BAD_PLUGIN = '''
ENTRY_POINTS = "not a dict"
'''

NO_ENTRY_POINTS = '''
SOME_VAR = 42
'''


class TestModuleLoading:
    def test_load_good_module_by_path(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "good_plugin.py"
            p.write_text(GOOD_PLUGIN, encoding="utf-8")
            mod = _load_module_by_path(p)
            assert mod.ENTRY_POINTS is not None
            assert _extract_version(mod) == "2.0.0"

    def test_load_module_without_entry_points(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "no_ep.py"
            p.write_text(NO_ENTRY_POINTS, encoding="utf-8")
            mod = _load_module_by_path(p)
            assert _load_entry_points(mod) is None

    def test_load_module_bad_entry_points_value(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "bad_plugin.py"
            p.write_text(BAD_PLUGIN, encoding="utf-8")
            mod = _load_module_by_path(p)
            with pytest.raises(TypeError):
                _load_entry_points(mod)


class TestEnvDiscovery:
    def test_no_env_returns_empty(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("LRD_BENCH_ESTIMATOR_PLUGIN", raising=False)
        monkeypatch.delenv("LRD_BENCH_ESTIMATOR_PLUGIN_PATH", raising=False)
        results = discover_plugins_from_env()
        assert results == ()

    def test_import_plugin_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        with tempfile.TemporaryDirectory() as td:
            pkg = Path(td) / "my_lrd_plugin"
            pkg.mkdir()
            init = pkg / "__init__.py"
            init.write_text(GOOD_PLUGIN, encoding="utf-8")
            # importlib.import_module reads sys.path, not PYTHONPATH env directly
            monkeypatch.syspath_prepend(td)
            monkeypatch.setenv("LRD_BENCH_ESTIMATOR_PLUGIN", "my_lrd_plugin")
            results = discover_plugins_from_env()
            assert len(results) == 1
            assert results[0].plugin_name == "DemoEstimator"
            assert results[0].status == "ok"
            assert results[0].version == "2.0.0"

    def test_path_plugin_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "good_plugin.py"
            p.write_text(GOOD_PLUGIN, encoding="utf-8")
            monkeypatch.setenv("LRD_BENCH_ESTIMATOR_PLUGIN_PATH", str(p))
            results = discover_plugins_from_env()
            assert len(results) == 1
            assert results[0].plugin_name == "DemoEstimator"
            assert results[0].status == "ok"
            assert results[0].source_hash is not None

    def test_nonexistent_path_returns_load_failed(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("LRD_BENCH_ESTIMATOR_PLUGIN_PATH", "/does/not/exist.py")
        results = discover_plugins_from_env()
        assert len(results) == 1
        assert results[0].status == "load_failed"

    def test_broken_builder_returns_invalid_builder(self, monkeypatch: pytest.MonkeyPatch) -> None:
        bad = '''
ENTRY_POINTS = {"BadEstimator": 42}
'''
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "bad_builder.py"
            p.write_text(bad, encoding="utf-8")
            monkeypatch.setenv("LRD_BENCH_ESTIMATOR_PLUGIN_PATH", str(p))
            results = discover_plugins_from_env()
            assert len(results) == 1
            assert results[0].status == "invalid_builder"

    def test_bad_entry_points_value_is_captured(self, monkeypatch: pytest.MonkeyPatch) -> None:
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "bad_entry_points.py"
            p.write_text(BAD_PLUGIN, encoding="utf-8")
            monkeypatch.setenv("LRD_BENCH_ESTIMATOR_PLUGIN_PATH", str(p))
            results = discover_plugins_from_env()
            assert len(results) == 1
            assert results[0].status == "invalid_entry_points"
            assert "ENTRY_POINTS must be a dict" in str(results[0].failure_reason)

    def test_bad_entry_point_name_is_captured(self, monkeypatch: pytest.MonkeyPatch) -> None:
        bad = '''
def _build(spec):
    raise AssertionError("not called")

ENTRY_POINTS = {42: _build}
'''
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "bad_name.py"
            p.write_text(bad, encoding="utf-8")
            monkeypatch.setenv("LRD_BENCH_ESTIMATOR_PLUGIN_PATH", str(p))
            results = discover_plugins_from_env()
            assert len(results) == 1
            assert results[0].status == "invalid_entry_point"
            assert results[0].plugin_name == "42"


class TestRegistryIntegration:
    def test_plugins_merge_with_defaults(self, monkeypatch: pytest.MonkeyPatch) -> None:
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "good_plugin.py"
            p.write_text(GOOD_PLUGIN, encoding="utf-8")
            monkeypatch.setenv("LRD_BENCH_ESTIMATOR_PLUGIN_PATH", str(p))
            reg, results = build_estimator_registry_with_plugins()
            assert any(r.plugin_name == "DemoEstimator" and r.status == "ok" for r in results)
            # Built-in RS should still be present
            assert "RS" in reg.list()
            # Plugin DemoEstimator should be present
            assert "DemoEstimator" in reg.list()

    def test_builtin_wins_name_collision(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Plugin tries to register an estimator called "RS" (same as built-in)
        collision = '''
from lrdbench.interfaces import BaseEstimator
from lrdbench.schema import EstimateResult, EstimatorSpec, SeriesRecord

def _build_collision(spec: EstimatorSpec) -> BaseEstimator:
    class CollisionEstimator(BaseEstimator):
        @property
        def spec(self) -> EstimatorSpec:
            return spec

        def fit(self, record: SeriesRecord) -> EstimateResult:
            return EstimateResult(
                record_id=record.record_id,
                estimator_name=spec.name,
                point=0.99,
                valid=True,
            )
    return CollisionEstimator()

ENTRY_POINTS = {"RS": _build_collision}
'''
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "collision.py"
            p.write_text(collision, encoding="utf-8")
            monkeypatch.setenv("LRD_BENCH_ESTIMATOR_PLUGIN_PATH", str(p))
            reg, results = build_estimator_registry_with_plugins()
            # RS should still resolve to the built-in one (not the plugin)
            rs_result = [r for r in results if r.plugin_name == "RS"]
            assert len(rs_result) == 1
            assert rs_result[0].status == "skipped_name_collision"

    def test_empty_env_yields_only_builtins(self) -> None:
        reg, results = build_estimator_registry_with_plugins(plugin_results=())
        assert "RS" in reg.list()
        assert len(results) == 0


class TestPluginProvenanceRecord:
    def test_result_attributes(self) -> None:
        r = PluginDiscoveryResult(
            plugin_name="Foo",
            module_name_or_path="foo.bar",
            entry_point_name="Foo",
            builder=None,
            status="ok",
            version="1.0.0",
            source_hash="abc123",
        )
        assert r.plugin_name == "Foo"
        assert r.version == "1.0.0"
        assert "builder=None" in repr(r)
