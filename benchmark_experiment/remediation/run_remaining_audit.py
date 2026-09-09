"""Classical-roster checks and a fixed development CI pilot, not confirmatory results."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import platform
import time
from importlib.metadata import distributions
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.special import gammaln

from lrdbench.defaults import build_default_estimator_registry
from lrdbench.enums import SourceType
from lrdbench.generators._signal import arfima_autocovariance, arfima_ma_coefficients
from lrdbench.schema import EstimatorSpec, ProvenanceRecord, SeriesRecord

SEED = 20260908
CASES = {
    "fGn025": (0, 0.25),
    "fGn050": (1, 0.5),
    "fGn075": (2, 0.75),
    "AR1_phi08": (3, 0.5),
    "ARFIMA_d03": (4, 0.8),
}
POINT_REPETITIONS = 32
CI_REPETITIONS = 64
CI_DRAWS = 199
CI_BLOCKS = (16, 32, 64)
CI_METHODS = {
    "GPH": {"m": 32},
    "Higuchi": {"k_max": 32, "input_representation": "increments"},
    "GHE": {"q": 1.0, "h_max": 32, "input_representation": "increments"},
}


def wilson(hits, total):
    if not total:
        return None, None
    z = 1.959963984540054
    p = hits / total
    center = (p + z * z / (2 * total)) / (1 + z * z / total)
    radius = z * np.sqrt(p * (1 - p) / total + z * z / (4 * total**2)) / (1 + z * z / total)
    return float(center - radius), float(center + radius)


def record_seed(case, n, repetition):
    return int(np.random.SeedSequence([SEED, CASES[case][0], n, repetition]).generate_state(1)[0])


def samples(case, n, repetitions):
    """Data identity depends only on case, n and independent repetition index."""
    noises = np.column_stack(
        [
            np.random.default_rng(record_seed(case, n, r)).normal(
                size=n + 4096 if case.startswith("AR1") else n
            )
            for r in range(repetitions)
        ]
    )
    h = CASES[case][1]
    if case.startswith("AR1"):
        noises *= np.sqrt(1 - 0.8**2)
        for t in range(1, len(noises)):
            noises[t] += 0.8 * noises[t - 1]
        return noises[-n:]
    k = np.arange(n, dtype=float)
    if case.startswith("ARFIMA"):
        d = h - 0.5
        # Direct gamma expression, independently of the generator's recurrence.
        covariance = np.exp(
            gammaln(1 - 2 * d) + gammaln(k + d) - gammaln(d) - gammaln(1 - d) - gammaln(k + 1 - d)
        )
    else:
        covariance = (np.abs(k - 1) ** (2 * h) - 2 * k ** (2 * h) + (k + 1) ** (2 * h)) / 2
    indices = np.abs(np.arange(n)[:, None] - np.arange(n)[None, :])
    return np.linalg.cholesky(covariance[indices]) @ noises


def configurations(root):
    with (root / "benchmark_experiment/remediation/estimator_eligibility.csv").open(
        encoding="utf-8", newline=""
    ) as handle:
        roster = list(csv.DictReader(handle))
    output = []
    for row in roster:
        params = json.loads(row["params_json"])
        base = params.pop("_base_estimator_name", row["configuration"])
        params.pop("_variant_name", None)
        params["n_bootstrap"] = 0
        if base in {"GHE", "Higuchi"}:
            params["input_representation"] = "increments"
        if base == "GHE":
            params["q"] = 1.0
        output.append((row["configuration"], base, params))
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--calibration-pilot", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    if (output / "point_estimates.csv").exists():
        raise SystemExit("Choose a new output directory to preserve prior audit results.")
    start = time.perf_counter()
    roster = configurations(root)
    registry = build_default_estimator_registry()
    pool, index = {}, []
    for n in (256, 512, 1024):
        for case in CASES:
            count = (
                CI_REPETITIONS
                if args.calibration_pilot and n == 512 and case in {"fGn050", "fGn075"}
                else POINT_REPETITIONS
            )
            pool[(case, n)] = samples(case, n, count)
            for r in range(count):
                x = pool[(case, n)][:, r]
                index.append(
                    {
                        "record_id": f"{case}_n{n}_r{r}",
                        "case": case,
                        "n": n,
                        "repetition": r,
                        "seed": record_seed(case, n, r),
                        "sha256": hashlib.sha256(x.tobytes()).hexdigest(),
                    }
                )
    np.savez_compressed(
        output / "shared_inputs.npz", **{f"{case}_n{n}": value for (case, n), value in pool.items()}
    )
    pd.DataFrame(index).to_csv(output / "input_index.csv", index=False)

    def fit(case, n, r, name, base, params):
        record_id = f"{case}_n{n}_r{r}"
        record = SeriesRecord(
            record_id,
            pool[(case, n)][:, r],
            None,
            None,
            SourceType.SYNTHETIC,
            case,
            provenance=ProvenanceRecord(
                record_id, None, "remaining_audit", "", seed=record_seed(case, n, r)
            ),
        )
        spec = EstimatorSpec(
            name, "diagnostic", "hurst_scaling_proxy", (), True, True, parameter_schema=params
        )
        estimate = registry.get(base)(spec).fit(record)
        return {
            "record_id": record_id,
            "case": case,
            "n": n,
            "repetition": r,
            "method": name,
            "H_target": CASES[case][1],
            "point": estimate.point,
            "valid": estimate.valid,
            "ci_low": estimate.ci_low,
            "ci_high": estimate.ci_high,
            "failure_reason": estimate.failure_reason,
            "estimator_version": estimate.estimator_version,
            "parameters_json": json.dumps(params, sort_keys=True),
            "diagnostics_json": json.dumps(dict(estimate.diagnostics), sort_keys=True),
        }

    points = []
    for n in (256, 512, 1024):
        for case in CASES:
            for r in range(POINT_REPETITIONS):
                for name, base, params in roster:
                    points.append(fit(case, n, r, name, base, params))
            print(f"Point checks complete: {case}, n={n}", flush=True)
    pd.DataFrame(points).to_csv(output / "point_estimates.csv", index=False)
    summary = []
    for (case, n, name), group in pd.DataFrame(points).groupby(["case", "n", "method"]):
        valid = group.loc[group.valid & group.point.notna(), "point"]
        target = CASES[case][1]
        summary.append(
            {
                "case": case,
                "n": n,
                "method": name,
                "H_target": target,
                "n_attempted": len(group),
                "n_valid": len(valid),
                "mean_H": valid.mean(),
                "bias": (valid - target).mean(),
                "mae": (valid - target).abs().mean(),
                "mean_mcse": valid.std(ddof=1) / np.sqrt(len(valid)) if len(valid) else None,
                "out_of_range_count": int(((valid <= 0) | (valid >= 1)).sum()),
                "persistence_exceedance_count": int((valid >= 0.6).sum()),
            }
        )
    pd.DataFrame(summary).to_csv(output / "point_summary.csv", index=False)
    ci_rows = []
    if args.calibration_pilot:
        for case in ("fGn050", "fGn075"):
            for name, settings in CI_METHODS.items():
                for block in CI_BLOCKS:
                    for r in range(CI_REPETITIONS):
                        row = fit(
                            case,
                            512,
                            r,
                            name,
                            name,
                            {**settings, "n_bootstrap": CI_DRAWS, "bootstrap_block_len": block},
                        )
                        row["block_length"] = block
                        ci_rows.append(row)
                        if (r + 1) % 16 == 0:
                            print(
                                f"CI pilot: {case}, {name}, block={block}, {r + 1}/{CI_REPETITIONS}",
                                flush=True,
                            )
                    pd.DataFrame(ci_rows).to_csv(output / "ci_estimates.csv", index=False)
        coverage = []
        for (case, name, block), group in pd.DataFrame(ci_rows).groupby(
            ["case", "method", "block_length"]
        ):
            available = group[group.valid & group.ci_low.notna() & group.ci_high.notna()]
            hits = int(
                ((available.ci_low <= CASES[case][1]) & (available.ci_high >= CASES[case][1])).sum()
            )
            low, high = wilson(hits, len(available))
            coverage.append(
                {
                    "case": case,
                    "method": name,
                    "n": 512,
                    "block_length": block,
                    "n_attempted": len(group),
                    "n_available": len(available),
                    "n_covered": hits,
                    "coverage": hits / len(available) if len(available) else None,
                    "coverage_wilson_low": low,
                    "coverage_wilson_high": high,
                    "mean_width": (available.ci_high - available.ci_low).mean(),
                    "nominal": 0.95,
                    "draws_per_fit": CI_DRAWS,
                }
            )
        pd.DataFrame(coverage).to_csv(output / "coverage_summary.csv", index=False)

    truncation = []
    for n in (256, 512, 1024):
        for d in (0.2, 0.3, 0.4, 0.45):
            taps = arfima_ma_coefficients(d, min(10 * n, 50000))
            exact = arfima_autocovariance(d, 1)[0]
            truncation.append(
                {
                    "n": n,
                    "d": d,
                    "truncation_lag": len(taps) - 1,
                    "exact_variance": exact,
                    "finite_filter_variance": np.dot(taps, taps),
                    "fraction_variance_missing": 1 - np.dot(taps, taps) / exact,
                }
            )
    pd.DataFrame(truncation).to_csv(output / "arfima_truncation.csv", index=False)
    provenance = {
        "status": "development_only_not_confirmatory",
        "seed": SEED,
        "point_repetitions": POINT_REPETITIONS,
        "ci_repetitions": CI_REPETITIONS if ci_rows else 0,
        "ci_draws": CI_DRAWS,
        "ci_blocks": CI_BLOCKS,
        "ci_methods": CI_METHODS,
        "independent_input_records": len(index),
        "point_fit_attempts": len(points),
        "ci_fit_attempts": len(ci_rows),
        "roster": roster,
        "elapsed_seconds": time.perf_counter() - start,
        "python": platform.python_version(),
        "packages": {d.metadata["Name"]: d.version for d in distributions() if d.metadata["Name"]},
        "source_sha256": {
            str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted((root / "src/lrdbench").rglob("*.py"))
        },
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    }
    (output / "provenance.json").write_text(json.dumps(provenance, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                key: provenance[key]
                for key in (
                    "independent_input_records",
                    "point_fit_attempts",
                    "ci_fit_attempts",
                    "elapsed_seconds",
                )
            }
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
