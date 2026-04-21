from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml

from lrdbench.interfaces import BaseResultStore
from lrdbench.schema import BenchmarkManifest, EstimateResult, MetricBundle, SeriesRecord


class CsvResultStore(BaseResultStore):
    """Minimal Phase 1 result store: CSV tables + numpy series sidecar files."""

    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self.raw = self.root / "raw"
        self.manifest_dir = self.root / "manifest"
        self.raw.mkdir(parents=True, exist_ok=True)
        self.manifest_dir.mkdir(parents=True, exist_ok=True)
        self._records_rows: list[dict[str, Any]] = []
        self._estimates_rows: list[dict[str, Any]] = []
        self._metrics_rows: list[dict[str, Any]] = []
        self._leader_rows: list[dict[str, Any]] = []
        self._artefact_rows: list[dict[str, Any]] = []

    def write_run_metadata(self, manifest: BenchmarkManifest, run_id: str) -> None:
        meta = {
            "run_id": run_id,
            "manifest_id": manifest.manifest_id,
            "name": manifest.name,
            "mode": manifest.mode.value,
        }
        (self.root / "run_summary.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
        if manifest.raw_yaml is not None:
            (self.manifest_dir / "benchmark_manifest.yaml").write_text(
                yaml.safe_dump(manifest.raw_yaml, sort_keys=False),
                encoding="utf-8",
            )

    def write_records(self, records: Sequence[SeriesRecord]) -> None:
        values_dir = self.raw / "values"
        values_dir.mkdir(parents=True, exist_ok=True)
        for rec in records:
            path = values_dir / f"{rec.record_id}.npy"
            np.save(path, rec.values)
            row = {
                "record_id": rec.record_id,
                "source_type": rec.source_type.value,
                "source_name": rec.source_name,
                "n": int(rec.values.size),
                "values_path": str(path.as_posix()),
                "truth_family": rec.truth.process_family if rec.truth else None,
                "target_estimand": rec.truth.target_estimand if rec.truth else None,
                "target_value": rec.truth.target_value if rec.truth else None,
                "annotations_json": json.dumps(dict(rec.annotations), sort_keys=True),
            }
            self._records_rows.append(row)

    def write_estimates(self, estimates: Sequence[EstimateResult]) -> None:
        for e in estimates:
            cis = [{"nominal": a, "ci_low": lo, "ci_high": hi} for a, lo, hi in e.bootstrap_cis]
            self._estimates_rows.append(
                {
                    "record_id": e.record_id,
                    "estimator_name": e.estimator_name,
                    "point": e.point,
                    "ci_low": e.ci_low,
                    "ci_high": e.ci_high,
                    "stderr": e.stderr,
                    "valid": e.valid,
                    "runtime_seconds": e.runtime_seconds,
                    "failure_reason": e.failure_reason,
                    "warnings": "|".join(e.warnings),
                    "bootstrap_cis_json": json.dumps(cis),
                }
            )

    def write_metrics(self, metrics: MetricBundle) -> None:
        for m in metrics.per_series:
            self._metrics_rows.append(
                {
                    "scope": "per_series",
                    "record_id": m.record_id,
                    "estimator_name": m.estimator_name,
                    "metric_name": m.metric_name,
                    "value": m.value,
                    "stratum_json": json.dumps(dict(m.stratum), sort_keys=True),
                    "metadata_json": json.dumps(dict(m.metadata), sort_keys=True),
                }
            )
        for m in metrics.aggregate:
            self._metrics_rows.append(
                {
                    "scope": "aggregate",
                    "record_id": m.record_id,
                    "estimator_name": m.estimator_name,
                    "metric_name": m.metric_name,
                    "value": m.value,
                    "stratum_json": json.dumps(dict(m.stratum), sort_keys=True),
                    "metadata_json": json.dumps(dict(m.metadata), sort_keys=True),
                }
            )
        for m in metrics.uncertainty:
            self._metrics_rows.append(
                {
                    "scope": "uncertainty",
                    "record_id": m.record_id,
                    "estimator_name": m.estimator_name,
                    "metric_name": m.metric_name,
                    "value": m.value,
                    "stratum_json": json.dumps(dict(m.stratum), sort_keys=True),
                    "metadata_json": json.dumps(dict(m.metadata), sort_keys=True),
                }
            )

    def write_leaderboards(self, rows: Sequence[Any]) -> None:
        for r in rows:
            self._leader_rows.append(
                {
                    "estimator_name": r.estimator_name,
                    "rank": r.rank,
                    "score": r.score,
                    "components_json": json.dumps(dict(r.component_values), sort_keys=True),
                }
            )

    def write_artefacts(self, rows: Sequence[Any]) -> None:
        for a in rows:
            self._artefact_rows.append(
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
            )

    def finalise(self) -> str:
        if self._records_rows:
            pd.DataFrame(self._records_rows).to_csv(self.raw / "records.csv", index=False)
        if self._estimates_rows:
            pd.DataFrame(self._estimates_rows).to_csv(self.raw / "estimates.csv", index=False)
        if self._metrics_rows:
            pd.DataFrame(self._metrics_rows).to_csv(self.raw / "metrics.csv", index=False)
        if self._leader_rows:
            pd.DataFrame(self._leader_rows).to_csv(self.raw / "leaderboards.csv", index=False)
        if self._artefact_rows:
            pd.DataFrame(self._artefact_rows).to_csv(self.raw / "artefacts.csv", index=False)
        return str(self.root.resolve())
