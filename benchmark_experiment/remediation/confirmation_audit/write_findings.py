"""Generate auditable prose and a draft-claim ledger from the verified run."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd
from audit import RUN


def main(source, output):
    audit = json.loads((output / "audit_evidence.json").read_text(encoding="utf-8"))
    if audit["status"] != "passed":
        raise ValueError("Passing independent audit required")
    frame = pd.read_csv(
        source / "summaries/canonical_summary.csv",
        keep_default_na=False,
        float_precision="round_trip",
        low_memory=False,
    )
    for key in ["value", "ci_low", "ci_high", "mcse", "n", "parameter", "H_target"]:
        frame[key] = frame[key].map(lambda v: float(v) if v != "" else float("nan"))
    narrative = []

    def select(scope, cell, method, metric, condition="clean", domain=None, contrast=""):
        mask = (
            frame.scope.eq(scope)
            & frame.cell.eq(cell)
            & frame.method.eq(method)
            & frame.metric.eq(metric)
            & frame.condition.eq(condition)
            & frame.contrast.eq(contrast)
        )
        if domain:
            mask &= frame.domain.eq(domain)
        rows = frame[mask]
        if len(rows) != 1:
            raise ValueError(
                f"Ambiguous narrative key: {scope}/{cell}/{method}/{metric}/{condition}"
            )
        row = rows.iloc[0]
        narrative.append(row.to_dict())
        return row

    def fmt(row, percent=False):
        value, lo, hi = row[["value", "ci_low", "ci_high"]]
        if percent:
            return f"{value * 100:.2f}% [{lo * 100:.2f}, {hi * 100:.2f}]"
        return f"{value:.4f} [{lo:.4f}, {hi:.4f}]"

    methods = sorted(frame[frame.scope.eq("accuracy")].method.unique())
    lines = [
        "| Pipeline | fGn MAE [95% MC interval] | ARFIMA MAE [95% MC interval] | AR(1) MAE [95% MC interval] |",
        "| --- | --- | --- | --- |",
    ]
    for method in methods:
        values = [
            fmt(select("accuracy", "domain_aggregate", method, "mae", domain=domain))
            for domain in ["fGn", "ARFIMA", "AR1"]
        ]
        lines.append("| " + " | ".join([method, *values]) + " |")
    mae_table = "\n".join(lines)
    lines = [
        "| Method | Centered minus raw clean MAE, fGn | ARFIMA | AR(1) |",
        "| --- | --- | --- | --- |",
    ]
    for method in ["Higuchi", "GHE"]:
        values = [
            fmt(
                select(
                    "accuracy",
                    "domain_aggregate",
                    method,
                    "mae_difference",
                    domain=domain,
                    contrast="geometric_mean_removal_clean",
                )
            )
            for domain in ["fGn", "ARFIMA", "AR1"]
        ]
        lines.append("| " + " | ".join([method, *values]) + " |")
    centering_table = "\n".join(lines)
    lines = [
        "| Method | Constant offset: raw | Constant offset: centered | Midpoint step of 2 SD: raw | Midpoint step of 2 SD: centered |",
        "| --- | --- | --- | --- | --- |",
    ]
    for method in ["Higuchi", "GHE"]:
        values = []
        for condition in ["constant_offset__shift_1", "step_change__position_0.5__shift_2"]:
            for suffix in ["", "::centered"]:
                row = select(
                    "stress",
                    "domain_aggregate",
                    method + suffix,
                    "absolute_error_inflation",
                    condition,
                    "fGn",
                )
                values.append("< 10⁻¹² (roundoff)" if abs(row.value) < 1e-12 else fmt(row))
        lines.append("| " + " | ".join([method, *values]) + " |")
    stress_table = "\n".join(lines)
    lines = [
        "| Method | CBC raw percentile | CBC centered percentile | CBC centered basic | Fitted-fGn centered basic |",
        "| --- | --- | --- | --- | --- |",
    ]
    for method in ["GPH::narrow_band", "Higuchi", "GHE"]:
        values = [
            fmt(
                select("intervals", "fGn_0.85_n512", method, "unconditional_coverage", condition),
                True,
            )
            for condition in [
                "cbc_raw_percentile",
                "cbc_centered_percentile",
                "cbc_centered_basic",
                "unknown_fgn_centered_basic",
            ]
        ]
        lines.append("| " + " | ".join([method, *values]) + " |")
    coverage_table = "\n".join(lines)
    normal = fmt(
        select(
            "intervals",
            "fGn_0.85_n512",
            "GPH::narrow_band",
            "unconditional_coverage",
            "gph_normal_raw",
        ),
        True,
    )
    paired = {}
    for method in ["Higuchi", "GHE"]:
        row = select(
            "intervals",
            "fGn_0.85_n512",
            method,
            "coverage_difference",
            "unknown_fgn_centered_basic_minus_cbc_centered_basic",
            contrast="interval_model",
        )
        paired[method] = (
            f"{row.value * 100:.2f} percentage points [{row.ci_low * 100:.2f}, {row.ci_high * 100:.2f}]"
        )
    c = audit["counts"]
    report = f"""# Confirmation results and independent audit

