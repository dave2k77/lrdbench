from __future__ import annotations

from pathlib import Path

from lrdbench.examples.custom_estimator import build_variance_ratio_estimator
from lrdbench.manifest import manifest_from_mapping
from lrdbench.registries import EstimatorRegistry
from lrdbench.runner import BenchmarkRunner
from lrdbench.schema import BenchmarkRunOutput


def build_external_registry() -> EstimatorRegistry:
    registry = EstimatorRegistry()
    registry.register("VarianceRatio", build_variance_ratio_estimator)
    return registry


def custom_estimator_manifest(export_root: str = "reports/custom_estimator") -> dict[str, object]:
    return {
        "manifest_id": "custom_estimator_example_v1",
        "name": "custom_estimator_example",
        "mode": "ground_truth",
        "source": {
            "type": "generator_grid",
            "generators": [
                {
                    "family": "fGn",
                    "params": {"H": [0.5, 0.7], "n": [256], "sigma": [1.0]},
                    "replicates": 1,
                }
            ],
        },
        "estimators": [
            {
                "name": "VarianceRatio",
                "family": "external",
                "target_estimand": "hurst_scaling_proxy",
                "assumptions": ["finite_variance", "example_only"],
                "supports_ci": False,
                "supports_diagnostics": True,
                "params": {"min_n": 32},
            }
        ],
        "metrics": ["bias", "mae", "validity_rate", "runtime"],
        "leaderboards": [
            {
                "name": "external_example",
                "mode": "ground_truth",
                "component_metrics": ["mae", "validity_rate", "runtime"],
                "weights": {"mae": 0.5, "validity_rate": 0.4, "runtime": 0.1},
                "ranking_rule": "weighted_rank",
                "tie_break_rule": "mae",
            }
        ],
        "report": {"formats": ["html", "csv"], "export_root": export_root},
        "seeds": {"global_seed": 20260426},
        "execution": {"max_workers": 1},
    }


def run_custom_estimator_example(export_root: str = "reports/custom_estimator") -> BenchmarkRunOutput:
    manifest = manifest_from_mapping(custom_estimator_manifest(export_root))
    return BenchmarkRunner(estimators=build_external_registry()).run(
        manifest,
        base_dir=Path.cwd(),
    )


if __name__ == "__main__":
    output = run_custom_estimator_example()
    print(f"run_id={output.run_id}")
    print(f"result_store={output.result_store_path}")
