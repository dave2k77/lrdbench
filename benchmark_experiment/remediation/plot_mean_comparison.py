"""Plot each method's coverage and width across lengths, retaining all controls."""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ORDER = ["fGn_0.25", "fGn_0.5", "fGn_0.75", "fGn_0.85", "ARFIMA_0.25", "AR1_0.8", "AR1_0.95"]
LABELS = [
    "fGn\nH=.25",
    "fGn\nH=.50",
    "fGn\nH=.75",
    "fGn\nH=.85",
    "ARFIMA\nd=.25",
    "AR(1)\nphi=.80",
    "AR(1)\nphi=.95",
]
STYLES = {
    "cbc_percentile": ("Blocks: raw percentile", "#b9382c", "o"),
    "cbc_centered_percentile": ("Blocks: centered percentile", "#c88113", "v"),
    "cbc_centered_basic": ("Blocks: centered basic", "#8b6508", "s"),
    "zero_raw_basic": ("fGn zero mean: raw basic", "#7a60a3", "^"),
    "zero_centered_basic": ("fGn zero mean: centered basic", "#368d7b", "P"),
    "unknown_centered_basic": ("fGn unknown mean: centered basic", "#195bab", "D"),
    "gph_raw_normal": ("GPH normal approximation", "#333333", "x"),
}


def plot(table, method, output):
    table = table[table.method == method]
    lengths = sorted(table.n.unique())
    fig, axes = plt.subplots(
        2, len(lengths), figsize=(16, 9), sharex=True, sharey="row", squeeze=False
    )
    for column, n in enumerate(lengths):
        order = [f"{prefix}_n{n}" for prefix in ORDER]
        for index, (candidate, (label, color, marker)) in enumerate(STYLES.items()):
            group = table[(table.n == n) & (table.candidate == candidate)].set_index("cell")
            if group.empty:
                continue
            group = group.reindex(order)
            x = np.arange(len(order)) + (index - 3) * 0.105
            y = group.coverage.to_numpy(float) * 100
            axes[0, column].errorbar(
                x,
                y,
                yerr=np.maximum(
                    0, np.vstack((y - group.wilson_low * 100, group.wilson_high * 100 - y))
                ),
                fmt=marker,
                color=color,
                markersize=3.6,
                capsize=1.5,
                linewidth=0.8,
                label=label,
            )
            axes[1, column].plot(
                x, group.mean_width, marker=marker, color=color, linewidth=0.7, markersize=3.6
            )
        axes[0, column].set_title(f"n = {n}", fontsize=13, weight="bold")
        axes[0, column].axhline(95, color="#555555", linestyle="--", linewidth=1)
        for row in range(2):
            ax = axes[row, column]
            ax.axvline(3.5, color="#9ca3af", linewidth=1)
            ax.set_xticks(np.arange(len(order)), LABELS, fontsize=8)
            ax.spines[["top", "right"]].set_visible(False)
            ax.grid(axis="y", alpha=0.2)
    axes[0, 0].set_ylim(-4, 105)
    axes[1, 0].set_ylim(0, 1.08 * table.mean_width.max())
    axes[0, 0].set_ylabel("Coverage among available intervals (%)")
    axes[1, 0].set_ylabel("Mean interval width (H units)")
    handles, labels = axes[0, 0].get_legend_handles_labels()
    fig.legend(
        handles,
        labels,
        loc="lower center",
        ncol=3,
        frameon=False,
        bbox_to_anchor=(0.5, 0.047),
        fontsize=9,
    )
    fig.suptitle(
        f"{method}: mean handling and record length", x=0.06, ha="left", fontsize=18, weight="bold"
    )
    fig.text(
        0.06,
        0.926,
        "64 independent records/cell | 199 draws/pool | error bars: Wilson 95% Monte Carlo intervals",
        fontsize=10,
    )
    footnote = "Dashed: nominal 95%. Vertical divider: fGn / model-mismatch controls. Development evidence; no confirmation claim."
    if method == "GPH":
        footnote += " Centered normal overlaps raw."
    fig.text(0.06, 0.02, footnote, fontsize=8.5)
    fig.subplots_adjust(left=0.06, right=0.985, top=0.88, bottom=0.21, hspace=0.12, wspace=0.12)
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, dpi=170, facecolor="white")
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    table = pd.read_csv(args.input)
    for method in ("Higuchi", "GHE", "GPH"):
        plot(table, method, args.output / f"mean_comparison_{method.lower()}.png")


if __name__ == "__main__":
    main()
