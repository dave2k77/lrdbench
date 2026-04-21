from __future__ import annotations

import html
import json
import platform
import sys
from collections.abc import Sequence
from datetime import UTC, datetime
from importlib import metadata
from pathlib import Path
from typing import Any

import pandas as pd

from lrdbench.enums import BenchmarkMode
from lrdbench.interfaces import BaseReporter
from lrdbench.schema import (
    ArtefactRecord,
    BenchmarkManifest,
    MetricBundle,
    ReportBundle,
    ReportSpec,
)


def _created_at() -> str:
    return datetime.now(UTC).isoformat()


def _package_version(name: str) -> str | None:
    try:
        return metadata.version(name)
    except metadata.PackageNotFoundError:
        return None

_STRESS_METRIC_NAMES = frozenset(
    {
        "estimate_drift",
        "relative_degradation_ratio",
        "validity_collapse",
        "coverage_collapse",
    }
)

_DISAGREEMENT_METRIC_NAMES = frozenset(
    {
        "cross_estimator_dispersion",
        "pairwise_estimator_disagreement",
        "family_level_disagreement",
    }
)

_SENSITIVITY_METRIC_NAMES = frozenset(
    {
        "parameter_variant_sensitivity",
        "max_variant_drift",
    }
)


def _fmt_cell(value: Any) -> str:
    if value is None:
        return "NA"
    if isinstance(value, float):
        return f"{value:.6g}"
    return str(value)


def _html_table(headers: Sequence[str], rows: Sequence[Sequence[Any]], *, empty: str) -> str:
    head = "".join(f"<th>{html.escape(h)}</th>" for h in headers)
    if rows:
        body = "".join(
            "<tr>"
            + "".join(f"<td>{html.escape(_fmt_cell(cell))}</td>" for cell in row)
            + "</tr>"
            for row in rows
        )
    else:
        body = f"<tr><td colspan={len(headers)}>{html.escape(empty)}</td></tr>"
    return (
        '<table border="1" cellpadding="4">'
        f"<thead><tr>{head}</tr></thead>"
        f"<tbody>{body}</tbody></table>"
    )


def _tex_escape(s: Any) -> str:
    return (
        str(s)
        .replace("\\", r"\textbackslash{}")
        .replace("&", r"\&")
        .replace("%", r"\%")
        .replace("#", r"\#")
        .replace("_", r"\_")
    )


def _write_latex_table(
    path: Path,
    headers: Sequence[str],
    rows: Sequence[Sequence[Any]],
) -> None:
    colspec = " ".join("l" for _ in headers)
    lines = [rf"\begin{{tabular}}{{{colspec}}}", r"\hline"]
    lines.append(" & ".join(_tex_escape(h) for h in headers) + r" \\")
    lines.append(r"\hline")
    for row in rows:
        lines.append(" & ".join(_tex_escape(_fmt_cell(cell)) for cell in row) + r" \\")
    lines.extend([r"\hline", r"\end{tabular}"])
    path.write_text("\n".join(lines), encoding="utf-8")


def _load_plotting() -> tuple[Any, Any]:
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import seaborn as sns
    except ImportError as exc:
        raise RuntimeError(
            "Figure generation requires the core plotting stack: matplotlib and seaborn."
        ) from exc
    sns.set_theme(style="whitegrid", context="paper")
    return plt, sns


def _failure_map_rows(metrics: MetricBundle) -> list[dict[str, Any]]:
    rows: dict[tuple[str, str], dict[str, Any]] = {}
    for m in metrics.aggregate:
        if m.stratum.get("level") == "balanced_global":
            continue
        stratum = dict(m.stratum)
        stratum_key = json.dumps(stratum, sort_keys=True)
        key = (m.estimator_name, stratum_key)
        row = rows.setdefault(
            key,
            {
                "estimator_name": m.estimator_name,
                "stratum_json": stratum_key,
                **{f"stratum__{k}": v for k, v in sorted(stratum.items())},
            },
        )
        metric_key = f"metric__{m.metric_name}"
        nominal = m.metadata.get("nominal")
        if nominal is not None:
            metric_key = f"{metric_key}__nominal_{nominal}"
        row[metric_key] = m.value
    return list(rows.values())


