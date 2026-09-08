"""Build manuscript evidence, tables and publication figures from audited exports.

Run with the locked scientific Python environment. No producer module is imported.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import TwoSlopeNorm

HERE = Path(__file__).resolve().parent
RESULTS = HERE.parent / "remediation/confirmation_audit/results"
RUN = "43d0a7f75c8afab6d32ab6fd1f2ff8db49cca59e36971e2b74404173f4cbfcf2"
PROVENANCE = json.loads((RESULTS / "export_provenance.json").read_text(encoding="utf-8"))
DATA = {}
for name in [
    "accuracy_cells",
    "accuracy_domains",
    "stress_domains",
    "intervals_cells",
    "planned_contrasts",
]:
    filename = name + ".csv.gz"
    assert (
        hashlib.sha256((RESULTS / filename).read_bytes()).hexdigest()
        == PROVENANCE["files"][filename]
    ), filename
    frame = pd.read_csv(RESULTS / filename, keep_default_na=False)
    for col in ["value", "ci_low", "ci_high", "n", "H_target", "parameter"]:
        frame[col] = pd.to_numeric(frame[col], errors="coerce")
    assert set(frame.run_identity_sha256) == {RUN}
    DATA[name] = frame

METHODS = {
    "RS": "R/S",
    "AbsoluteMoment": "Absolute moment",
    "Variance": "Variance",
    "VarianceResidual": "Residual variance",
    "DFA::short_scales": "DFA short",
    "DFA::balanced_scales": "DFA balanced",
    "DFA::long_scales": "DFA long",
    "DMA::short_windows": "DMA short",
    "DMA::balanced_windows": "DMA balanced",
    "DMA::long_windows": "DMA long",
    "GPH::narrow_band": "GPH m32",
    "GPH::wider_band": "GPH m64",
    "WhittleMLE": "ARFIMA-shape Whittle",
    "ModifiedLocalWhittle": "Local Whittle",
    "WaveletOLS::broad_band": "Wavelet db2 broad",
    "WaveletOLS::upper_band": "Wavelet db2 reduced",
    "WaveletOLS::conservative_band": "Wavelet db4 conservative",
    "Higuchi": "Higuchi raw",
    "Higuchi::centered": "Higuchi centered",
    "GHE": "GHE raw",
    "GHE::centered": "GHE centered",
}
actual = set(DATA["accuracy_domains"].query("metric == 'mae'").method)
assert set(METHODS) == actual, (set(METHODS) - actual, actual - set(METHODS))
EVIDENCE = []
TOKENS = {}


def row(table, **filters):
    frame = DATA[table]
    mask = np.ones(len(frame), dtype=bool)
    for k, v in filters.items():
        mask &= frame[k].to_numpy() == v
    found = frame.loc[mask]
    assert len(found) == 1, (table, filters, len(found))
    return found.iloc[0]


def record(key, table, r, transformation, formatted):
    item = r.to_dict()
    item.update(
        evidence_id=key,
        source_file=table + ".csv.gz",
        transformation=transformation,
        formatted=formatted,
    )
    EVIDENCE.append(item)


def number(key, table, *, digits=3, percent=False, ci=False, signed=False, offset=0.0, **filters):
    r = row(table, **filters)
    scale = 100 if percent else 1
    fmt = f"{{:{'+' if signed else ''}.{digits}f}}"
    value = (r.value + offset) * scale
    result = fmt.format(value)
    if ci:
        result += f" [{fmt.format((r.ci_low + offset) * scale)}, {fmt.format((r.ci_high + offset) * scale)}]"
    TOKENS[key] = result
    record(key, table, r, f"(value + {offset}) * {scale}; {digits} decimals; CI={ci}", result)
    return result


aliases = {
    "hg": "Higuchi",
    "ghe": "GHE",
    "hgc": "Higuchi::centered",
    "ghec": "GHE::centered",
    "dfa_short": "DFA::short_scales",
    "dfa_long": "DFA::long_scales",
    "dma_long": "DMA::long_windows",
    "gph32": "GPH::narrow_band",
    "gph64": "GPH::wider_band",
}
for prefix, method in aliases.items():
    for short, domain in {"fg": "fGn", "fima": "ARFIMA", "ar": "AR1"}.items():
        for with_ci in [False, True]:
            number(
                f"{prefix}_{short}_mae" + ("_ci" if with_ci else ""),
                "accuracy_domains",
                method=method,
                domain=domain,
                metric="mae",
                condition="clean",
                ci=with_ci,
                digits=4 if with_ci else 3,
            )
for short, h in [("h25", 0.25), ("h85", 0.85)]:
    for prefix, method in [("hg", "Higuchi"), ("ghe", "GHE")]:
        number(
            f"{prefix}_{short}_mean",
            "accuracy_cells",
            method=method,
            cell=f"fGn_{h}_n512",
            metric="bias",
            condition="clean",
            offset=h,
        )
for prefix, method in [("hg", "Higuchi"), ("ghe", "GHE")]:
    for short, domain in [("fg", "fGn"), ("ar", "AR1")]:
        number(
            f"{prefix}_center_{short}_delta",
            "accuracy_domains",
            method=method,
            domain=domain,
            metric="mae_difference",
            contrast="geometric_mean_removal_clean",
            ci=True,
            signed=True,
            digits=4,
        )
for prefix, method in [("dfa", "DFA::short_scales"), ("hg", "Higuchi"), ("ghe", "GHE")]:
    number(
        f"{prefix}_ar_bias",
        "accuracy_domains",
        method=method,
        domain="AR1",
        metric="bias",
        condition="clean",
        ci=True,
        digits=4,
        signed=True,
    )
number(
    "dfa_ar095_outside",
    "accuracy_cells",
    method="DFA::short_scales",
    cell="AR1_0.95_n512",
    metric="outside_0_1",
    condition="clean",
    percent=True,
    ci=True,
    digits=2,
)

CONDS = {}
CONDS["O"] = ("constant_offset__shift_1", "Offset 1 SD")
for i, (p, a) in enumerate([(p, a) for p in [0.25, 0.5, 0.75] for a in [0.5, 1, 2]], 1):
    CONDS[f"S{i}"] = (f"step_change__position_{p:g}__shift_{a:g}", f"Step p={p:g}, a={a:g}")
for i, q in enumerate([0.005, 0.01, 0.05], 1):
    CONDS[f"I{i}"] = (f"outliers__amplitude_8__rate_{q:g}", f"Impulses {100 * q:g}%, 8 SD")
for i, (p, a) in enumerate([(p, a) for p in [1, 2] for a in [0.25, 0.5, 1]], 1):
    CONDS[f"P{i}"] = (f"polynomial_trend__order_{p}__strength_{a:g}", f"Trend order {p}, a={a:g}")
for i, (df, a) in enumerate([(df, a) for df in [3, 5] for a in [0.5, 1]], 1):
    CONDS[f"T{i}"] = (f"heavy_tail_noise__df_{df}__scale_{a:g}", f"t noise df={df}, a={a:g}")
assert len(CONDS) == 23
stress_choices = {"offset": "O", "step": "S6", "poly": "P6", "outlier": "I3", "t": "T2"}
for prefix, method in [
    ("hg", "Higuchi"),
    ("ghe", "GHE"),
    ("hgc", "Higuchi::centered"),
    ("ghec", "GHE::centered"),
    ("dfa", "DFA::short_scales"),
    ("gph", "GPH::narrow_band"),
]:
    for kind, code in stress_choices.items():
        number(
            f"{prefix}_{kind}_delta",
            "stress_domains",
            domain="fGn",
            method=method,
            condition=CONDS[code][0],
            metric="absolute_error_inflation",
            ci=kind in ["offset", "step"],
        )
    if prefix in ["hgc", "ghec"]:
        number(
            f"{prefix}_step_drift",
            "stress_domains",
            domain="fGn",
            method=method,
            condition=CONDS["S6"][0],
            metric="absolute_estimate_drift",
        )

CANDIDATES = {
    "cbc_raw_percentile": "Block raw percentile",
    "cbc_raw_basic": "Block raw basic",
    "cbc_centered_percentile": "Block centered percentile",
    "cbc_centered_basic": "Block centered basic",
    "unknown_fgn_centered_basic": "Fitted fGn centered basic",
    "gph_normal_raw": "Normal raw",
}
cov_alias = {
    "raw_pct": "cbc_raw_percentile",
    "cbc_pct": "cbc_centered_percentile",
    "cbc_basic": "cbc_centered_basic",
    "model": "unknown_fgn_centered_basic",
}
for prefix, method in [("hg", "Higuchi"), ("ghe", "GHE")]:
    for short, candidate in cov_alias.items():
        for ci in [False, True]:
            number(
                f"{prefix}_{short}_cov" + ("_ci" if ci else ""),
                "intervals_cells",
                cell="fGn_0.85_n512",
                method=method,
                condition=candidate,
                metric="unconditional_coverage",
                percent=True,
                ci=ci,
                digits=2,
            )
    for short, candidate in [
        ("cbc", "cbc_centered_basic"),
        ("model", "unknown_fgn_centered_basic"),
    ]:
        number(
            f"{prefix}_{short}_width",
            "intervals_cells",
            cell="fGn_0.85_n512",
            method=method,
            condition=candidate,
            metric="mean_width",
        )
    number(
        f"{prefix}_model_cov_delta",
        "intervals_cells",
        cell="fGn_0.85_n512",
        method=method,
        metric="coverage_difference",
        contrast="interval_model",
        ci=True,
        percent=True,
        digits=2,
    )
    for short, candidate in [
        ("pct", "cbc_centered_percentile"),
        ("model", "unknown_fgn_centered_basic"),
    ]:
        number(
            f"{prefix}_1024_{short}_cov",
            "intervals_cells",
            cell="fGn_0.85_n1024",
            method=method,
            condition=candidate,
            metric="unconditional_coverage",
            percent=True,
            digits=2,
        )
for short, cand in [
    ("pct", "cbc_raw_percentile"),
    ("basic", "cbc_raw_basic"),
    ("model", "unknown_fgn_centered_basic"),
    ("normal", "gph_normal_raw"),
]:
    number(
        f"gph_{short}_cov",
        "intervals_cells",
        cell="fGn_0.85_n512",
        method="GPH::narrow_band",
        condition=cand,
        metric="unconditional_coverage",
        percent=True,
        digits=2,
    )
    if short != "pct":
        number(
            f"gph_{'cbc' if short == 'basic' else short}_width",
            "intervals_cells",
            cell="fGn_0.85_n512",
            method="GPH::narrow_band",
            condition=cand,
            metric="mean_width",
        )
for short, cell in [
    ("ar08", "AR1_0.8_n512"),
    ("ar095", "AR1_0.95_n512"),
    ("1024", "fGn_0.85_n1024"),
]:
    for kind, cand in [("model", "unknown_fgn_centered_basic"), ("normal", "gph_normal_raw")]:
        key = f"gph_{short}_{kind}_cov" if short == "1024" else f"gph_{kind}_{short}_cov"
        number(
            key,
            "intervals_cells",
            cell=cell,
            method="GPH::narrow_band",
            condition=cand,
            metric="unconditional_coverage",
            percent=True,
            digits=2,
        )

TABLES = {}
TABLES["design"] = {
    "caption": "Table 1 Experimental design and units of replication",
    "headers": ["Component", "Design", "Independent parents", "Evaluations"],
    "widths": [0.9, 2.8, 1.1, 1.2],
    "rows": [
        [
            "Clean accuracy",
            "11 settings × 3 lengths (512, 1024, 2048) × 2,000 repetitions; 21 pipelines",
            "66,000",
            "1,386,000 fits",
        ],
        [
            "Contamination",
            "7 settings × 2 lengths (512, 1024) × 500 repetitions; 23 separate descendants; 21 pipelines",
            "7,000\nSubset of clean",
            "161,000 descendants; 3,381,000 fits",
        ],
        [
            "Intervals core",
            "7 settings × n=512 × 2,000 repetitions; 16 candidates",
            "14,000\nSubset of clean",
            "224,000 intervals",
        ],
        [
            "Intervals sensitivity",
            "3 settings × n=1024 × 500 repetitions; 16 candidates",
            "1,500\nSubset of clean",
            "24,000 intervals",
        ],
        [
            "Within-record resampling",
            "1,999 circular-block and 1,999 fitted-fGn draws for each of 15,500 parents",
            "No additional independent parents",
            "61,969,000 resampled records",
        ],
        [
            "Summary uncertainty",
            "1,999 resamples of parents within each fixed cell, preserving method and condition pairing",
            "Uses declared parent counts",
            "Pointwise Monte Carlo intervals",
        ],
    ],
    "note": "The seven-setting subset comprises all four fGn H values, ARFIMA d=0.25 and AR(1) φ=0.8 and 0.95. The three sensitivity settings are fGn H=0.50 and 0.85 and AR(1) φ=0.95. Bootstrap draws and contaminated descendants are not independent repetitions. Each physical resampling pool is reused across multiple statistics. Counts follow the frozen protocol and audited accounting.",
}

TABLES["clean"] = {
    "caption": "Table 2 Clean domain mean absolute error",
    "headers": ["Pipeline", "fGn", "ARFIMA", "AR(1)"],
    "widths": [2.05, 1.32, 1.32, 1.31],
    "rows": [],
    "font": 8.5,
    "note": "Entries are MAE [95% Monte Carlo interval] in H units. Domains give equal weight to 12 fGn, 9 ARFIMA and 12 AR(1) process–length cells, each with 2,000 parents. Intervals resample parents within cells jointly across pipelines, with 1,999 draws. Domains and configurations are not ranked. Raw and centered refer to the increments before cumulative-path construction.",
}
for m, label in METHODS.items():
    vals = [
        number(
            f"T2_{m}_{d}",
            "accuracy_domains",
            method=m,
            domain=d,
            condition="clean",
            metric="mae",
            ci=True,
            digits=4,
        )
        for d in ["fGn", "ARFIMA", "AR1"]
    ]
    TABLES["clean"]["rows"].append([label] + vals)

TABLES["stress"] = {
    "caption": "Table 3 Illustrative paired contamination effects on fractional Gaussian noise",
    "headers": ["Condition", "DFA short", "GPH m32", "Higuchi raw", "GHE raw"],
    "widths": [1.55, 1.12, 1.12, 1.12, 1.09],
    "rows": [],
    "font": 8.5,
    "note": "Entries are changes in MAE [95% Monte Carlo interval], relative to the same clean parents, in H units. Equal weights cover eight fGn cells (four H values × two lengths), each with 500 parents. The rows illustrate different operators; they are not a new inferential selection or ranking. All 23 conditions and 21 pipelines are shown separately by domain in Figures S1–S3 and the complete machine-readable exports. Drift measures are distinct from these changes in error. SD is the parent standard deviation.",
}
for code in ["O", "S6", "I3", "P3", "P6", "T2", "T4"]:
    cond, label = CONDS[code]
    vals = [
        number(
            f"T3_{code}_{m}",
            "stress_domains",
            domain="fGn",
            method=m,
            condition=cond,
            metric="absolute_error_inflation",
            ci=True,
        )
        for m in ["DFA::short_scales", "GPH::narrow_band", "Higuchi", "GHE"]
    ]
    TABLES["stress"]["rows"].append([label] + vals)

TABLES["coverage"] = {
    "caption": "Table 4 Coverage and width at fGn H of 0.85 and n of 512",
    "headers": ["Statistic", "Interval", "Coverage % [95% interval]", "Mean width [95% interval]"],
    "widths": [0.70, 2.25, 1.55, 1.5],
    "rows": [],
    "font": 8.5,
    "note": "There were 2,000 parent records and all intervals were available. Coverage intervals are Wilson 95% Monte Carlo intervals; width intervals use paired parent resampling. Width is in H units. Block denotes the circular block bootstrap with block length 32 and 1,999 draws. Fitted fGn uses unknown-mean Gaussian profile likelihood and centered basic endpoints. Every nominal interval is 95%. The displayed uncertainty describes the benchmark summary, not the interval for a new individual record.",
}
interval_pairs = []
for m in ["GPH::narrow_band", "Higuchi", "GHE"]:
    for cond, label in CANDIDATES.items():
        if cond == "gph_normal_raw" and m != "GPH::narrow_band":
            continue
        interval_pairs.append((m, cond))
        cov = number(
            f"T4_cov_{m}_{cond}",
            "intervals_cells",
            cell="fGn_0.85_n512",
            method=m,
            condition=cond,
            metric="unconditional_coverage",
            percent=True,
            ci=True,
            digits=2,
        )
        width = number(
            f"T4_width_{m}_{cond}",
            "intervals_cells",
            cell="fGn_0.85_n512",
            method=m,
            condition=cond,
            metric="mean_width",
            ci=True,
        )
        TABLES["coverage"]["rows"].append(["GPH m32" if "GPH" in m else m, label, cov, width])

settings = pd.read_csv(
    HERE.parent / "remediation/protocol-v1/method_settings.csv", keep_default_na=False
)
TABLES["methods"] = {
    "caption": "Table S1 Evaluated pipelines and exact settings",
    "headers": ["Manuscript name and repository identifier", "Definition and configuration"],
    "widths": [2.10, 3.90],
    "rows": [],
    "font": 9,
    "note": "All inputs are increments. For both geometric statistics the cumulative path includes the initial zero. The centered variant removes the arithmetic increment mean before integration. All point bootstraps are disabled. The accompanying method_settings.csv preserves all 63 pipeline–length configurations verbatim, including base identifiers and expanded frequency and wavelet bands. No method was retuned using confirmation outcomes.",
}
definitions = {
    "RS": "Mean rescaled range of forward disjoint blocks; no Anis–Lloyd correction. Scales start at 8, end at floor(n/2), rounded ×1.5. Population SD within blocks; log–log OLS slope is H.",
    "AbsoluteMoment": "First centered absolute moment of nonoverlapping block means. Scales 8 to 256, rounded ×1.5. H=1+slope.",
    "Variance": "Sample variance (divisor number of blocks minus one) of nonoverlapping block means. Scales 8 to 256, rounded ×1.5. H=1+slope/2.",
    "VarianceResidual": "Linearly detrended variance of the demeaned cumulative profile within forward disjoint blocks, averaged across blocks. Scales 8 to 256, rounded ×1.5. H=slope/2.",
    "WhittleMLE": "Band-limited ARFIMA-shape Whittle, m=64, λj=2πj/n. Shape |2sin(λj/2)|^(−2d), profiled scale mean(Ij/shape). Minimize mean(log fitted spectrum + Ij/fitted spectrum), d∈[−0.49,0.49]; H=d+0.5. No taper.",
    "ModifiedLocalWhittle": "Ordinary Gaussian local Whittle, m=64. Minimize log(mean(λj^(2d)Ij))−2d mean(log λj), d∈[−0.49,0.49]; H=d+0.5. No taper or extra modification.",
}
for m, label in METHODS.items():
    if m in definitions:
        desc = definitions[m]
    elif m.startswith(("DFA", "DMA")):
        p = json.loads(settings[(settings.method == m) & (settings.n == 512)].iloc[0]["params"])
        desc = (
            (
                "Linear DFA of demeaned profile; forward disjoint segments, RMS residuals."
                if m.startswith("DFA")
                else "Backward moving average of demeaned profile; RMS over every valid residual."
            )
            + f" Scale bounds [{p['min_scale']},{p['max_scale']}], rounded ×1.25, at every n. Log–log OLS slope is H."
        )
    elif m.startswith("GPH"):
        count = 32 if "narrow" in m else 64
        desc = f"Untapered log-periodogram OLS at j=1,…,{count}. Regressor log[4sin²(πj/n)], H=0.5−slope. Frequency band 1/n to {count}/n cycles/sample."
    elif m.startswith("Wavelet"):
        rows = settings[settings.method == m]
        p = json.loads(rows.iloc[0]["params"])
        bands = "; ".join(f"n={int(r.n)}: {r.retained_wavelet_levels}" for r in rows.itertuples())
        desc = f"{p['wavelet']}, symmetric boundary extension, unweighted OLS of log₂ sample detail variance versus octave. H=(slope+1)/2. Retained octaves {bands}."
    elif m.startswith("Higuchi"):
        desc = "Cumulative path; k=1,…,32. With path length N and J=floor((N−1−m)/k), each subsequence length is sum|X(m+ik)−X(m+(i−1)k)| × (N−1)/(Jk²), then averaged over offsets m. H=2−slope(log length versus log(1/k))."
        if "centered" in m:
            desc = "Subtract increment mean first. " + desc
    else:
        desc = "q=1 absolute moments of cumulative-path increments; unweighted log–log OLS slope. 18 geometric candidate lags, rounded and deduplicated, from 1 to floor((n+1)/8), i.e. maxima 64, 128, 256. No slope substitution."
        if "centered" in m:
            desc = "Subtract increment mean first. " + desc
    TABLES["methods"]["rows"].append([label + "\n" + m, desc])
settings.to_csv(HERE / "tables/method_settings.csv", index=False, lineterminator="\n")
pd.DataFrame(
    [(k, *v) for k, v in CONDS.items()], columns=["code", "condition", "description"]
).to_csv(HERE / "tables/condition_key.csv", index=False, lineterminator="\n")
for key, table in TABLES.items():
    pd.DataFrame(table["rows"], columns=table["headers"]).to_csv(
        HERE / f"tables/{key}.csv", index=False, lineterminator="\n"
    )

plt.rcParams.update(
    {
        "font.family": "DejaVu Sans",
        "font.size": 9,
        "axes.titlesize": 11,
        "svg.fonttype": "none",
        "savefig.dpi": 230,
    }
)
FIGURES = {}


def save(fig, key, caption, note):
    for suffix in ["png", "svg"]:
        fig.savefig(
            HERE / f"figures/{key}.{suffix}",
            facecolor="white",
            metadata={"Date": None} if suffix == "svg" else {},
        )
    plt.close(fig)
    FIGURES[key] = {"path": f"figures/{key}.png", "caption": caption, "note": note}


def plot_source(key, table, subset):
    subset.to_csv(HERE / f"tables/figure_{key}_source.csv", index=False, lineterminator="\n")
    for _, r in subset.iterrows():
        record("Figure_" + key, table, r, "unchanged (coverage ×100 in figure)", "")


# Figure 1 keeps all cells, ordered by parameter then length within each domain.
fig, axes = plt.subplots(
    1, 3, figsize=(11.5, 6.4), gridspec_kw={"width_ratios": [12, 9, 12]}, sharey=True
)
clean_max = np.ceil(DATA["accuracy_cells"].query("metric=='mae'").value.max() * 10) / 10
for ax, domain in zip(axes, ["fGn", "ARFIMA", "AR1"], strict=False):
    s = DATA["accuracy_cells"].query("metric=='mae' and condition=='clean' and domain==@domain")
    cells = s[["cell", "parameter", "n"]].drop_duplicates().sort_values(["parameter", "n"])
    a = (
        s.pivot(index="method", columns="cell", values="value")
        .loc[list(METHODS), cells.cell]
        .to_numpy()
    )
    im = ax.imshow(a, aspect="auto", vmin=0, vmax=clean_max, cmap="viridis_r")
    ax.set_title({"fGn": "fGn   H", "ARFIMA": "ARFIMA   d", "AR1": "AR(1)   φ"}[domain])
    ax.set_xticks(
        range(len(cells)),
        [f"{r.parameter:g} / {int(r.n)}" for r in cells.itertuples()],
        fontsize=8,
        rotation=90,
    )
    ax.set_yticks(range(21), list(METHODS.values()), fontsize=8.5)
    for k in range(3, len(cells), 3):
        ax.axvline(k - 0.5, color="white", lw=1)
    plot_source("clean_" + domain, "accuracy_cells", s)
fig.subplots_adjust(left=0.205, right=0.93, bottom=0.19, top=0.93, wspace=0.08)
cax = fig.add_axes([0.945, 0.20, 0.015, 0.65])
fig.colorbar(im, cax=cax, label="Mean absolute error")
save(
    fig,
    "clean",
    "Figure 1 Clean accuracy across every process and record length",
    f"Each tile is MAE from 2,000 independent parents. Column labels give generating parameter / record length. All panels share the color scale (0 to {clean_max:g}), spanning every observed value without clipping. Rows retain all 21 declared pipelines. Table 2 gives domain means and their Monte Carlo intervals; complete cell values and uncertainty accompany the figure.",
)

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
labels = [
    "fGn .25",
    "fGn .50",
    "fGn .75",
    "fGn .85",
    "ARFIMA .25",
    "AR(1) .8",
    "AR(1) .95",
    "fGn .50",
    "fGn .85",
    "AR(1) .95",
]
fig, ax = plt.subplots(figsize=(11.5, 6.3))
arr = np.array(
    [
        [
            row(
                "intervals_cells", cell=c, method=m, condition=cond, metric="unconditional_coverage"
            ).value
            * 100
            for c in cells
        ]
        for m, cond in interval_pairs
    ]
)
im = ax.imshow(arr, aspect="auto", vmin=0, vmax=100, cmap="viridis")
ax.set_xticks(
    range(10),
    [label + "\n" + ("512" if j < 7 else "1024") for j, label in enumerate(labels)],
    fontsize=8.5,
)
ax.set_yticks(
    range(16),
    [
        ("GPH m32" if "GPH" in m else m)
        + " | "
        + CANDIDATES[c].replace("Block ", "CBC ").replace("Fitted fGn ", "fGn ")
        for m, c in interval_pairs
    ],
    fontsize=8.2,
)
for (i, j), value in np.ndenumerate(arr):
    ax.text(
        j,
        i,
        f"{value:.2f}",
        ha="center",
        va="center",
        color="white" if value < 55 else "#151515",
        fontsize=8,
    )
ax.axvline(6.5, color="white", lw=2.5)
for y in [5.5, 10.5]:
    ax.axhline(y, color="white", lw=1.5)
ax.set_title("Core: n=512, R=2,000                              Sensitivity: n=1024, R=500", pad=12)
fig.subplots_adjust(left=0.34, right=0.94, bottom=0.13, top=0.91)
cax = fig.add_axes([0.954, 0.18, 0.014, 0.64])
fig.colorbar(im, cax=cax, label="Coverage (%)")
plot_source(
    "coverage", "intervals_cells", DATA["intervals_cells"].query("metric=='unconditional_coverage'")
)
save(
    fig,
    "coverage",
    "Figure 2 Coverage of all interval candidates",
    "Entries are percentages; all intervals were available. Nominal coverage is 95%. Each column identifies the generating model parameter and n, with ARFIMA values denoting d and AR(1) values denoting φ. CBC is circular block resampling. The vertical line separates the core and sensitivity designs. Values are rounded to two decimals for display; Table 4 and the machine-readable tables also provide Wilson intervals. Zero observed coverage has a nonzero upper confidence bound.",
)

all_stress = DATA["stress_domains"].query("metric=='absolute_error_inflation'")
vmin = min(-0.05, float(all_stress.value.min()))
vmax = max(0.7, float(all_stress.value.max()))
vmin = np.floor(vmin * 10) / 10
vmax = np.ceil(vmax * 10) / 10
for idx, domain in enumerate(["fGn", "ARFIMA", "AR1"], 1):
    s = all_stress[all_stress.domain == domain]
    a = (
        s.pivot(index="method", columns="condition", values="value")
        .loc[list(METHODS), [v[0] for v in CONDS.values()]]
        .to_numpy()
    )
    fig, ax = plt.subplots(figsize=(11.5, 6.15))
    im = ax.imshow(a, aspect="auto", cmap="RdBu_r", norm=TwoSlopeNorm(0, vmin=vmin, vmax=vmax))
    ax.set_xticks(range(23), list(CONDS), fontsize=9)
    ax.set_yticks(range(21), list(METHODS.values()), fontsize=8.5)
    ax.set_title(
        f"{domain if domain != 'AR1' else 'AR(1)'}   Change in MAE relative to the paired clean record"
    )
    for x in [0.5, 9.5, 12.5, 18.5]:
        ax.axvline(x, color="black", lw=0.7)
    fig.subplots_adjust(left=0.205, right=0.935, bottom=0.09, top=0.92)
    cax = fig.add_axes([0.95, 0.16, 0.014, 0.68])
    fig.colorbar(im, cax=cax, label="Change in MAE")
    plot_source("stress_" + domain, "stress_domains", s)
    save(
        fig,
        "stress_" + domain,
        f"Figure S{idx} Complete contamination profile for {domain if domain != 'AR1' else 'AR(1)'}",
        "Equal cell weights; 500 paired parents per cell. Red indicates increased MAE and blue decreased MAE; white is zero. All three panels use the same color scale. O: offset 1 SD. S1–S9: step positions .25, .50, .75, with amplitudes .5, 1, 2 within each position. I1–I3: impulses at .5%, 1%, 5% of samples, amplitude 8 SD. P1–P6: orders 1, 2 with strengths .25, .5, 1 within each order. T1–T4: Student-t df 3, 5 with strengths .5, 1 within each df. Order two is the centered sum t+t². Negative error change is not evidence of decontamination. Exact values, uncertainty and drift are supplied in the source tables.",
    )

template = (HERE / "manuscript.template.md").read_text(encoding="utf-8")
used = set(re.findall(r"\{\{(\w+)\}\}", template))
assert used <= TOKENS.keys(), used - TOKENS.keys()
manuscript = re.sub(r"\{\{(\w+)\}\}", lambda m: TOKENS[m[1]], template)
(HERE / "manuscript.md").write_text(manuscript, encoding="utf-8", newline="\n")
(HERE / "document_data.json").write_text(
    json.dumps({"tables": TABLES, "figures": FIGURES}, ensure_ascii=False, indent=2),
    encoding="utf-8",
    newline="\n",
)
pd.DataFrame(EVIDENCE).to_csv(HERE / "tables/evidence_map.csv", index=False, lineterminator="\n")
(HERE / "build_evidence.json").write_text(
    json.dumps(
        {
            "run_identity": RUN,
            "canonical_summary_sha256": PROVENANCE["canonical_summary_sha256"],
            "verified_input_files": {
                n + ".csv.gz": PROVENANCE["files"][n + ".csv.gz"] for n in DATA
            },
            "narrative_tokens_used": sorted(used),
            "evidence_rows": len(EVIDENCE),
            "all_methods": len(METHODS),
            "all_conditions": len(CONDS),
            "interval_cells": len(cells),
            "interval_candidates": len(interval_pairs),
            "source_row_counts": {n: len(f) for n, f in DATA.items()},
            "body_words_before_references": len(manuscript.split("## References")[0].split()),
        },
        indent=2,
    ),
    encoding="utf-8",
    newline="\n",
)
print(
    json.dumps(
        {
            "status": "built",
            "narrative_values": len(used),
            "evidence_rows": len(EVIDENCE),
            "tables": len(TABLES),
            "figures": len(FIGURES),
        }
    )
)
