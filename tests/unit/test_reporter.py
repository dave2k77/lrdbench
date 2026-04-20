from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from lrdbench.enums import BenchmarkMode
from lrdbench.reporter import SimpleHtmlCsvReporter
from lrdbench.schema import BenchmarkManifest, MetricBundle, MetricValue, ReportSpec


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