Package 10 · 7 September 2026 · production revision `9c02d04`

The full confirmation result set passes the independent audit described below.
The findings require a substantial rewrite of the supplied draft: point accuracy
depends on the process and scale rules, removing a sample mean has distinct costs
and benefits, and numerical interval availability does not establish coverage.

## What was verified

| Quantity | Audited total |
| --- | ---: |
| Committed chunks | {c["chunks"]:,} |
| Independent clean parents | {c["parents"]:,} |
| Separately contaminated descendants | {c["descendants"]:,} |
| Point fits / valid point fits | {c["point_fits"]:,} / {c["valid_point_fits"]:,} |
| Interval parents, selected from clean parents | {c["interval_parents"]:,} |
| Interval comparisons / available intervals | {c["interval_rows"]:,} / {c["available_intervals"]:,} |
| Physical bootstrap records | {c["physical_bootstrap_records"]:,} |
| Statistic attempts / finite statistics | {c["statistic_attempts"]:,} / {c["statistic_used"]:,} |
| Failed / invalid / unattempted statistic positions | {c["statistic_failed"]:,} / {c["statistic_invalid"]:,} / {c["statistic_unattempted"]:,} |
| Cell and domain summary rows | {c["cell_summary_rows"] + c["domain_summary_rows"]:,} |

There are 33 accuracy cells (2,000 parents each), 14 stress cells (the first 500
parents of each eligible accuracy cell) and 10 interval cells. Seven interval
core cells have 2,000 parents each at n=512; three length-sensitivity cells have
500 each at n=1024. The 21 point pipelines comprise 19 audited configurations
from 12 base algorithms plus sample-centered Higuchi and GHE variants.
The 23 contaminations are applied separately to each selected clean parent.

The independent audit imports no producer reader, interval builder or summary
function. It checks all chunk files, signals, seed derivations, parent links,
method settings, analyzed-input hashes and target labels; replays all 161,000
contaminations; inspects every aligned within-record statistic; and reconstructs
all 248,000 interval endpoint pairs. It also checks that the original interval
statistics agree with the corresponding point-study estimates.

All {c["cell_summary_rows"]:,} cell summary values, paired contrasts, support
counts and applicable Monte Carlo standard errors are independently reconstructed.
Literal parent gathering reproduces {c["cell_summary_draws_reconstructed"]:,}
entries at 31 predetermined positions in each 1,999-draw cell distribution.
All {c["cell_summary_draw_positions_inspected"]:,} stored cell-draw positions are
inspected when recalculating uncertainty and availability. Every one of the
{c["domain_summary_draws_reconstructed"]:,} domain-draw entries is recombined
from its cells, including weighted MAE ratios and RMSE. All 118,917 canonical
rows reconcile exactly after explicit parsing of numeric CSV columns.

