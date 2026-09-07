"""Finite-sample diagnostic pilot, not a confirmatory estimator/CI validation."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import platform
import subprocess
import types
from importlib.metadata import distributions
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from lrdbench.defaults import build_default_estimator_registry
from lrdbench.enums import SourceType
from lrdbench.schema import EstimatorSpec, ProvenanceRecord, SeriesRecord

BASE = "5189d85"
SEED = 20260907
N = 512
REPETITIONS = 32
BOOTSTRAP_DRAWS = 64
BLOCK_LENGTH = 32
METHODS = {
    "RS": ("RS", {"min_scale": 8, "max_scale": 128}),
    "DFA": ("DFA", {"min_scale": 8, "max_scale": 128, "detrend_order": 1}),
    "GPH": ("GPH", {"m": 32}),
    "Higuchi": ("Higuchi", {"k_max": 32, "input_representation": "increments"}),
    "GHE_q1": ("GHE", {"q": 1, "h_max": 32, "input_representation": "increments"}),
    "GHE_q2": ("GHE", {"q": 2, "h_max": 32, "input_representation": "increments"}),
    "WaveletOLS": ("WaveletOLS", {"wavelet": "db2", "j_drop_high": 1, "j_drop_low": 1}),
}


def reference_fgn(hurst: float, rng: np.random.Generator) -> np.ndarray:
    # Direct covariance reference, independent of the framework generator.
    lags = np.abs(np.arange(N)[:, None] - np.arange(N)[None, :])
    covariance = 0.5 * (
        np.abs(lags - 1) ** (2 * hurst) - 2 * lags ** (2 * hurst) + (lags + 1) ** (2 * hurst)
    )
    return np.linalg.cholesky(covariance) @ rng.normal(size=(N, REPETITIONS))


def reference_ar1(rng: np.random.Generator) -> np.ndarray:
    phi = 0.8
    innovations = rng.normal(scale=np.sqrt(1 - phi**2), size=(N + 4096, REPETITIONS))
    for t in range(1, innovations.shape[0]):
        innovations[t] += phi * innovations[t - 1]
    return innovations[-N:]


def write_csv(path: Path, rows: list[dict]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def wilson(hits: int, total: int) -> tuple[float, float]:
    z = 1.959963984540054
    p = hits / total
    denominator = 1 + z**2 / total
    center = (p + z**2 / (2 * total)) / denominator
    radius = z * np.sqrt(p * (1 - p) / total + z**2 / (4 * total**2)) / denominator
    return float(center - radius), float(center + radius)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    output = parser.parse_args().output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    root = Path(__file__).resolve().parents[2]
    registry = build_default_estimator_registry()
    legacy = {}
    for family in ("spectral", "geometric"):
        code = subprocess.check_output(
            ["git", "show", f"{BASE}:src/lrdbench/estimators/{family}.py"], cwd=root
        ).decode("utf-8")
        module = types.ModuleType(f"audit_legacy_{family}")
        exec(compile(code, f"{BASE}/{family}.py", "exec"), module.__dict__)
        legacy[family] = module
    rows = []
    baseline_rows = []
    for case, hurst in (
        ("fGn_H025", 0.25),
        ("fGn_H050", 0.5),
        ("fGn_H075", 0.75),
        ("AR1_phi08", 0.5),
    ):
        case_index = len({r["case"] for r in rows})
        rng = np.random.default_rng(SEED + case_index)
        samples = reference_ar1(rng) if case.startswith("AR1") else reference_fgn(hurst, rng)
        for repetition in range(REPETITIONS):
            values = samples[:, repetition]
            record = SeriesRecord(
                record_id=f"{case}_{repetition}",
                values=values,
                time_axis=None,
                sampling_rate=None,
                source_type=SourceType.SYNTHETIC,
                source_name="independent_reference",
                provenance=ProvenanceRecord(
                    record_id=f"{case}_{repetition}",
                    parent_id=None,
                    manifest_id="method_audit",
                    created_at="2026-09-07",
                    seed=SEED + 1000 * case_index + repetition,
                ),
            )
            for label, (name, params) in METHODS.items():
                n_boot = (
                    BOOTSTRAP_DRAWS
                    if case in {"fGn_H050", "fGn_H075"} and label in {"GPH", "Higuchi", "GHE_q1"}
                    else 0
                )
                spec = EstimatorSpec(
                    name=name,
                    family="audit",
                    target_estimand="hurst_scaling_proxy",
                    assumptions=(),
                    supports_ci=True,
                    supports_diagnostics=True,
                    parameter_schema={
                        **params,
                        "n_bootstrap": n_boot,
                        "bootstrap_block_len": BLOCK_LENGTH,
                    },
                )
                result = registry.get(name)(spec).fit(record)
                ci = next(
                    ((lo, hi) for level, lo, hi in result.bootstrap_cis if level == 0.95), None
                )
                rows.append(
                    {
                        "case": case,
                        "H_target": hurst,
                        "n": N,
                        "repetition": repetition,
                        "method": label,
                        "point": result.point,
                        "valid": result.valid,
                        "ci_low": ci[0] if ci else None,
                        "ci_high": ci[1] if ci else None,
                        "covered": int(ci[0] <= hurst <= ci[1]) if ci else None,
                        "bootstrap_draws": n_boot,
                        "failure_reason": result.failure_reason,
                        "estimator_version": result.estimator_version,
                        "diagnostics_json": json.dumps(dict(result.diagnostics), sort_keys=True),
                    }
                )
                if label == "GPH":
                    old = legacy["spectral"]._log_periodogram_regression_d(values, m=32)
                    old = old + 0.5 if old is not None else None
                elif label == "Higuchi":
                    old = legacy["geometric"]._higuchi_hurst_proxy(
                        np.r_[0.0, np.cumsum(values)], k_max=32
                    )
                else:
                    continue
                baseline_rows.append(
                    {
                        "case": case,
                        "H_target": hurst,
                        "repetition": repetition,
                        "method": label,
                        "old_point": old,
                        "new_point": result.point,
                    }
                )
        print(f"Completed {case}: {REPETITIONS} independent records", flush=True)

    point_summary, coverage_summary = [], []
    for case in dict.fromkeys(r["case"] for r in rows):
        for method in METHODS:
            selected = [r for r in rows if r["case"] == case and r["method"] == method]
            points = np.array(
                [r["point"] for r in selected if r["valid"] and r["point"] is not None]
            )
            target = selected[0]["H_target"]
            point_summary.append(
                {
                    "case": case,
                    "method": method,
                    "H_target": target,
                    "n_attempted": len(selected),
                    "n_valid": points.size,
                    "mean_H": float(np.mean(points)),
                    "bias": float(np.mean(points - target)),
                    "mae": float(np.mean(np.abs(points - target))),
                    "mean_mcse": float(np.std(points, ddof=1) / np.sqrt(points.size)),
                    "persistence_exceedance_at_06": float(np.mean(points >= 0.6)),
                }
            )
            if selected[0]["bootstrap_draws"]:
                intervals = [r for r in selected if r["covered"] is not None]
                hits = sum(r["covered"] for r in intervals)
                lo, hi = wilson(hits, len(intervals)) if intervals else (None, None)
                coverage_summary.append(
                    {
                        "case": case,
                        "method": method,
                        "nominal": 0.95,
                        "n_attempted": len(selected),
                        "n_available": len(intervals),
                        "n_covered": hits,
                        "coverage": hits / len(intervals) if intervals else None,
                        "coverage_wilson_low": lo,
                        "coverage_wilson_high": hi,
                        "bootstrap_draws": BOOTSTRAP_DRAWS,
                        "block_length": BLOCK_LENGTH,
                    }
                )
    write_csv(output / "point_estimates.csv", rows)
    write_csv(output / "point_summary.csv", point_summary)
    write_csv(output / "coverage_pilot.csv", coverage_summary)
    write_csv(output / "before_after.csv", baseline_rows)

    fig, axes = plt.subplots(1, 2, figsize=(10, 4), sharey=True)
    for ax, method in zip(axes, ("GPH", "Higuchi"), strict=True):
        for key, label, marker in (
            ("old_point", "Before repair", "x"),
            ("new_point", "After repair", "o"),
        ):
            means = [
                np.mean(
                    [r[key] for r in baseline_rows if r["method"] == method and r["case"] == case]
                )
                for case in ("fGn_H025", "fGn_H050", "fGn_H075")
            ]
            ax.plot([0.25, 0.5, 0.75], means, marker=marker, label=label)
        ax.plot([0.2, 0.8], [0.2, 0.8], "--", color="grey", label="Known H")
        ax.set(title=method, xlabel="Known H", ylabel="Mean estimated H", ylim=(0, 1.05))
        ax.legend()
    fig.suptitle(
        f"Implementation audit: n={N}, {REPETITIONS} records per H; Higuchi uses integrated paths"
    )
    fig.tight_layout()
    fig.savefig(output / "before_after.png", dpi=160)
    plt.close(fig)
    provenance = {
        "status": "diagnostic_pilot_not_confirmatory",
        "baseline_commit": BASE,
        "seed": SEED,
        "n": N,
        "independent_repetitions_per_case": REPETITIONS,
        "methods": METHODS,
        "ci_bootstrap_draws": BOOTSTRAP_DRAWS,
        "ci_block_length": BLOCK_LENGTH,
        "python": platform.python_version(),
        "packages": {d.metadata["Name"]: d.version for d in distributions() if d.metadata["Name"]},
        "source_sha256": {
            str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted((root / "src/lrdbench").rglob("*.py"))
        },
    }
    (output / "provenance.json").write_text(json.dumps(provenance, indent=2), encoding="utf-8")
    print(json.dumps(coverage_summary, indent=2))


if __name__ == "__main__":
    main()
