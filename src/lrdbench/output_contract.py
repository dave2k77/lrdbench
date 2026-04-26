from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

PUBLIC_OUTPUT_CONTRACT_VERSION = "0.9.0-rc1"

PUBLIC_OUTPUT_CONTRACT: dict[str, Any] = {
    "contract_version": PUBLIC_OUTPUT_CONTRACT_VERSION,
    "run_root": "<report.export_root>/<run_id>",
    "required_files": {
        "summary": [
            "tables/run_summary.csv",
            "tables/per_stratum_metrics.csv",
            "tables/leaderboard.csv",
            "tables/estimator_metadata.csv",
            "tables/failures.csv",
            "tables/failure_map.csv",
            "tables/uncertainty_calibration.csv",
            "tables/benchmark_uncertainty.csv",
            "tables/estimator_disagreement.csv",
            "tables/scale_window_sensitivity.csv",
            "html/report.html",
            "manifest/environment.json",
            "artefacts/artefact_index.csv",
        ],
        "raw_result_store": [
            "raw/records.csv",
            "raw/estimates.csv",
            "raw/metrics.csv",
            "raw/artefacts.csv",
        ],
    },
    "conditional_files": {
        "tables/stress_metrics.csv": "present for stress_test reports",
        "raw/leaderboards.csv": "present when leaderboard rows are generated",
        "manifest/benchmark_manifest.yaml": "present when the manifest was loaded from YAML",
        "figures/*.png": "present when requested report.figure_set entries have data",
        "latex/*.tex": "present when latex report output is requested",
    },
    "required_columns": {
        "tables/run_summary.csv": ["run_id", "manifest_id", "benchmark_name", "mode"],
        "tables/per_stratum_metrics.csv": [
            "estimator_name",
            "metric_name",
            "value",
            "stratum_json",
            "metadata_json",
        ],
        "tables/leaderboard.csv": ["estimator_name", "rank", "score"],
        "tables/estimator_metadata.csv": [
            "estimator_name",
            "family",
            "target_estimand",
            "supports_ci",
            "supports_diagnostics",
            "assumptions_json",
            "params_json",
            "version",
        ],
        "tables/failures.csv": [
            "estimator_name",
            "stratum_json",
            "n_metric_rows",
            "n_missing_values",
            "n_missing_uncertainty",
            "n_validity_observations",
            "n_invalid_estimates",
            "invalid_rate",
            "missing_value_rate",
        ],
        "tables/failure_map.csv": ["estimator_name", "stratum_json"],
        "tables/uncertainty_calibration.csv": [
            "estimator_name",
            "metric_name",
            "value",
            "nominal",
        ],
        "tables/benchmark_uncertainty.csv": [
            "estimator_name",
            "metric_name",
            "value",
            "uncertainty_type",
            "aggregation",
            "nominal",
            "ci_low",
            "ci_high",
            "stratum_json",
            "metadata_json",
        ],
        "tables/estimator_disagreement.csv": [
            "scope",
            "record_id",
            "estimator_name",
            "metric_name",
            "value",
            "stratum_json",
            "metadata_json",
        ],
        "tables/scale_window_sensitivity.csv": [
            "scope",
            "record_id",
            "estimator_name",
            "metric_name",
            "value",
            "stratum_json",
            "metadata_json",
        ],
        "tables/stress_metrics.csv": [
            "record_id",
            "estimator_name",
            "metric_name",
            "value",
            "stratum_json",
            "contamination_operator",
            "clean_record_id",
            "nominal",
        ],
        "artefacts/artefact_index.csv": [
            "artefact_id",
            "run_id",
            "artefact_type",
            "format",
            "path",
            "hash",
            "created_at",
            "depends_on_json",
        ],
        "raw/records.csv": [
            "record_id",
            "source_type",
            "source_name",
            "n",
            "values_path",
            "truth_family",
            "target_estimand",
            "target_value",
            "annotations_json",
        ],
        "raw/estimates.csv": [
            "record_id",
            "estimator_name",
            "point",
            "ci_low",
            "ci_high",
            "stderr",
            "valid",
            "runtime_seconds",
            "failure_reason",
            "warnings",
            "bootstrap_cis_json",
        ],
        "raw/metrics.csv": [
            "scope",
            "record_id",
            "estimator_name",
            "metric_name",
            "value",
            "stratum_json",
            "metadata_json",
        ],
        "raw/leaderboards.csv": ["estimator_name", "rank", "score", "components_json"],
        "raw/artefacts.csv": [
            "artefact_id",
            "run_id",
            "artefact_type",
            "format",
            "path",
            "hash",
            "created_at",
            "depends_on_json",
        ],
    },
    "dynamic_columns": {
        "tables/leaderboard.csv": "metric__<component_metric> columns are added per leaderboard",
        "tables/failure_map.csv": "stratum__<key> and metric__<metric_name> columns are data dependent",
        "tables/failures.csv": "stratum__<key> columns are data dependent",
    },
}


def public_output_contract() -> dict[str, Any]:
    return dict(PUBLIC_OUTPUT_CONTRACT)


def required_output_files() -> tuple[str, ...]:
    required = PUBLIC_OUTPUT_CONTRACT["required_files"]
    return (*required["summary"], *required["raw_result_store"])


def validate_output_contract(run_root: str | Path) -> list[str]:
    root = Path(run_root)
    errors: list[str] = []
    required_columns: dict[str, list[str]] = PUBLIC_OUTPUT_CONTRACT["required_columns"]

    for rel in required_output_files():
        path = root / rel
        if not path.is_file():
            errors.append(f"missing required file: {rel}")
            continue
        if rel.endswith(".csv"):
            errors.extend(_validate_csv_columns(path, rel, required_columns.get(rel, [])))

    for rel, columns in required_columns.items():
        if rel in required_output_files():
            continue
        path = root / rel
        if path.is_file():
            errors.extend(_validate_csv_columns(path, rel, columns))

    return errors


def _validate_csv_columns(path: Path, rel: str, required: list[str]) -> list[str]:
    if not required:
        return []
    try:
        with path.open(newline="", encoding="utf-8") as fh:
            reader = csv.reader(fh)
            header = next(reader, None)
    except UnicodeDecodeError as exc:
        return [f"{rel}: cannot read CSV as UTF-8: {exc}"]
    if not header:
        return [f"{rel}: missing CSV header"]
    missing = [name for name in required if name not in header]
    if missing:
        return [f"{rel}: missing required columns: {', '.join(missing)}"]
    return []