This is an independent result audit, not a second execution of all estimator
fits or all clean simulations. Those equations and replay paths were validated
in the earlier packages. Only 31 of 1,999 cell summary resamples are independently
reconstructed from raw parents here; all saved distributions supply the separate
full interval/SE checks. Fourteen adversarial tests cover pairing, missing
intervals, nonlinear aggregation, boundary uncertainty, mixed CSV types and
deliberately corrupted summaries. The audit needed a numeric-parsing correction
for blank-containing CSV columns; this did not change any producer output.

## Clean-record accuracy is process dependent

Each domain below weights its declared process/length cells equally: 12 fGn,
9 ARFIMA and 12 AR(1) cells. The AR(1) target is its asymptotic H=0.5; strong
short-memory persistence can produce substantial finite-scale error against
that target. These are descriptive pointwise Monte Carlo intervals, without a
global composite ranking or a test of universal superiority.

{mae_table}

The corrected geometric implementations no longer support the draft's saturation
and constant-anchor account. At n=512, mean Higuchi estimates are 0.2469 and
0.8347 for fGn H=0.25 and H=0.85; GHE means are 0.2467 and 0.8320. The historical
implementation defects remain documented as defects of those versions.

![Every clean accuracy cell](confirmation_audit/results/clean_accuracy.png)

## Mean removal solves the offset control but not internal steps

Sample centering raises average clean fGn/ARFIMA MAE for these geometric pipelines
and slightly reduces it over the AR(1) grid. The following are the predeclared
paired centered-minus-raw contrasts; positive values mean higher MAE.

{centering_table}

For the fGn stress domain (eight process/length cells, 500 paired parents each),
the examples below report MAE increase relative to the matched clean subset.
The constant offset is one clean sample SD; the internal step is two clean
sample SDs at the midpoint. They are different interventions. Sample centering
removes the constant-offset effect to floating-point precision, while substantial
step-related error remains. These examples illustrate the complete 23-condition
tables, which retain all methods and all cells.

{stress_table}

Absolute estimate drift is exported separately from MAE increase. A method can
move substantially while its mean absolute error changes little; these quantities
must not share a pooled score, axis or caption. The stress target is latent clean
recovery, not an assertion that the contaminated record has the clean process H.

## Available intervals can be severely miscalibrated

All 248,000 interval comparisons are available, and all 278,860,500 requested
statistic positions are finite. At fGn H=0.85 and n=512, however, unconditional
coverage varies markedly. Each estimate below uses 2,000 independent parents;
brackets are 95% Wilson intervals for the coverage proportion.

{coverage_table}

The GPH normal comparator covers {normal}. Switching from centered CBC basic
to fitted-fGn centered basic increases coverage by {paired["Higuchi"]} for
Higuchi and {paired["GHE"]} for GHE in this cell; these are paired Monte Carlo
intervals. Even the fitted-fGn geometric intervals retain some undercoverage.
The complete cellwise table is required: nominal-looking performance in one
cell does not establish calibration across the grid.

The model-mismatch controls are decisive. For AR(1) phi=0.8 or 0.95 at n=512,
the fitted-fGn Higuchi and GHE intervals cover H=0.5 in 0/2,000 parents per
method/cell (Wilson upper bound 0.192%). At n=1024, phi=0.95, they cover 0/500
(upper bound 0.762%). The fitted-fGn optimizer reaches its declared boundary
region in 1,971/2,000 phi=0.8 core parents, all 2,000 phi=0.95 core parents,
and all 500 phi=0.95 sensitivity parents. These fits are retained and flagged.
Completion of the optimizer is not evidence that the fGn model represents these
short-memory controls adequately. No fitted-model interval is a universal remedy.

![All declared interval coverage cells](confirmation_audit/results/interval_coverage.png)

The interval study includes GPH, Higuchi and GHE on clean records. It supplies
no confirmation evidence about DFA interval coverage or coverage under
contamination. H>=0.6 remains an exceedance diagnostic, not a calibrated LRD test
or an estimate of a nominal 5% false-positive rate.

## Consequences for the paper

