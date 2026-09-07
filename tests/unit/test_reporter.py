from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from lrdbench.enums import BenchmarkMode
from lrdbench.reporter import SimpleHtmlCsvReporter
from lrdbench.schema import BenchmarkManifest, EstimatorSpec, MetricBundle, MetricValue, ReportSpec


def test_degradation_figure_keeps_metric_units_and_estimators_separate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import matplotlib.pyplot as plt

    manifest = BenchmarkManifest(
        manifest_id="stress_fig",
        name="stress",
        mode=BenchmarkMode.STRESS_TEST,
        source_spec={"type": "test"},
    )
    rows = tuple(
        MetricValue(
            run_id="stress_fig",
            record_id="r",
            estimator_name=name,
            metric_name=metric,
            value=value,
            metadata={"contamination_operator": "step_change"},
        )
        for name, drift, ratio in (("A", 0.1, 10.0), ("Z", 0.3, 30.0))
        for metric, value in (("estimate_drift", drift), ("relative_degradation_ratio", ratio))
    )
    captured: dict[str, list[float]] = {}
    savefig = plt.savefig

    def capture(*args: object, **kwargs: object) -> None:
        for ax in plt.gcf().axes:
            captured[ax.get_ylabel()] = [patch.get_height() for patch in ax.patches]
        savefig(*args, **kwargs)

    monkeypatch.setattr(plt, "savefig", capture)
    SimpleHtmlCsvReporter().build(
        manifest,
        MetricBundle(per_series=rows, aggregate=()),
        (),
        report_spec=ReportSpec(
            formats=("html", "csv"),
            leaderboards=(),
            figure_set=("degradation_curve",),
            export_root=str(tmp_path),
        ),
        run_id="figure",
    )
    assert captured == {
        "Mean absolute paired drift": [0.1, 0.3],
        "Mean per-record error ratio": [10.0, 30.0],
    }


def test_uncertainty_figure_includes_all_methods_on_separate_metric_axes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import matplotlib.pyplot as plt

    manifest = BenchmarkManifest(
        manifest_id="uq_fig",
        name="uq",
        mode=BenchmarkMode.GROUND_TRUTH,
        source_spec={"type": "test"},
    )
    rows = tuple(
        MetricValue(
            run_id="uq_fig",
            record_id=None,
            estimator_name=f"method_{i:02d}",
            metric_name=metric,
            value=point,
            stratum={"level": "balanced_global"},
            metadata={
                "uncertainty_type": "aggregate_bootstrap",
                "nominal": 0.95,
                "ci_low": lo,
                "ci_high": hi,
            },
        )
        for i in range(35)
        for metric, point, lo, hi in (("mae", 0.1, 0.2, 0.3), ("coverage", 0.9, 0.8, 1.0))
    )
    captured: dict[str, tuple[list[str], list[float]]] = {}
    savefig = plt.savefig

    def capture(*args: object, **kwargs: object) -> None:
        for ax in plt.gcf().axes:
            first_segment = ax.collections[0].get_segments()[0]
            captured[ax.get_xlabel()] = (
                [t.get_text() for t in ax.get_yticklabels()],
                list(first_segment[:, 0]),
            )
        savefig(*args, **kwargs)

    monkeypatch.setattr(plt, "savefig", capture)
    SimpleHtmlCsvReporter().build(
        manifest,
        MetricBundle(per_series=(), aggregate=(), uncertainty=rows),
        (),
        report_spec=ReportSpec(
            formats=("html", "csv"),
            leaderboards=(),
            figure_set=("benchmark_uncertainty_intervals",),
            export_root=str(tmp_path),
        ),
        run_id="figure",
    )
    assert set(captured) == {"mae", "coverage"}
    assert captured["mae"][0] == captured["coverage"][0] == [f"method_{i:02d}" for i in range(35)]
    assert captured["mae"][1] == [0.2, 0.3]  # Interval must not expand to contain point 0.1.