def _failure_rows(metrics: MetricBundle) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], dict[str, Any]] = {}
    for m in metrics.per_series:
        if m.record_id is None:
            continue
        stratum_key = json.dumps(dict(m.stratum), sort_keys=True)
        key = (m.estimator_name, stratum_key)
        row = grouped.setdefault(
            key,
            {
                "estimator_name": m.estimator_name,
                "stratum_json": stratum_key,
                "n_metric_rows": 0,
                "n_missing_values": 0,
                "n_missing_uncertainty": 0,
                "n_validity_observations": 0,
                "n_invalid_estimates": 0,
                **{f"stratum__{k}": v for k, v in sorted(dict(m.stratum).items())},
            },
        )
        row["n_metric_rows"] += 1
        if m.value is None:
            row["n_missing_values"] += 1
        if m.metadata.get("missing_ci"):
            row["n_missing_uncertainty"] += 1
        if m.metric_name == "validity_rate":
            row["n_validity_observations"] += 1
            if m.value == 0.0:
                row["n_invalid_estimates"] += 1

    for row in grouped.values():
        n_valid = int(row["n_validity_observations"])
        row["invalid_rate"] = (
            float(row["n_invalid_estimates"]) / n_valid if n_valid > 0 else None
        )
        row["missing_value_rate"] = (
            float(row["n_missing_values"]) / int(row["n_metric_rows"])
            if int(row["n_metric_rows"]) > 0
            else None
        )
    return list(grouped.values())