The draft's main rankings, counts, saturation conclusions, coverage-collapse
tables, false-positive claims and EEG-validation claims must be replaced.
The eight old observational records were software fixtures. This confirmation
supports a synthetic benchmark of memory/scaling estimates with explicit
model-mismatch and contamination controls; it does not establish clinical,
biomarker, criticality or empirical EEG validity.

The next phase is a manuscript rebuild using this one result set: retitle and
rewrite the abstract; replace Methods with the frozen design and explicit
estimands; replace Results figures/tables; rewrite Discussion around the observed
tradeoffs; and audit every remaining numeric claim. The original draft PDF stays
preserved. The [claim replacement ledger](confirmation_audit/results/draft_claim_ledger.csv)
records the disposition of the major legacy claims.

## Reproducible artifacts

* [Audit specification and limits](confirmation_audit/README.md)
* [Machine-readable audit evidence](confirmation_audit/results/audit_evidence.json)
* [Cell accounting and model-boundary counts](confirmation_audit/results/cell_accounting.csv)
* [All clean MAEs with Monte Carlo intervals](confirmation_audit/results/accuracy_mae.csv)
* [All cell/domain coverage values and uncertainty](confirmation_audit/results/interval_coverage.csv)
* [Every stress condition's domain effects](confirmation_audit/results/stress_effects_domains.csv)
* Full metric and contrast tables: `confirmation_audit/results/{{accuracy,stress,intervals}}_{{cells,domains}}.csv.gz`
* [All planned contrasts](confirmation_audit/results/planned_contrasts.csv.gz)
* [Exact source rows for narrative examples](confirmation_audit/results/narrative_evidence.csv)
* [Export checksums](confirmation_audit/results/export_provenance.json)

Run identity: `{RUN}`. Scientific design:
`{audit["scientific_design_sha256"]}`. The frozen runtime and production archive
remain outside OneDrive; this audit changes neither. Figures are provided as
PNG and editable SVG. CSV values are unrounded; prose and figures round only
for presentation.
"""
    (output.parent.parent / "confirmation-results.md").write_text(report, encoding="utf-8")
    claims = [
        (
            "C01",
            "Title; abstract; Sections 1 and 5",
            "Empirical neural-time-series evaluation and neurophysiological estimator guidance",
            "replace",
            "Synthetic process benchmark with model-mismatch controls; no empirical EEG or clinical validation",
            "Frozen claim exclusions",
            "Retitle and rewrite framing",
        ),
        (
            "C02",
            "Abstract; Sections 2.2-2.3; Table 1",
            "15 methods; 160 clean and 3200 stress records; old lengths and H grid",
            "replace",
            "21 pipelines, 12 base algorithms, 66000 independent parents, 161000 descendants; protocol-v1 grid",
            "cell_accounting.csv; scientific_design_lock.json",
            "Regenerate design and method tables",
        ),
        (
            "C03",
            "Sections 2.3.1-2.3.2",
            "Davies-Harte generation and shared GT/ST sampling",
            "replace",
            "Exact covariance Cholesky or stationary AR1 recursion; identical clean parents reused for stress/interval subsets",
            "audit_evidence.json; confirmation-protocol.md",
            "Document exact algorithms and seeds",
        ),
        (
            "C04",
            "Abstract; Tables 2-3 and 12; Figures 1-2; Sections 4.1 and 5",
            "DFA short scales is first across modes and robust across families",
            "replace",
            "Report all clean cells and separate equal-cell fGn/ARFIMA/AR1 means; all stress conditions separate",
            "accuracy_mae.csv; stress_effects_domains.csv",
            "Remove global winner and composite-score narrative",
        ),
        (
            "C05",
            "Section 2.3.2; Figure 3",
            "Level shift robustness describes an internal jump",
            "replace",
            "Constant offset and internal step are distinct controls; centering removes offset but retains step effects",
            "stress_cells.csv.gz; planned_contrasts.csv.gz",
            "Use exact onset/amplitude definitions and separate panels",
        ),
        (
            "C06",
            "Section 3.3; Figure 3",
            "Mixed drift/error-ratio degradation curve",
            "replace",
            "Separate absolute estimate drift, signed drift, paired MAE increase and ratio of aggregate MAEs",
            "stress_cells.csv.gz; stress_domains.csv.gz",
            "Regenerate captions and metric-specific figures",
        ),
        (
            "C07",
            "Tables 5-6; Sections 3.6 and 4.4; conclusion",
            "DFA perfect coverage and coverage collapse under contamination",
            "remove from confirmation claims",
            "Current interval experiment concerns clean GPH/Higuchi/GHE only; coverage is cellwise and construction-specific",
            "interval_coverage.csv; intervals_cells.csv.gz",
            "Replace CI section; do not imply DFA or stress-CI evidence",
        ),
        (
            "C08",
            "Section 2.4; Table 7; Figure 7; Sections 3.7 and 5",
            "95% CI-based LRD test and nominal 5% false-positive results",
            "remove",
            "H>=0.6 is an exceedance diagnostic; no calibrated LRD testing experiment",
            "accuracy_cells.csv.gz; protocol claim exclusions",
            "Remove hypothesis-test and false-positive terminology",
        ),
        (
            "C09",
            "Table 8; Section 4.1",
            "500 resamples establish a statistically significant universal ordering",
            "replace",
            "2000/500 independent parents, B1999 within-record resamples, and separate B1999 summary resamples; descriptive paired pointwise intervals",
            "audit_evidence.json; planned_contrasts.csv.gz",
            "Separate replication levels; remove non-overlap significance claim",
        ),
        (
            "C10",
            "Abstract; Table 9; Sections 4.2-4.3; conclusion",
            "Higuchi saturation and GHE anchoring are intrinsic method failures",
            "replace",
            "Earlier implementation defects repaired; corrected estimates change with process H; remaining bias and centering effects are measured",
            "accuracy_cells.csv.gz; method-audit.md",
            "Distinguish historical code defects from method performance",
        ),
        (
            "C11",
            "Tables 10-12; Figure 8; Section 3.10; conclusion",
            "Eight EEG records externally validate estimator accuracy and stability",
            "remove from empirical findings",
            "Eight deterministic fixtures demonstrate software workflow only",
            "benchmark-review.md; frozen claim exclusions",
            "Remove observational validation narrative; future EEG work needs new protocol/data",
        ),
        (
            "C12",
            "Section 3.8; conclusion",
            "100% point validity proves no resampling failures or calibration problem",
            "replace",
            "Point validity, statistic accounting, interval availability and coverage audited separately",
            "audit_evidence.json; interval_coverage.csv",
            "Report each denominator independently",
        ),
        (
            "C13",
            "Abstract; Discussion; Conclusion",
            "Polynomial trend is universally the worst operator",
            "replace",
            "Report each declared contamination condition and process domain; no global stress score or arbitrary condition weights",
            "stress_cells.csv.gz; stress_domains.csv.gz",
            "Bound conclusions to specific operator, strength, method and domain",
        ),
    ]
    pd.DataFrame(
        claims,
        columns=[
            "id",
            "draft_location",
            "legacy_claim_paraphrase",
            "disposition",
            "replacement_basis",
            "evidence",
            "manuscript_action",
        ],
    ).to_csv(output / "draft_claim_ledger.csv", index=False)
    # Include mean-estimate checks and mismatch examples in the evidence ledger too.
    for cell in ["fGn_0.25_n512", "fGn_0.85_n512"]:
        for method in ["Higuchi", "GHE"]:
            select("accuracy", cell, method, "bias")
    for cell in ["AR1_0.8_n512", "AR1_0.95_n512", "AR1_0.95_n1024"]:
        for method in ["Higuchi", "GHE"]:
            select(
                "intervals", cell, method, "unconditional_coverage", "unknown_fgn_centered_basic"
            )
        select("intervals", cell, "unknown_mean_fGn_ML", "model_boundary_rate_all_attempts")
    pd.DataFrame(narrative).drop_duplicates().to_csv(output / "narrative_evidence.csv", index=False)
    print("Wrote confirmation-results.md and 13 draft-claim dispositions.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    main(args.source, args.output)