def test_reporter_per_stratum_metrics_includes_all_aggregate_rows(tmp_path: Path) -> None:
    manifest = BenchmarkManifest(
        manifest_id="report_test",
        name="report test",
        mode=BenchmarkMode.GROUND_TRUTH,
        source_spec={"type": "generator_grid"},
    )
    metrics = MetricBundle(
        per_series=(),
        aggregate=(
            MetricValue(
                run_id="report_test",
                record_id=None,
                estimator_name="RS",
                metric_name="mae",
                value=0.1,
                stratum={"process_family": "fGn", "H": 0.5},
                metadata={"aggregation": "mean_within_stratum"},
            ),
            MetricValue(
                run_id="report_test",
                record_id=None,
                estimator_name="RS",
                metric_name="mae",
                value=0.1,
                stratum={"level": "balanced_global"},
                metadata={"aggregation": "mean_over_strata"},
            ),
        ),
    )
    report_spec = ReportSpec(
        formats=("html", "csv"),
        leaderboards=(),
        export_root=str(tmp_path / "reports"),
    )

    bundle = SimpleHtmlCsvReporter().build(
        manifest,
        metrics,
        (),
        report_spec=report_spec,
        run_id="run_1",
    )

    metrics_path = Path(bundle.summary_table_path or "").parent / "per_stratum_metrics.csv"
    rows = pd.read_csv(metrics_path)
    strata = [json.loads(raw) for raw in rows["stratum_json"]]
    assert {"process_family": "fGn", "H": 0.5} in strata
    assert {"level": "balanced_global"} in strata

    failure_map_path = Path(bundle.summary_table_path or "").parent / "failure_map.csv"
    failure_rows = pd.read_csv(failure_map_path)
    assert len(failure_rows) == 1
    assert failure_rows.loc[0, "estimator_name"] == "RS"
    assert failure_rows.loc[0, "stratum__process_family"] == "fGn"
    assert failure_rows.loc[0, "metric__mae"] == 0.1


def test_reporter_exports_estimator_disagreement_table(tmp_path: Path) -> None:
    manifest = BenchmarkManifest(
        manifest_id="report_disagreement",
        name="report disagreement",
        mode=BenchmarkMode.GROUND_TRUTH,
        source_spec={"type": "generator_grid"},
    )
    metrics = MetricBundle(
        per_series=(
            MetricValue(
                run_id="report_disagreement",
                record_id="r1",
                estimator_name="A__vs__B",
                metric_name="pairwise_estimator_disagreement",
                value=0.2,
                stratum={"process_family": "fGn", "H": 0.5},
                metadata={"estimator_a": "A", "estimator_b": "B"},
            ),
        ),
        aggregate=(
            MetricValue(
                run_id="report_disagreement",
                record_id=None,
                estimator_name="A__vs__B",
                metric_name="pairwise_estimator_disagreement",
                value=0.2,
                stratum={"level": "balanced_global"},
                metadata={"aggregation": "mean_over_strata"},
            ),
        ),
    )
    report_spec = ReportSpec(
        formats=("html", "csv"),
        leaderboards=(),
        export_root=str(tmp_path / "reports"),
    )

    bundle = SimpleHtmlCsvReporter().build(
        manifest,
        metrics,
        (),
        report_spec=report_spec,
        run_id="run_1",
    )

    disagreement_path = Path(bundle.summary_table_path or "").parent / "estimator_disagreement.csv"
    rows = pd.read_csv(disagreement_path)
    assert set(rows["scope"]) == {"per_series", "aggregate"}
    assert rows.loc[0, "metric_name"] == "pairwise_estimator_disagreement"
    assert rows.loc[0, "value"] == 0.2


def test_reporter_exports_scale_window_sensitivity_table(tmp_path: Path) -> None:
    manifest = BenchmarkManifest(
        manifest_id="report_sensitivity",
        name="report sensitivity",
        mode=BenchmarkMode.GROUND_TRUTH,
        source_spec={"type": "generator_grid"},
    )
    metrics = MetricBundle(
        per_series=(
            MetricValue(
                run_id="report_sensitivity",
                record_id="r1",
                estimator_name="DFA",
                metric_name="parameter_variant_sensitivity",
                value=0.2,
                stratum={"process_family": "fGn", "H": 0.5},
                metadata={"variant_names": ("short", "long")},
            ),
        ),
        aggregate=(
            MetricValue(
                run_id="report_sensitivity",
                record_id=None,
                estimator_name="DFA",
                metric_name="parameter_variant_sensitivity",
                value=0.2,
                stratum={"level": "balanced_global"},
                metadata={"aggregation": "mean_over_strata"},
            ),
        ),
    )
    report_spec = ReportSpec(
        formats=("html", "csv"),
        leaderboards=(),
        export_root=str(tmp_path / "reports"),
    )

    bundle = SimpleHtmlCsvReporter().build(
        manifest,
        metrics,
        (),
        report_spec=report_spec,
        run_id="run_1",
    )

    sensitivity_path = Path(bundle.summary_table_path or "").parent / "scale_window_sensitivity.csv"
    rows = pd.read_csv(sensitivity_path)
    assert set(rows["scope"]) == {"per_series", "aggregate"}
    assert rows.loc[0, "metric_name"] == "parameter_variant_sensitivity"
    assert rows.loc[0, "value"] == 0.2


