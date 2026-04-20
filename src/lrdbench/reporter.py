from __future__ import annotations

import html
import json
from collections.abc import Sequence
from datetime import UTC, datetime
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

_STRESS_METRIC_NAMES = frozenset(
    {
        "estimate_drift",
        "relative_degradation_ratio",
        "validity_collapse",
        "coverage_collapse",
    }
)


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
        artefacts.append(
            ArtefactRecord(
                artefact_id=f"{run_id}_run_summary",
                run_id=run_id,
                artefact_type="metric_export",
                format="csv",
                path=str(run_summary_path.as_posix()),
                created_at=datetime.now(UTC).isoformat(),
            )
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
        artefacts.append(
            ArtefactRecord(
                artefact_id=f"{run_id}_leaderboard_csv",
                run_id=run_id,
                artefact_type="leaderboard_export",
                format="csv",
                path=str(lb_path.as_posix()),
                created_at=datetime.now(UTC).isoformat(),
            )
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
        artefacts.append(
            ArtefactRecord(
                artefact_id=f"{run_id}_metrics_csv",
                run_id=run_id,
                artefact_type="metric_export",
                format="csv",
                path=str(agg_path.as_posix()),
                created_at=datetime.now(UTC).isoformat(),
            )
        )

        failure_map_path = tables / "failure_map.csv"
        failure_rows = _failure_map_rows(metrics)
        if failure_rows:
            pd.DataFrame(failure_rows).to_csv(failure_map_path, index=False)
        else:
            failure_map_path.write_text("", encoding="utf-8")
        artefacts.append(
            ArtefactRecord(
                artefact_id=f"{run_id}_failure_map_csv",
                run_id=run_id,
                artefact_type="metric_export",
                format="csv",
                path=str(failure_map_path.as_posix()),
                created_at=datetime.now(UTC).isoformat(),
            )
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
        artefacts.append(
            ArtefactRecord(
                artefact_id=f"{run_id}_uncertainty_csv",
                run_id=run_id,
                artefact_type="metric_export",
                format="csv",
                path=str(unc_path.as_posix()),
                created_at=datetime.now(UTC).isoformat(),
            )
        )

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
            artefacts.append(
                ArtefactRecord(
                    artefact_id=f"{run_id}_stress_metrics_csv",
                    run_id=run_id,
                    artefact_type="metric_export",
                    format="csv",
                    path=str(stress_path.as_posix()),
                    created_at=datetime.now(UTC).isoformat(),
                )
            )

        if (
            manifest.mode is BenchmarkMode.STRESS_TEST
            and "degradation_curve" in report_spec.figure_set
        ):
            try:
                import matplotlib

                matplotlib.use("Agg")
                import matplotlib.pyplot as plt
            except ImportError:
                pass
            else:
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
                    artefacts.append(
                        ArtefactRecord(
                            artefact_id=f"{run_id}_degradation_curve",
                            run_id=run_id,
                            artefact_type="figure",
                            format="png",
                            path=str(fig_path.as_posix()),
                            created_at=datetime.now(UTC).isoformat(),
                        )
                    )

        latex_paths: list[str] = []
        if "latex" in report_spec.formats:
            latex_dir = run_dir / "latex"
            latex_dir.mkdir(parents=True, exist_ok=True)
            tex_path = latex_dir / "metrics_summary.tex"

            def _tex_escape(s: str) -> str:
                return (
                    str(s)
                    .replace("\\", r"\textbackslash{}")
                    .replace("&", r"\&")
                    .replace("%", r"\%")
                    .replace("#", r"\#")
                    .replace("_", r"\_")
                )

            lines = [
                r"\begin{tabular}{l l r r}",
                r"\hline",
                r"Estimator & Metric & Nominal & Value \\",
                r"\hline",
            ]
            for m in unc:
                nom = m.metadata.get("nominal")
                nom_s = f"{float(nom):.4f}" if isinstance(nom, (int, float)) else "--"
                val = m.value
                val_s = f"{float(val):.6g}" if val is not None else "NA"
                en = _tex_escape(m.estimator_name)
                mn = _tex_escape(m.metric_name)
                lines.append(f"{en} & {mn} & {nom_s} & {val_s} \\\\")
            lines.extend([r"\hline", r"\end{tabular}"])
            tex_path.write_text("\n".join(lines), encoding="utf-8")
            latex_paths.append(str(tex_path.as_posix()))
            artefacts.append(
                ArtefactRecord(
                    artefact_id=f"{run_id}_latex_metrics",
                    run_id=run_id,
                    artefact_type="latex_table",
                    format="tex",
                    path=str(tex_path.as_posix()),
                    created_at=datetime.now(UTC).isoformat(),
                )
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
        unc_block = (
            "<h2>Uncertainty (global aggregates)</h2>"
            '<table border="1" cellpadding="4">'
            "<thead><tr><th>Estimator</th><th>Metric</th><th>Nominal</th><th>Value</th></tr></thead>"
            f"<tbody>{unc_rows or '<tr><td colspan=4>No uncertainty metrics</td></tr>'}</tbody></table>"
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
{unc_block}
<p><em>Observational safeguards:</em> this report is mode-aware; ground-truth metrics are omitted in observational mode by construction.</p>
</body></html>"""
        html_path = html_dir / "report.html"
        html_path.write_text(body, encoding="utf-8")
        artefacts.append(
            ArtefactRecord(
                artefact_id=f"{run_id}_html",
                run_id=run_id,
                artefact_type="html_report",
                format="html",
                path=str(html_path.as_posix()),
                created_at=datetime.now(UTC).isoformat(),
            )
        )

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
