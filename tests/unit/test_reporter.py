from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from lrdbench.enums import BenchmarkMode
from lrdbench.reporter import SimpleHtmlCsvReporter
from lrdbench.schema import BenchmarkManifest, EstimatorSpec, MetricBundle, MetricValue, ReportSpec


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
                family="time_domain",
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
    assert estimator_rows.loc[0, "family"] == "time_domain"

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
                metadata={"ci_low": 0.1, "ci_high": 0.3},
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
        Path(bundle.summary_table_path or "").parent.parent
        / "latex"
        / "disagreement_summary.tex"
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
                metadata={"ci_low": 0.1, "ci_high": 0.3},
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