def test_reporter_exports_benchmark_uncertainty_table(tmp_path: Path) -> None:
    manifest = BenchmarkManifest(
        manifest_id="report_uq",
        name="report uq",
        mode=BenchmarkMode.GROUND_TRUTH,
        source_spec={"type": "generator_grid"},
    )
    metrics = MetricBundle(
        per_series=(),
        aggregate=(),
        uncertainty=(
            MetricValue(
                run_id="report_uq",
                record_id=None,
                estimator_name="RS",
                metric_name="mae",
                value=0.2,
                stratum={"level": "balanced_global"},
                metadata={
                    "uncertainty_type": "aggregate_bootstrap",
                    "aggregation": "bootstrap_over_strata",
                    "nominal": 0.95,
                    "ci_low": 0.1,
                    "ci_high": 0.3,
                },
            ),
        ),
    )
    report_spec = ReportSpec(
        formats=("html", "csv"),
        leaderboards=(),
        export_root=str(tmp_path / "reports"),
    )

    bundle = SimpleHtmlCsvReporter().build(
        manifest,
        metrics,
        (),
        report_spec=report_spec,
        run_id="run_1",
    )

    uncertainty_path = Path(bundle.summary_table_path or "").parent / "benchmark_uncertainty.csv"
    rows = pd.read_csv(uncertainty_path)
    assert rows.loc[0, "uncertainty_type"] == "aggregate_bootstrap"
    assert rows.loc[0, "ci_low"] == 0.1
    assert rows.loc[0, "ci_high"] == 0.3


def test_reporter_exports_audit_tables(tmp_path: Path) -> None:
    manifest = BenchmarkManifest(
        manifest_id="report_audit",
        name="report audit",
        mode=BenchmarkMode.GROUND_TRUTH,
        source_spec={"type": "generator_grid"},
        estimator_specs=(
            EstimatorSpec(
                name="RS",
                family="temporal",
                target_estimand="hurst_scaling_proxy",
                assumptions=("stationary",),
                supports_ci=True,
                supports_diagnostics=True,
                parameter_schema={"n_bootstrap": 8},
            ),
        ),
        seed_spec={"global_seed": 123},
    )
    metrics = MetricBundle(
        per_series=(
            MetricValue(
                run_id="report_audit",
                record_id="r1",
                estimator_name="RS",
                metric_name="validity_rate",
                value=0.0,
                stratum={"process_family": "fGn"},
                metadata={},
            ),
            MetricValue(
                run_id="report_audit",
                record_id="r1",
                estimator_name="RS",
                metric_name="ci_width",
                value=None,
                stratum={"process_family": "fGn"},
                metadata={"missing_ci": True},
            ),
        ),
        aggregate=(),
    )
    report_spec = ReportSpec(
        formats=("html", "csv"),
        leaderboards=(),
        export_root=str(tmp_path / "reports"),
    )

    bundle = SimpleHtmlCsvReporter().build(
        manifest,
        metrics,
        (),
        report_spec=report_spec,
        run_id="run_1",
    )
    tables = Path(bundle.summary_table_path or "").parent
    run_dir = tables.parent

    estimator_rows = pd.read_csv(tables / "estimator_metadata.csv")
    assert estimator_rows.loc[0, "estimator_name"] == "RS"
    assert estimator_rows.loc[0, "family"] == "temporal"

    failure_rows = pd.read_csv(tables / "failures.csv")
    assert failure_rows.loc[0, "n_invalid_estimates"] == 1
    assert failure_rows.loc[0, "n_missing_uncertainty"] == 1

    env = json.loads((run_dir / "manifest" / "environment.json").read_text(encoding="utf-8"))
    assert env["seed_policy"] == {"global_seed": 123}
    assert "python_version" in env

    artefact_rows = pd.read_csv(run_dir / "artefacts" / "artefact_index.csv")
    assert "environment_snapshot" in set(artefact_rows["artefact_type"])
    assert "artefact_index" in set(artefact_rows["artefact_type"])

    html_text = (run_dir / "html" / "report.html").read_text(encoding="utf-8")
    assert "Failure Summary" in html_text
    assert "Audit Artefacts" in html_text


