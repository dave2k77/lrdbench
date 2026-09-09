"""Display development coverage and width without pooling unlike model domains."""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ORDER = [
    "fGn_0.25_n512",
    "fGn_0.5_n512",
    "fGn_0.75_n512",
    "fGn_0.85_n512",
    "ARFIMA_0.25_n512",
    "AR1_0.8_n512",
    "AR1_0.95_n512",
]
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
    "cbc_percentile": ("Block percentile", "#bd392c", "o"),
    "cbc_basic": ("Block basic", "#e28b26", "s"),
    "fgn_percentile": ("Fitted fGn percentile", "#24857c", "^"),
    "fgn_basic": ("Fitted fGn basic", "#2257a3", "D"),
    "gph_ols_normal": ("GPH normal approximation", "#855c9c", "v"),
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    table = pd.read_csv(args.input)
    fig, axes = plt.subplots(2, 3, figsize=(15, 8.8), sharex=True, sharey="row")
    for column, method in enumerate(("Higuchi", "GHE", "GPH")):
        for index, (candidate, (label, color, marker)) in enumerate(STYLES.items()):
            group = table[(table.method == method) & (table.candidate == candidate)].set_index(
                "cell"
            )
            if group.empty:
                continue
            group = group.reindex(ORDER)
            x = np.arange(len(ORDER)) + (index - 2) * 0.13
            y = group.coverage.to_numpy(float) * 100
            axes[0, column].errorbar(
                x,
                y,
                yerr=np.vstack((y - group.wilson_low * 100, group.wilson_high * 100 - y)),
                fmt=marker,
                color=color,
                markersize=4,
                capsize=2,
                linewidth=0.9,
                label=label,
            )
            axes[1, column].plot(
                x, group.mean_width, marker=marker, color=color, linewidth=0.8, markersize=4
            )
        axes[0, column].set_title(method, fontsize=13, weight="bold")
        axes[0, column].axhline(95, color="#4b5563", linestyle="--", linewidth=1)
        for row in range(2):
            axis = axes[row, column]
            axis.axvline(3.5, color="#9ca3af", linewidth=1)
            axis.set_xticks(np.arange(len(ORDER)), LABELS, fontsize=8)
            axis.grid(axis="y", alpha=0.2)
            axis.spines[["top", "right"]].set_visible(False)
        axes[0, column].set_ylim(-4, 105)
    axes[1, 0].set_ylim(0, 1.08 * table.mean_width.max())
    axes[0, 0].set_ylabel("Coverage among available intervals (%)")
    axes[1, 0].set_ylabel("Mean interval width (H units)")
    handles, labels = axes[0, 2].get_legend_handles_labels()
    fig.legend(
        handles, labels, loc="lower center", ncol=3, frameon=False, bbox_to_anchor=(0.5, 0.045)
    )
    fig.suptitle(
        "Interval candidates: first development comparison",
        x=0.05,
        ha="left",
        fontsize=18,
        weight="bold",
    )
    fig.text(
        0.05,
        0.925,
        "n=512 | 64 independent records/cell | 199 draws/pool | bars: Wilson 95% Monte Carlo intervals",
        fontsize=10,
    )
    fig.text(
        0.05,
        0.018,
        "Dashed: nominal 95% coverage. Vertical divider: fitted-model domain / model-mismatch controls. No confirmation claim.",
        fontsize=9,
    )
    fig.subplots_adjust(left=0.06, right=0.985, top=0.88, bottom=0.17, hspace=0.12, wspace=0.12)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(args.output, dpi=170, facecolor="white")
    plt.close(fig)


if __name__ == "__main__":
    main()
