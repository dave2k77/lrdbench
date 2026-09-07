"""Plot the explicit coverage/denominator/Wilson fields from a development pilot."""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.ticker import PercentFormatter


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    data = pd.read_csv(args.directory / "coverage_summary.csv")
    fig, axes = plt.subplots(2, 3, figsize=(11, 6), sharey=True, sharex=True)
    for row, case in enumerate(("fGn050", "fGn075")):
        for col, method in enumerate(("GPH", "Higuchi", "GHE")):
            ax = axes[row, col]
            subset = data[(data.case == case) & (data.method == method)].sort_values("block_length")
            x = np.arange(len(subset))
            ax.axhline(0.95, color="0.45", linestyle="--", label="Nominal 95%")
            ax.errorbar(
                x,
                subset.coverage,
                yerr=[
                    subset.coverage - subset.coverage_wilson_low,
                    subset.coverage_wilson_high - subset.coverage,
                ],
                fmt="o",
                capsize=4,
                color="#136f89",
            )
            for i, entry in enumerate(subset.itertuples()):
                ax.annotate(
                    f"{entry.n_covered}/{entry.n_available}",
                    (i, entry.coverage_wilson_high),
                    xytext=(0, 5),
                    textcoords="offset points",
                    ha="center",
                    fontsize=9,
                )
            ax.set_xticks(x, subset.block_length)
            ax.set_ylim(0.5, 1.065)
            ax.set_xlim(-0.45, 2.45)
            ax.yaxis.set_major_formatter(PercentFormatter(1))
            ax.grid(axis="y", alpha=0.2)
            if row == 0:
                ax.set_title("GHE (q = 1)" if method == "GHE" else method)
            else:
                ax.set_xlabel("Bootstrap block length")
            if col == 0:
                ax.set_ylabel(f"H = {0.5 if row == 0 else 0.75}\nCoverage")
    fig.suptitle(
        "Development pilot: n = 512, 64 independent records per H, 199 draws per fit",
        fontsize=12,
    )
    fig.text(
        0.5,
        0.01,
        "Dashed: nominal 95%. Whiskers: 95% Wilson intervals for Monte Carlo coverage. All 64 intervals available in each cell.",
        ha="center",
        fontsize=9,
    )
    fig.tight_layout(rect=(0, 0.04, 1, 0.96))
    fig.savefig(args.directory / "coverage_by_block.png", dpi=160)
    plt.close(fig)


if __name__ == "__main__":
    main()