def _environment_snapshot(manifest: BenchmarkManifest, run_id: str) -> dict[str, Any]:
    return {
        "run_id": run_id,
        "manifest_id": manifest.manifest_id,
        "created_at": _created_at(),
        "python_version": sys.version,
        "python_executable": sys.executable,
        "platform": platform.platform(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "package_versions": {
            "lrdbench": _package_version("lrdbench"),
            "numpy": _package_version("numpy"),
            "pandas": _package_version("pandas"),
        },
        "seed_policy": dict(manifest.seed_spec),
        "execution": dict(manifest.execution_spec),
        "uncertainty": dict(manifest.uncertainty_spec),
    }


class SimpleHtmlCsvReporter(BaseReporter):
    def build(
        self,
        manifest: BenchmarkManifest,
        metrics: MetricBundle,
        leaderboards: Sequence[Any],
        *,
        report_spec: ReportSpec,
        run_id: str,
    ) -> ReportBundle:
        export_root = Path(report_spec.export_root)
        run_dir = export_root / run_id
        tables = run_dir / "tables"
        html_dir = run_dir / "html"
        tables.mkdir(parents=True, exist_ok=True)
        html_dir.mkdir(parents=True, exist_ok=True)

        artefacts: list[ArtefactRecord] = []
        figure_paths: list[str] = []
        environment_path = run_dir / "manifest" / "environment.json"
        environment_path.parent.mkdir(parents=True, exist_ok=True)

        def _record_artifact(
            *,
            artefact_id: str,
            artefact_type: str,
            format: str,
            path: Path,
        ) -> None:
            artefacts.append(
                ArtefactRecord(
                    artefact_id=artefact_id,
                    run_id=run_id,
                    artefact_type=artefact_type,
                    format=format,
                    path=str(path.as_posix()),
                    created_at=_created_at(),
                )
            )

        run_summary_path = tables / "run_summary.csv"
        pd.DataFrame(
            [
                {
                    "run_id": run_id,
                    "manifest_id": manifest.manifest_id,
                    "benchmark_name": manifest.name,
                    "mode": manifest.mode.value,
                }
            ]
        ).to_csv(run_summary_path, index=False)
        _record_artifact(
            artefact_id=f"{run_id}_run_summary",
            artefact_type="metric_export",
            format="csv",
            path=run_summary_path,
        )

        estimator_metadata_path = tables / "estimator_metadata.csv"
        pd.DataFrame(
            [
                {
                    "estimator_name": e.name,
                    "family": e.family,
                    "target_estimand": e.target_estimand,
                    "supports_ci": e.supports_ci,
                    "supports_diagnostics": e.supports_diagnostics,
                    "assumptions_json": json.dumps(tuple(e.assumptions)),
                    "params_json": json.dumps(dict(e.parameter_schema), sort_keys=True),
                    "version": e.version,
                }
                for e in manifest.estimator_specs
            ]
        ).to_csv(estimator_metadata_path, index=False)
        _record_artifact(
            artefact_id=f"{run_id}_estimator_metadata_csv",
            artefact_type="estimator_metadata",
            format="csv",
            path=estimator_metadata_path,
        )

        env = _environment_snapshot(manifest, run_id)
        environment_path.write_text(json.dumps(env, indent=2, sort_keys=True), encoding="utf-8")
        _record_artifact(
            artefact_id=f"{run_id}_environment_json",
            artefact_type="environment_snapshot",
            format="json",
            path=environment_path,
        )

        # Leaderboard CSV
        lb_rows = [
            {
                "estimator_name": r.estimator_name,
                "rank": r.rank,
                "score": r.score,
                **{f"metric__{k}": v for k, v in r.component_values.items()},
            }
            for r in leaderboards
        ]
        lb_path = tables / "leaderboard.csv"
        if lb_rows:
            pd.DataFrame(lb_rows).to_csv(lb_path, index=False)
        else:
            lb_path.write_text("", encoding="utf-8")
        _record_artifact(
            artefact_id=f"{run_id}_leaderboard_csv",
            artefact_type="leaderboard_export",
            format="csv",
            path=lb_path,
        )

        # Aggregate metrics table: per-stratum rows plus balanced-global summaries.
        agg = list(metrics.aggregate)
        agg_path = tables / "per_stratum_metrics.csv"
        pd.DataFrame(
            [
                {
                    "estimator_name": m.estimator_name,
                    "metric_name": m.metric_name,
                    "value": m.value,
                    "stratum_json": json.dumps(dict(m.stratum), sort_keys=True),
                    "metadata_json": json.dumps(dict(m.metadata), sort_keys=True),
                }
                for m in agg
            ]
        ).to_csv(agg_path, index=False)
        _record_artifact(
            artefact_id=f"{run_id}_metrics_csv",
            artefact_type="metric_export",
            format="csv",
            path=agg_path,
        )

        failure_map_path = tables / "failure_map.csv"
        failure_rows = _failure_map_rows(metrics)
        if failure_rows:
            pd.DataFrame(failure_rows).to_csv(failure_map_path, index=False)
        else:
            failure_map_path.write_text("", encoding="utf-8")
        _record_artifact(
            artefact_id=f"{run_id}_failure_map_csv",
            artefact_type="metric_export",
            format="csv",
            path=failure_map_path,
        )

        disagreement_path = tables / "estimator_disagreement.csv"
        disagreement_rows = [
            {
                "scope": "per_series" if m.record_id is not None else "aggregate",
                "record_id": m.record_id,
                "estimator_name": m.estimator_name,
                "metric_name": m.metric_name,
                "value": m.value,
                "stratum_json": json.dumps(dict(m.stratum), sort_keys=True),
                "metadata_json": json.dumps(dict(m.metadata), sort_keys=True),
            }
            for m in (*metrics.per_series, *metrics.aggregate)
            if m.metric_name in _DISAGREEMENT_METRIC_NAMES
        ]
        if disagreement_rows:
            pd.DataFrame(disagreement_rows).to_csv(disagreement_path, index=False)
        else:
            disagreement_path.write_text("", encoding="utf-8")
        _record_artifact(
            artefact_id=f"{run_id}_estimator_disagreement_csv",
            artefact_type="metric_export",
            format="csv",
            path=disagreement_path,
        )

        sensitivity_path = tables / "scale_window_sensitivity.csv"
        sensitivity_rows = [
            {
                "scope": "per_series" if m.record_id is not None else "aggregate",
                "record_id": m.record_id,
                "estimator_name": m.estimator_name,
                "metric_name": m.metric_name,
                "value": m.value,
                "stratum_json": json.dumps(dict(m.stratum), sort_keys=True),
                "metadata_json": json.dumps(dict(m.metadata), sort_keys=True),
            }
            for m in (*metrics.per_series, *metrics.aggregate)
            if m.metric_name in _SENSITIVITY_METRIC_NAMES
        ]
        if sensitivity_rows:
            pd.DataFrame(sensitivity_rows).to_csv(sensitivity_path, index=False)
        else:
            sensitivity_path.write_text("", encoding="utf-8")
        _record_artifact(
            artefact_id=f"{run_id}_scale_window_sensitivity_csv",
            artefact_type="metric_export",
            format="csv",
            path=sensitivity_path,
        )

        unc = [m for m in agg if m.metric_name in ("coverage", "ci_width", "coverage_error")]
        unc_path = tables / "uncertainty_calibration.csv"
        pd.DataFrame(
            [
                {
                    "estimator_name": m.estimator_name,
                    "metric_name": m.metric_name,
                    "value": m.value,
                    "nominal": m.metadata.get("nominal"),
                }
                for m in unc
            ]
        ).to_csv(unc_path, index=False)
        _record_artifact(
            artefact_id=f"{run_id}_uncertainty_csv",
            artefact_type="metric_export",
            format="csv",
            path=unc_path,
        )

        benchmark_uncertainty_path = tables / "benchmark_uncertainty.csv"
        benchmark_uncertainty_rows = [
            {
                "estimator_name": m.estimator_name,
                "metric_name": m.metric_name,
                "value": m.value,
                "uncertainty_type": m.metadata.get("uncertainty_type"),
                "aggregation": m.metadata.get("aggregation"),
                "nominal": m.metadata.get("nominal"),
                "ci_low": m.metadata.get("ci_low"),
                "ci_high": m.metadata.get("ci_high"),
                "stratum_json": json.dumps(dict(m.stratum), sort_keys=True),
                "metadata_json": json.dumps(dict(m.metadata), sort_keys=True),
            }
            for m in metrics.uncertainty
        ]
        if benchmark_uncertainty_rows:
            pd.DataFrame(benchmark_uncertainty_rows).to_csv(
                benchmark_uncertainty_path, index=False
            )
        else:
            benchmark_uncertainty_path.write_text("", encoding="utf-8")
        _record_artifact(
            artefact_id=f"{run_id}_benchmark_uncertainty_csv",
            artefact_type="metric_export",
            format="csv",
            path=benchmark_uncertainty_path,
        )

        failure_summary_rows = _failure_rows(metrics)
        failures_path = tables / "failures.csv"
        if failure_summary_rows:
            pd.DataFrame(failure_summary_rows).to_csv(failures_path, index=False)
        else:
            failures_path.write_text("", encoding="utf-8")
        _record_artifact(
            artefact_id=f"{run_id}_failures_csv",
            artefact_type="failure_export",
            format="csv",
            path=failures_path,
        )

        artefact_index_path = run_dir / "artefacts" / "artefact_index.csv"
        artefact_index_path.parent.mkdir(parents=True, exist_ok=True)

        if manifest.mode is BenchmarkMode.STRESS_TEST:
            stress_rows = [
                {
                    "record_id": m.record_id,
                    "estimator_name": m.estimator_name,
                    "metric_name": m.metric_name,
                    "value": m.value,
                    "stratum_json": json.dumps(dict(m.stratum), sort_keys=True),
                    "contamination_operator": m.metadata.get("contamination_operator"),
                    "clean_record_id": m.metadata.get("clean_record_id"),
                    "nominal": m.metadata.get("nominal"),
                }
                for m in metrics.per_series
                if m.record_id is not None and m.metric_name in _STRESS_METRIC_NAMES
            ]
            stress_path = tables / "stress_metrics.csv"
            pd.DataFrame(stress_rows).to_csv(stress_path, index=False)
            _record_artifact(
                artefact_id=f"{run_id}_stress_metrics_csv",
                artefact_type="metric_export",
                format="csv",
                path=stress_path,
            )

        if (
            manifest.mode is BenchmarkMode.STRESS_TEST
            and "degradation_curve" in report_spec.figure_set
        ):
            rows = [
                {
                    "metric_name": m.metric_name,
                    "value": m.value,
                    "contamination_operator": m.metadata.get("contamination_operator"),
                }
                for m in metrics.per_series
                if m.record_id is not None
                and m.metric_name in ("relative_degradation_ratio", "estimate_drift")
                and m.value is not None
                and m.metadata.get("contamination_operator") is not None
            ]
            if rows:
                plt, _sns = _load_plotting()
                fig_dir = run_dir / "figures"
                fig_dir.mkdir(parents=True, exist_ok=True)
                dfp = pd.DataFrame(rows)
                pivot = dfp.groupby("contamination_operator", as_index=True)["value"].mean()
                fig_path = fig_dir / "degradation_curve.png"
                _fig, ax = plt.subplots(figsize=(6, 3.5))
                pivot.plot(kind="bar", ax=ax, legend=False, color="steelblue")
                ax.set_xlabel("contamination operator")
                ax.set_ylabel("mean metric value")
                ax.set_title("Stress degradation (paired series)")
                plt.tight_layout()
                plt.savefig(fig_path, dpi=120)
                plt.close()
                figure_paths.append(str(fig_path.as_posix()))
                _record_artifact(
                    artefact_id=f"{run_id}_degradation_curve",
                    artefact_type="figure",
                    format="png",
                    path=fig_path,
                )

        if "disagreement_heatmap" in report_spec.figure_set:
            rows = [
                r
                for r in disagreement_rows
                if r["scope"] == "aggregate" and r["value"] is not None
            ]
            if rows:
                plt, sns = _load_plotting()
                fig_dir = run_dir / "figures"
                fig_dir.mkdir(parents=True, exist_ok=True)
                dfp = pd.DataFrame(rows)
                pivot = dfp.pivot_table(
                    index="estimator_name",
                    columns="metric_name",
                    values="value",
                    aggfunc="mean",
                ).fillna(0.0)
                fig_path = fig_dir / "disagreement_heatmap.png"
                _fig, ax = plt.subplots(figsize=(7, max(2.5, 0.35 * len(pivot.index))))
                sns.heatmap(
                    pivot,
                    ax=ax,
                    cmap="viridis",
                    cbar_kws={"label": "mean value"},
                )
                ax.set_xticklabels(ax.get_xticklabels(), rotation=35, ha="right")
                ax.set_title("Estimator disagreement")
                plt.tight_layout()
                plt.savefig(fig_path, dpi=140)
                plt.close()
                figure_paths.append(str(fig_path.as_posix()))
                _record_artifact(
                    artefact_id=f"{run_id}_disagreement_heatmap",
                    artefact_type="figure",
                    format="png",
                    path=fig_path,
                )

        if "sensitivity_heatmap" in report_spec.figure_set:
            rows = [
                r
                for r in sensitivity_rows
                if r["scope"] == "aggregate" and r["value"] is not None
            ]
            if rows:
                plt, sns = _load_plotting()
                fig_dir = run_dir / "figures"
                fig_dir.mkdir(parents=True, exist_ok=True)
                dfp = pd.DataFrame(rows)
                pivot = dfp.pivot_table(
                    index="estimator_name",
                    columns="metric_name",
                    values="value",
                    aggfunc="mean",
                ).fillna(0.0)
                fig_path = fig_dir / "sensitivity_heatmap.png"
                _fig, ax = plt.subplots(figsize=(7, max(2.5, 0.35 * len(pivot.index))))
                sns.heatmap(
                    pivot,
                    ax=ax,
                    cmap="magma",
                    cbar_kws={"label": "mean value"},
                )
                ax.set_xticklabels(ax.get_xticklabels(), rotation=35, ha="right")
                ax.set_title("Scale/window sensitivity")
                plt.tight_layout()
                plt.savefig(fig_path, dpi=140)
                plt.close()
                figure_paths.append(str(fig_path.as_posix()))
                _record_artifact(
                    artefact_id=f"{run_id}_sensitivity_heatmap",
                    artefact_type="figure",
                    format="png",
                    path=fig_path,
                )

        if "benchmark_uncertainty_intervals" in report_spec.figure_set:
            rows = [
                r
                for r in benchmark_uncertainty_rows
                if r["value"] is not None and r["ci_low"] is not None and r["ci_high"] is not None
            ]
            if rows:
                plt, _sns = _load_plotting()
                fig_dir = run_dir / "figures"
                fig_dir.mkdir(parents=True, exist_ok=True)
                rows = rows[:30]
                labels = [f"{r['estimator_name']}:{r['metric_name']}" for r in rows]
                values = [float(r["value"]) for r in rows]
                low = [float(r["ci_low"]) for r in rows]
                high = [float(r["ci_high"]) for r in rows]
                xerr = [
                    [max(0.0, v - lo) for v, lo in zip(values, low, strict=True)],
                    [max(0.0, hi - v) for v, hi in zip(values, high, strict=True)],
                ]
                fig_path = fig_dir / "benchmark_uncertainty_intervals.png"
                _fig, ax = plt.subplots(figsize=(8, max(3.0, 0.32 * len(rows))))
                y = list(range(len(rows)))
                ax.errorbar(values, y, xerr=xerr, fmt="o", color="black", ecolor="steelblue")
                ax.set_yticks(y)
                ax.set_yticklabels(labels)
                ax.invert_yaxis()
                ax.set_xlabel("Metric value")
                ax.set_title("Benchmark uncertainty intervals")
                plt.tight_layout()
                plt.savefig(fig_path, dpi=140)
                plt.close()
                figure_paths.append(str(fig_path.as_posix()))
                _record_artifact(
                    artefact_id=f"{run_id}_benchmark_uncertainty_intervals",
                    artefact_type="figure",
                    format="png",
                    path=fig_path,
                )

        if "false_positive_lrd" in report_spec.figure_set:
            rows = [
                {
                    "estimator_name": m.estimator_name,
                    "value": m.value,
                }
                for m in metrics.aggregate
                if m.metric_name == "false_positive_lrd_rate"
                and m.stratum.get("level") == "balanced_global"
                and m.value is not None
            ]
            if rows:
                plt, _sns = _load_plotting()
                fig_dir = run_dir / "figures"
                fig_dir.mkdir(parents=True, exist_ok=True)
                dfp = pd.DataFrame(rows).groupby("estimator_name", as_index=True)["value"].mean()
                fig_path = fig_dir / "false_positive_lrd.png"
                _fig, ax = plt.subplots(figsize=(6, max(3.0, 0.35 * len(dfp.index))))
                dfp.sort_values().plot(kind="barh", ax=ax, color="indianred")
                ax.set_xlabel("False-positive LRD rate")
                ax.set_ylabel("Estimator")
                ax.set_title("False-positive LRD")
                plt.tight_layout()
                plt.savefig(fig_path, dpi=140)
                plt.close()
                figure_paths.append(str(fig_path.as_posix()))
                _record_artifact(
                    artefact_id=f"{run_id}_false_positive_lrd",
                    artefact_type="figure",
                    format="png",
                    path=fig_path,
                )

        latex_paths: list[str] = []
        if "latex" in report_spec.formats:
            latex_dir = run_dir / "latex"
            latex_dir.mkdir(parents=True, exist_ok=True)
            tex_path = latex_dir / "metrics_summary.tex"
            _write_latex_table(
                tex_path,
                ("Estimator", "Metric", "Nominal", "Value"),
                [
                    (
                        m.estimator_name,
                        m.metric_name,
                        m.metadata.get("nominal", "--"),
                        m.value,
                    )
                    for m in unc
                ],
            )
            latex_paths.append(str(tex_path.as_posix()))
            _record_artifact(
                artefact_id=f"{run_id}_latex_metrics",
                artefact_type="latex_table",
                format="tex",
                path=tex_path,
            )

            latex_specs = (
                (
                    "disagreement_summary",
                    ("Estimator", "Metric", "Value", "Scope"),
                    [
                        (
                            r["estimator_name"],
                            r["metric_name"],
                            r["value"],
                            r["scope"],
                        )
                        for r in disagreement_rows
                        if r["scope"] == "aggregate"
                    ],
                ),
                (
                    "sensitivity_summary",
                    ("Estimator", "Metric", "Value", "Scope"),
                    [
                        (
                            r["estimator_name"],
                            r["metric_name"],
                            r["value"],
                            r["scope"],
                        )
                        for r in sensitivity_rows
                        if r["scope"] == "aggregate"
                    ],
                ),
                (
                    "benchmark_uncertainty",
                    ("Estimator", "Metric", "Value", "CI low", "CI high"),
                    [
                        (
                            r["estimator_name"],
                            r["metric_name"],
                            r["value"],
                            r["ci_low"],
                            r["ci_high"],
                        )
                        for r in benchmark_uncertainty_rows
                    ],
                ),
                (
                    "failure_summary",
                    ("Estimator", "Invalid", "Missing UQ", "Invalid Rate"),
                    [
                        (
                            r["estimator_name"],
                            r["n_invalid_estimates"],
                            r["n_missing_uncertainty"],
                            r["invalid_rate"],
                        )
                        for r in failure_summary_rows
                    ],
                ),
            )
            for stem, headers, rows_for_table in latex_specs:
                path = latex_dir / f"{stem}.tex"
                _write_latex_table(path, headers, rows_for_table)
                latex_paths.append(str(path.as_posix()))
                _record_artifact(
                    artefact_id=f"{run_id}_latex_{stem}",
                    artefact_type="latex_table",
                    format="tex",
                    path=path,
                )

        # HTML summary
        title = html.escape(manifest.name)

        def _primary_component(vals: dict[str, float | None]) -> float:
            for v in vals.values():
                if v is not None:
                    return float(v)
            return float("nan")

        rows_html = "".join(
            f"<tr><td>{html.escape(r.estimator_name)}</td><td>{int(r.rank)}</td><td>{float(r.score):.6g}</td><td>{_primary_component(dict(r.component_values)):.6g}</td></tr>"
            for r in leaderboards
        )
        unc_rows = "".join(
            f"<tr><td>{html.escape(m.estimator_name)}</td>"
            f"<td>{html.escape(m.metric_name)}</td>"
            f"<td>{html.escape(str(m.metadata.get('nominal', '')))}</td>"
            f"<td>{'NA' if m.value is None else float(m.value):.6g}</td></tr>"
            for m in unc
        )
        unc_table = (
            '<table border="1" cellpadding="4">'
            "<thead><tr><th>Estimator</th><th>Metric</th><th>Nominal</th><th>Value</th></tr></thead>"
            f"<tbody>{unc_rows or '<tr><td colspan=4>No uncertainty metrics</td></tr>'}</tbody></table>"
        )
        failure_table = _html_table(
            ("Estimator", "Invalid", "Missing Values", "Missing UQ", "Invalid Rate"),
            [
                (
                    r["estimator_name"],
                    r["n_invalid_estimates"],
                    r["n_missing_values"],
                    r["n_missing_uncertainty"],
                    r["invalid_rate"],
                )
                for r in failure_summary_rows[:25]
            ],
            empty="No failure rows",
        )
        disagreement_table = _html_table(
            ("Estimator", "Metric", "Value", "Scope"),
            [
                (r["estimator_name"], r["metric_name"], r["value"], r["scope"])
                for r in disagreement_rows
                if r["scope"] == "aggregate"
            ][:25],
            empty="No estimator disagreement metrics",
        )
        sensitivity_table = _html_table(
            ("Estimator", "Metric", "Value", "Scope"),
            [
                (r["estimator_name"], r["metric_name"], r["value"], r["scope"])
                for r in sensitivity_rows
                if r["scope"] == "aggregate"
            ][:25],
            empty="No scale/window sensitivity metrics",
        )
        benchmark_uncertainty_table = _html_table(
            ("Estimator", "Metric", "Value", "CI low", "CI high"),
            [
                (r["estimator_name"], r["metric_name"], r["value"], r["ci_low"], r["ci_high"])
                for r in benchmark_uncertainty_rows[:25]
            ],
            empty="No benchmark uncertainty intervals",
        )

        body = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>{title}</title></head>
<body>
<h1>{title}</h1>
<p>Mode: <strong>{html.escape(manifest.mode.value)}</strong></p>
<p>Manifest: <code>{html.escape(manifest.manifest_id)}</code></p>
<h2>Leaderboard</h2>
<table border="1" cellpadding="4">
<thead><tr><th>Estimator</th><th>Rank</th><th>Score</th><th>Primary component</th></tr></thead>
<tbody>{rows_html or "<tr><td colspan=4>No leaderboard rows</td></tr>"}</tbody>
</table>
<h2>Failure Summary</h2>
{failure_table}
<h2>Estimator Disagreement</h2>
{disagreement_table}
<h2>Scale/window Sensitivity</h2>
{sensitivity_table}
<h2>Benchmark Uncertainty</h2>
{benchmark_uncertainty_table}
<h2>Uncertainty Calibration</h2>
{unc_table}
<h2>Audit Artefacts</h2>
<ul>
<li><code>{html.escape(str(estimator_metadata_path.as_posix()))}</code></li>
<li><code>{html.escape(str(failures_path.as_posix()))}</code></li>
<li><code>{html.escape(str(benchmark_uncertainty_path.as_posix()))}</code></li>
<li><code>{html.escape(str(environment_path.as_posix()))}</code></li>
<li><code>{html.escape(str(artefact_index_path.as_posix()))}</code></li>
</ul>
<p><em>Observational safeguards:</em> this report is mode-aware; ground-truth metrics are omitted in observational mode by construction.</p>
</body></html>"""
        html_path = html_dir / "report.html"
        html_path.write_text(body, encoding="utf-8")
        _record_artifact(
            artefact_id=f"{run_id}_html",
            artefact_type="html_report",
            format="html",
            path=html_path,
        )

        _record_artifact(
            artefact_id=f"{run_id}_artefact_index_csv",
            artefact_type="artefact_index",
            format="csv",
            path=artefact_index_path,
        )
        pd.DataFrame(
            [
                {
                    "artefact_id": a.artefact_id,
                    "run_id": a.run_id,
                    "artefact_type": a.artefact_type,
                    "format": a.format,
                    "path": a.path,
                    "hash": a.hash,
                    "created_at": a.created_at,
                    "depends_on_json": json.dumps(tuple(a.depends_on)),
                }
                for a in artefacts
            ]
        ).to_csv(artefact_index_path, index=False)

        return ReportBundle(
            run_id=run_id,
            summary_table_path=str(run_summary_path.as_posix()),
            leaderboard_paths=(str(lb_path.as_posix()),),
            figure_paths=tuple(figure_paths),
            latex_table_paths=tuple(latex_paths),
            html_report_path=str(html_path.as_posix()),
            result_store_path=None,
            artefacts=tuple(artefacts),
        )
