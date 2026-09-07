"""Build complete analysis tables and figures only after the audit passes."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from audit import RUN, file_hash
from matplotlib.colors import Normalize, TwoSlopeNorm


def cell_label(cell):
    family, parameter, length = cell.split("_")
    return f"{parameter}\n{length[1:]}"


def main(source, destination):
    evidence = json.loads((destination / "audit_evidence.json").read_text(encoding="utf-8"))
    if evidence["status"] != "passed" or evidence["run_identity_sha256"] != RUN:
        raise ValueError("A passing audit of this run is required.")
    canonical = source / "summaries/canonical_summary.csv"
    if file_hash(source / "summaries/complete.json") != evidence["summary_manifest_sha256"]:
        raise ValueError("The audited summary manifest changed.")
    frame = pd.read_csv(
        canonical, keep_default_na=False, float_precision="round_trip", low_memory=False
    )
    for key in ["value", "ci_low", "ci_high", "mcse", "bootstrap_se", "n", "parameter", "H_target"]:
        frame[key] = frame[key].map(lambda v: np.nan if v == "" else float(v))
    columns = [
        "run_identity_sha256",
        "scope",
        "cell",
        "domain",
        "interval_role",
        "parameter",
        "n",
        "H_target",
        "method",
        "condition",
        "metric",
        "contrast",
        "value",
        "ci_low",
        "ci_high",
        "interval_method",
        "mcse",
        "bootstrap_se",
        "parents_attempted",
        "parents_used",
        "parents_excluded",
        "support",
        "successes",
        "denominator",
    ]
    tables = {}
    for scope in ["accuracy", "stress", "intervals"]:
        for aggregate in [False, True]:
            subset = frame[
                (frame.scope == scope) & (frame.cell.eq("domain_aggregate") == aggregate)
            ]
            # Keep every metric and contrast; numeric endpoints are never rounded in CSV.
            name = scope + ("_domains" if aggregate else "_cells") + ".csv.gz"
            subset[columns].to_csv(
                destination / name, index=False, compression={"method": "gzip", "mtime": 0}
            )
            tables[name] = len(subset)
    contrasts = frame[frame.contrast.ne("")]
    contrasts[columns].to_csv(
        destination / "planned_contrasts.csv.gz",
        index=False,
        compression={"method": "gzip", "mtime": 0},
    )
    tables["planned_contrasts.csv.gz"] = len(contrasts)
    for name, subset in [
        ("accuracy_mae", frame[frame.scope.eq("accuracy") & frame.metric.eq("mae")]),
        (
            "interval_coverage",
            frame[frame.scope.eq("intervals") & frame.metric.eq("unconditional_coverage")],
        ),
        (
            "stress_effects_domains",
            frame[
                frame.scope.eq("stress")
                & frame.cell.eq("domain_aggregate")
                & frame.metric.isin(["absolute_error_inflation", "absolute_estimate_drift"])
            ],
        ),
    ]:
        subset[columns].to_csv(destination / (name + ".csv"), index=False)
        tables[name + ".csv"] = len(subset)
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 9,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "svg.fonttype": "none",
            "savefig.facecolor": "white",
        }
    )
    methods = sorted(frame[frame.scope.eq("accuracy")].method.unique())
    families = ["fGn", "ARFIMA", "AR1"]
    accuracy = frame[
        (frame.scope == "accuracy") & (frame.cell != "domain_aggregate") & (frame.metric == "mae")
    ]
    fig, axes = plt.subplots(
        1, 3, figsize=(15, 8), sharey=True, gridspec_kw={"width_ratios": [12, 9, 12]}
    )
    norm = Normalize(0, np.ceil(accuracy.value.max() * 10) / 10)
    for ax, family in zip(axes, families, strict=True):
        subset = accuracy[accuracy.domain == family]
        cells = (
            subset[["cell", "parameter", "n"]]
            .drop_duplicates()
            .sort_values(["parameter", "n"])
            .cell.tolist()
        )
        matrix = subset.pivot(index="method", columns="cell", values="value").loc[methods, cells]
        im = ax.imshow(matrix, cmap="magma_r", norm=norm, aspect="auto", interpolation="nearest")
        ax.set_xticks(range(len(cells)), [cell_label(c) for c in cells], fontsize=8)
        ax.set_yticks(range(len(methods)), methods)
        ax.set_title(family + (" (target H = 0.5)" if family == "AR1" else ""), fontweight="bold")
        ax.set_xlabel(
            ("H" if family == "fGn" else "d" if family == "ARFIMA" else "phi") + " / record length"
        )
        for x in range(3, len(cells), 3):
            ax.axvline(x - 0.5, color="white", linewidth=1)
    fig.suptitle(
        "Clean-record mean absolute error across every declared cell", fontsize=15, y=0.975
    )
    fig.subplots_adjust(left=0.205, right=0.91, bottom=0.13, top=0.89, wspace=0.08)
    cax = fig.add_axes([0.935, 0.2, 0.014, 0.58])
    fig.colorbar(im, cax=cax, label="MAE (H units; common color scale)")
    fig.text(
        0.205,
        0.035,
        "2,000 independent parents per cell; 21 pipelines. Fixed sample-scale rules vary by method.\nAll points valid. Error is relative to the declared process target; no global ranking is inferred.",
        fontsize=9,
    )
    for ext in ["png", "svg"]:
        fig.savefig(destination / f"clean_accuracy.{ext}", dpi=180)
    plt.close(fig)

    coverage = frame[
        (frame.scope == "intervals")
        & (frame.cell != "domain_aggregate")
        & (frame.metric == "unconditional_coverage")
    ]
    cells = [
        "fGn_0.25_n512",
        "fGn_0.5_n512",
        "fGn_0.75_n512",
        "fGn_0.85_n512",
        "ARFIMA_0.25_n512",
        "AR1_0.8_n512",
        "AR1_0.95_n512",
        "fGn_0.5_n1024",
        "fGn_0.85_n1024",
        "AR1_0.95_n1024",
    ]
    from audit import LABELS

    matrix = coverage.pivot(index=["method", "condition"], columns="cell", values="value").loc[
        LABELS, cells
    ]
    short = {
        "cbc_raw_percentile": "CBC raw percentile",
        "cbc_raw_basic": "CBC raw basic",
        "cbc_centered_percentile": "CBC centered percentile",
        "cbc_centered_basic": "CBC centered basic",
        "unknown_fgn_centered_basic": "Fitted fGn centered basic",
        "gph_normal_raw": "GPH normal",
    }
    labels = [("GPH" if m.startswith("GPH") else m) + " | " + short[c] for m, c in LABELS]
    fig, ax = plt.subplots(figsize=(14, 9))
    im = ax.imshow(
        matrix,
        aspect="auto",
        cmap="RdYlBu",
        norm=TwoSlopeNorm(vmin=0, vcenter=0.95, vmax=1),
        interpolation="nearest",
    )
    ax.set_yticks(range(16), labels)
    ax.set_xticks(
        range(10),
        [c.replace("_n", "\nn=").replace("_", " ") for c in cells],
        rotation=40,
        ha="right",
    )
    for i in range(16):
        for j in range(10):
            value = matrix.iloc[i, j]
            ax.text(
                j,
                i,
                f"{value * 100:.2f}",
                ha="center",
                va="center",
                fontsize=9,
                color="white" if value < 0.25 or value > 0.99 else "black",
            )
    ax.axvline(6.5, color="black", linewidth=2)
    ax.axhline(5.5, color="black", linewidth=1)
    ax.axhline(10.5, color="black", linewidth=1)
    fig.suptitle(
        "95% interval coverage depends on both construction and process", fontsize=15, y=0.975
    )
    ax.set_title(
        "Core: n=512, R=2,000                                     Sensitivity: n=1024, R=500",
        fontsize=10,
        pad=15,
    )
    fig.subplots_adjust(left=0.29, right=0.91, bottom=0.24, top=0.88)
    cax = fig.add_axes([0.935, 0.3, 0.014, 0.5])
    colorbar = fig.colorbar(im, cax=cax, label="Coverage (%)")
    colorbar.set_ticks([0, 0.25, 0.5, 0.75, 0.95, 1], labels=["0", "25", "50", "75", "95", "100"])
    fig.text(
        0.29,
        0.045,
        "Numbers are percentages of all attempted parents; unavailable intervals count as misses.\nAll 248,000 intervals were available. Color midpoint = nominal 95%; color scale is piecewise linear.\nCellwise Wilson bounds and paired comparisons appear in the accompanying tables.",
        fontsize=9,
    )
    for ext in ["png", "svg"]:
        fig.savefig(destination / f"interval_coverage.{ext}", dpi=180)
    plt.close(fig)
    provenance = {
        "run_identity_sha256": RUN,
        "canonical_summary_sha256": file_hash(canonical),
        "export_source_sha256": file_hash(Path(__file__)),
        "table_rows": tables,
        "files": {
            p.name: file_hash(p)
            for p in sorted(destination.iterdir())
            if p.suffix in [".csv", ".gz", ".png", ".svg"]
        },
    }
    (destination / "export_provenance.json").write_text(
        json.dumps(provenance, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(tables, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    main(args.source, args.output)
