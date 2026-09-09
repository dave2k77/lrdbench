"""Per-domain descriptive error-inflation figures from the canonical paired export."""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import TwoSlopeNorm

LABELS = {
    "constant_offset_1sd": "Constant\noffset",
    "midpoint_step_1sd": "Midpoint\nstep",
    "additive_outliers_1pct_8sd": "Additive\noutliers",
    "linear_trend_0p5sd": "Linear\ntrend",
    "linear_plus_quadratic_0p5sd": "Linear +\nquadratic",
    "t3_realized_sd_0p5": "t(3) noise\nsample SD",
    "t5_realized_sd_0p5": "t(5) noise\nsample SD",
}


def run(output):
    frame = pd.read_csv(output / "paired_summary.csv")
    frame = frame[frame.metric == "absolute_error_inflation"]
    limit = max(0.1, float(np.ceil(frame.value.abs().max() * 10) / 10))
    for domain in ("fGn", "ARFIMA", "AR1"):
        matrix = frame[frame.domain == domain].pivot(
            index="method", columns="condition", values="value"
        )
        matrix = matrix[list(LABELS)]
        fig, ax = plt.subplots(figsize=(10.5, 10.5))
        im = ax.imshow(
            matrix.to_numpy(),
            cmap="RdBu_r",
            norm=TwoSlopeNorm(vmin=-limit, vcenter=0, vmax=limit),
            aspect="auto",
        )
        ax.set_xticks(np.arange(len(matrix.columns)), list(LABELS.values()), fontsize=10)
        ax.xaxis.tick_top()
        ax.tick_params(axis="both", length=0, pad=7)
        names = [
            s.replace("::", " / ").replace("ModifiedLocalWhittle", "Local Whittle¹")
            for s in matrix.index
        ]
        ax.set_yticks(np.arange(len(matrix)), names, fontsize=10)
        for i, row in enumerate(matrix.to_numpy()):
            for j, value in enumerate(row):
                label = (
                    "NA"
                    if not np.isfinite(value)
                    else f"{value:+.2f}"
                    if abs(value) >= 0.005
                    else "0.00"
                )
                ax.text(
                    j,
                    i,
                    label,
                    ha="center",
                    va="center",
                    fontsize=9,
                    color="white" if np.isfinite(value) and abs(value) > 0.6 * limit else "#182430",
                )
        ax.set_xticks(np.arange(-0.5, len(matrix.columns), 1), minor=True)
        ax.set_yticks(np.arange(-0.5, len(matrix), 1), minor=True)
        ax.grid(which="minor", color="white", linewidth=1)
        ax.tick_params(which="minor", bottom=False, left=False)
        for spine in ax.spines.values():
            spine.set_visible(False)
        bar = fig.colorbar(im, ax=ax, location="bottom", shrink=0.8, pad=0.035, aspect=30)
        bar.set_label("Change in absolute error against latent clean H (H units)", fontsize=10)
        fig.suptitle(
            f"{domain}: paired contamination effects",
            x=0.54,
            y=0.965,
            fontsize=17,
            fontweight="bold",
        )
        sub = {
            "fGn": "H = 0.25, 0.50, 0.75, 0.85 · 256 independent parents",
            "ARFIMA": "d = 0.25 · 64 independent parents",
            "AR1": "φ = 0.80, 0.95 · 128 independent parents",
        }[domain]
        fig.text(
            0.54,
            0.929,
            f"{sub}\nn = 512 · 64 parents per cell · equal cell weights",
            ha="center",
            va="top",
            fontsize=10,
            linespacing=1.6,
        )
        fig.text(
            0.035,
            0.025,
            "Development screen; common complete parents across the declared methods and conditions.\n"
            "Positive values mean greater error; negative values mean lower error in this design.\n"
            "¹ Repository identifier: ModifiedLocalWhittle. Summary intervals and counts are in the accompanying CSV.\n"
            "Noise uses realized sample-SD scaling. No within-record H intervals or EEG claims are evaluated.",
            fontsize=9,
            linespacing=1.5,
        )
        fig.subplots_adjust(left=0.32, right=0.975, top=0.84, bottom=0.14)
        fig.savefig(output / f"stress_{domain}.png", dpi=180, facecolor="white")
        plt.close(fig)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    run(parser.parse_args().output.resolve())