def test_reporter_writes_publication_latex_tables(tmp_path: Path) -> None:
    manifest = BenchmarkManifest(
        manifest_id="report_latex",
        name="report latex",
        mode=BenchmarkMode.GROUND_TRUTH,
        source_spec={"type": "generator_grid"},
    )
    metrics = MetricBundle(
        per_series=(
            MetricValue(
                run_id="report_latex",
                record_id="r1",
                estimator_name="A__vs__B",
                metric_name="pairwise_estimator_disagreement",
                value=0.2,
                stratum={"process_family": "fGn"},
                metadata={},
            ),
        ),
        aggregate=(
            MetricValue(
                run_id="report_latex",
                record_id=None,
                estimator_name="A__vs__B",
                metric_name="pairwise_estimator_disagreement",
                value=0.2,
                stratum={"level": "balanced_global"},
                metadata={"aggregation": "mean_over_strata"},
            ),
            MetricValue(
                run_id="report_latex",
                record_id=None,
                estimator_name="DFA",
                metric_name="parameter_variant_sensitivity",
                value=0.1,
                stratum={"level": "balanced_global"},
                metadata={"aggregation": "mean_over_strata"},
            ),
        ),
        uncertainty=(
            MetricValue(
                run_id="report_latex",
                record_id=None,
                estimator_name="RS",
                metric_name="mae",
                value=0.2,
                stratum={"level": "balanced_global"},
                metadata={
                    "uncertainty_type": "aggregate_bootstrap",
                    "nominal": 0.95,
                    "ci_low": 0.1,
                    "ci_high": 0.3,
                },
            ),
        ),
    )
    report_spec = ReportSpec(
        formats=("html", "csv", "latex"),
        leaderboards=(),
        export_root=str(tmp_path / "reports"),
    )

    bundle = SimpleHtmlCsvReporter().build(
        manifest,
        metrics,
        (),
        report_spec=report_spec,
        run_id="run_1",
    )

    expected = {
        "metrics_summary.tex",
        "disagreement_summary.tex",
        "sensitivity_summary.tex",
        "benchmark_uncertainty.tex",
        "failure_summary.tex",
    }
    assert expected.issubset({Path(p).name for p in bundle.latex_table_paths})
    disagreement = (
        Path(bundle.summary_table_path or "").parent.parent / "latex" / "disagreement_summary.tex"
    )
    assert "pairwise\\_estimator\\_disagreement" in disagreement.read_text(encoding="utf-8")


def test_reporter_writes_opt_in_publication_figures(tmp_path: Path) -> None:
    manifest = BenchmarkManifest(
        manifest_id="report_figures",
        name="report figures",
        mode=BenchmarkMode.GROUND_TRUTH,
        source_spec={"type": "generator_grid"},
    )
    metrics = MetricBundle(
        per_series=(),
        aggregate=(
            MetricValue(
                run_id="report_figures",
                record_id=None,
                estimator_name="A__vs__B",
                metric_name="pairwise_estimator_disagreement",
                value=0.2,
                stratum={"level": "balanced_global"},
                metadata={"aggregation": "mean_over_strata"},
            ),
            MetricValue(
                run_id="report_figures",
                record_id=None,
                estimator_name="DFA",
                metric_name="parameter_variant_sensitivity",
                value=0.1,
                stratum={"level": "balanced_global"},
                metadata={"aggregation": "mean_over_strata"},
            ),
            MetricValue(
                run_id="report_figures",
                record_id=None,
                estimator_name="RS",
                metric_name="false_positive_lrd_rate",
                value=0.25,
                stratum={"level": "balanced_global"},
                metadata={"aggregation": "mean_over_strata"},
            ),
        ),
        uncertainty=(
            MetricValue(
                run_id="report_figures",
                record_id=None,
                estimator_name="RS",
                metric_name="mae",
                value=0.2,
                stratum={"level": "balanced_global"},
                metadata={
                    "uncertainty_type": "aggregate_bootstrap",
                    "nominal": 0.95,
                    "ci_low": 0.1,
                    "ci_high": 0.3,
                },
            ),
        ),
    )
    report_spec = ReportSpec(
        formats=("html", "csv"),
        leaderboards=(),
        figure_set=(
            "disagreement_heatmap",
            "sensitivity_heatmap",
            "benchmark_uncertainty_intervals",
            "false_positive_lrd",
        ),
        export_root=str(tmp_path / "reports"),
    )

    bundle = SimpleHtmlCsvReporter().build(
        manifest,
        metrics,
        (),
        report_spec=report_spec,
        run_id="run_1",
    )

    figure_names = {Path(p).name for p in bundle.figure_paths}
    assert {
        "disagreement_heatmap.png",
        "sensitivity_heatmap.png",
        "benchmark_uncertainty_intervals.png",
        "false_positive_lrd.png",
    }.issubset(figure_names)
    assert all(Path(p).is_file() for p in bundle.figure_paths)
