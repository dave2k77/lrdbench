"""Export compact public summaries for the neural classical benchmark.

The full benchmark reports contain large row-level CSV files that should not be
tracked in git. This script derives small tables suitable for the repository
from completed report directories.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import pandas as pd


ROUND_DIGITS = 6


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(path)
    return pd.read_csv(path)


def _load_strata_column(df: pd.DataFrame) -> pd.DataFrame:
    if "stratum_json" not in df.columns:
        return df

    strata = df["stratum_json"].map(json.loads).apply(pd.Series)
    strata.columns = [f"stratum__{column}" for column in strata.columns]
    return pd.concat([df.drop(columns=["stratum_json"]), strata], axis=1)


def _round_numeric(df: pd.DataFrame) -> pd.DataFrame:
    result = df.copy()
    numeric_columns = result.select_dtypes(include="number").columns
    result[numeric_columns] = result[numeric_columns].round(ROUND_DIGITS)
    return result


def export_leaderboard_comparison(ground_truth: Path, stress: Path, output: Path) -> None:
    gt = _read_csv(ground_truth / "tables" / "leaderboard.csv")
    st = _read_csv(stress / "tables" / "leaderboard.csv")

    keep_gt = gt.rename(
        columns={
            "rank": "ground_truth_rank",
            "metric__mae": "ground_truth_mae",
            "metric__validity_rate": "ground_truth_validity_rate",
            "metric__runtime": "ground_truth_runtime_seconds",
        }
    )[
        [
            "estimator_name",
            "ground_truth_rank",
            "ground_truth_mae",
            "ground_truth_validity_rate",
            "ground_truth_runtime_seconds",
        ]
    ]
    keep_st = st.rename(
        columns={
            "rank": "stress_rank",
            "metric__mae": "stress_mae",
            "metric__estimate_drift": "stress_estimate_drift",
            "metric__validity_rate": "stress_validity_rate",
            "metric__runtime": "stress_runtime_seconds",
        }
    )[
        [
            "estimator_name",
            "stress_rank",
            "stress_mae",
            "stress_estimate_drift",
            "stress_validity_rate",
            "stress_runtime_seconds",
        ]
    ]

    merged = keep_gt.merge(keep_st, on="estimator_name", how="outer")
    merged["mae_delta_stress_minus_ground_truth"] = (
        merged["stress_mae"] - merged["ground_truth_mae"]
    )
    merged = merged.sort_values(["stress_rank", "ground_truth_rank"], na_position="last")
    _round_numeric(merged).to_csv(output / "estimator_leaderboard_comparison.csv", index=False)


def export_uncertainty_summary(ground_truth: Path, stress: Path, output: Path) -> None:
    def summarize(path: Path, prefix: str) -> pd.DataFrame:
        data = _read_csv(path / "tables" / "uncertainty_calibration.csv")
        pivot = (
            data.pivot_table(
                index="estimator_name",
                columns="metric_name",
                values="value",
                aggfunc="mean",
            )
            .reset_index()
            .rename_axis(None, axis=1)
        )
        rename = {
            column: f"{prefix}_mean_{column}"
            for column in pivot.columns
            if column != "estimator_name"
        }
        return pivot.rename(columns=rename)

    gt = summarize(ground_truth, "ground_truth")
    st = summarize(stress, "stress")
    merged = gt.merge(st, on="estimator_name", how="outer")
    merged["coverage_delta_stress_minus_ground_truth"] = (
        merged["stress_mean_coverage"] - merged["ground_truth_mean_coverage"]
    )
    merged["ci_width_delta_stress_minus_ground_truth"] = (
        merged["stress_mean_ci_width"] - merged["ground_truth_mean_ci_width"]
    )
    merged = merged.sort_values("coverage_delta_stress_minus_ground_truth")
    _round_numeric(merged).to_csv(output / "uncertainty_coverage_summary.csv", index=False)


def export_stress_operator_summary(stress: Path, output: Path) -> None:
    data = _read_csv(stress / "tables" / "stress_metrics.csv")
    summary = (
        data.groupby(["contamination_operator", "metric_name"], dropna=False)["value"]
        .agg(["mean", "median", "max", "count"])
        .reset_index()
        .pivot_table(
            index="contamination_operator",
            columns="metric_name",
            values=["mean", "median", "max", "count"],
            aggfunc="first",
        )
    )
    summary.columns = [
        f"{stat}_{metric}".strip("_") for stat, metric in summary.columns.to_flat_index()
    ]
    summary = summary.reset_index()
    _round_numeric(summary).to_csv(output / "stress_operator_summary.csv", index=False)

    worst = (
        data[data["metric_name"].isin(["estimate_drift", "coverage_collapse"])]
        .groupby(["contamination_operator", "estimator_name", "metric_name"], dropna=False)[
            "value"
        ]
        .mean()
        .reset_index()
        .sort_values(["metric_name", "value"], ascending=[True, False])
    )
    _round_numeric(worst).to_csv(output / "stress_estimator_failure_modes.csv", index=False)


def export_false_positive_summary(ground_truth: Path, output: Path) -> None:
    data = _load_strata_column(_read_csv(ground_truth / "tables" / "per_stratum_metrics.csv"))
    false_positive = data[
        (data["metric_name"] == "false_positive_lrd_rate")
        & (data["stratum__H"] == 0.5)
    ][["estimator_name", "stratum__n", "value"]].rename(
        columns={"stratum__n": "n", "value": "false_positive_lrd_rate_at_h_0_5"}
    )
    false_positive = false_positive.sort_values(
        ["false_positive_lrd_rate_at_h_0_5", "estimator_name"],
        ascending=[False, True],
    )
    _round_numeric(false_positive).to_csv(output / "false_positive_summary.csv", index=False)


def export_scale_window_summary(ground_truth: Path, stress: Path, output: Path) -> None:
    def summarize(path: Path, prefix: str) -> pd.DataFrame:
        data = _load_strata_column(_read_csv(path / "tables" / "scale_window_sensitivity.csv"))
        data = data[data["scope"] == "per_series"]
        return (
            data.groupby(["estimator_name", "metric_name"], dropna=False)["value"]
            .mean()
            .reset_index()
            .pivot_table(
                index="estimator_name",
                columns="metric_name",
                values="value",
                aggfunc="first",
            )
            .reset_index()
            .rename_axis(None, axis=1)
            .rename(
                columns={
                    "parameter_variant_sensitivity": f"{prefix}_parameter_variant_sensitivity",
                    "max_variant_drift": f"{prefix}_max_variant_drift",
                }
            )
        )

    gt = summarize(ground_truth, "ground_truth")
    st = summarize(stress, "stress")
    merged = gt.merge(st, on="estimator_name", how="outer").sort_values("estimator_name")
    _round_numeric(merged).to_csv(output / "scale_window_sensitivity_summary.csv", index=False)


def export_run_index(ground_truth: Path, stress: Path, output: Path) -> None:
    rows = []
    for label, path in [("ground_truth", ground_truth), ("stress", stress)]:
        summary = json.loads((path / "run_summary.json").read_text(encoding="utf-8"))
        rows.append(
            {
                "run_label": label,
                "run_id": summary["run_id"],
                "manifest_id": summary["manifest_id"],
                "mode": summary["mode"],
                "local_report_path": str(path.as_posix()),
            }
        )
    pd.DataFrame(rows).to_csv(output / "run_index.csv", index=False)


def write_checksums(output: Path) -> None:
    rows = []
    for path in sorted(output.glob("*.csv")):
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        rows.append({"sha256": digest, "file": path.name})
    pd.DataFrame(rows).to_csv(output / "checksums.sha256.csv", index=False)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ground-truth", type=Path, required=True)
    parser.add_argument("--stress", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    args.output.mkdir(parents=True, exist_ok=True)
    export_run_index(args.ground_truth, args.stress, args.output)
    export_leaderboard_comparison(args.ground_truth, args.stress, args.output)
    export_uncertainty_summary(args.ground_truth, args.stress, args.output)
    export_stress_operator_summary(args.stress, args.output)
    export_false_positive_summary(args.ground_truth, args.output)
    export_scale_window_summary(args.ground_truth, args.stress, args.output)
    write_checksums(args.output)


if __name__ == "__main__":
    main()
