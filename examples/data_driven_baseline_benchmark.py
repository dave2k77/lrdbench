from __future__ import annotations

from pathlib import Path

from lrdbench.manifest import manifest_from_mapping
from lrdbench.runner import BenchmarkRunner
from lrdbench.schema import BenchmarkRunOutput


def data_driven_manifest(export_root: str = "reports/data_driven_example") -> dict[str, object]:
    return {
        "manifest_id": "data_driven_example_v1",
        "name": "data_driven_example",
        "mode": "stress_test",
        "source": {
            "type": "generator_grid",
            "generators": [
                {
                    "family": "fGn",
                    "params": {"H": [0.45, 0.75], "n": [128], "sigma": [1.0]},
                    "replicates": 1,
                }
            ],
        },
        "contamination": {
            "operators": [
                {"name": "level_shift", "params": {"shift": [0.2]}},
            ]
        },
        "ml_training": {
            "enabled": True,
            "target_estimand": "hurst_scaling_proxy",
            "validation_fraction": 0.25,
            "source": {
                "type": "generator_grid",
                "generators": [
                    {
                        "family": "fGn",
                        "params": {"H": [0.35, 0.5, 0.65, 0.8], "n": [128], "sigma": [1.0]},
                        "replicates": 2,
                    }
                ],
            },
            "contamination": {
                "include_clean": True,
                "operators": [
                    {"name": "level_shift", "params": {"shift": [0.2]}},
                ],
            },
        },
        "estimators": [
            {
                "name": "RS",
                "family": "temporal",
                "target_estimand": "hurst_scaling_proxy",
                "supports_ci": False,
                "supports_diagnostics": True,
                "params": {"n_bootstrap": 0},
            },
            {
                "name": "MLRandomForest",
                "family": "data_driven",
                "target_estimand": "hurst_scaling_proxy",
                "assumptions": ["trained_on_manifest_synthetic_distribution"],
                "supports_ci": False,
                "supports_diagnostics": True,
                "params": {"n_estimators": 20, "random_state": 7, "max_lag": 8},
            },
            {
                "name": "MLSVR",
                "family": "data_driven",
                "target_estimand": "hurst_scaling_proxy",
                "assumptions": ["trained_on_manifest_synthetic_distribution"],
                "supports_ci": False,
                "supports_diagnostics": True,
                "params": {"C": 5.0, "epsilon": 0.05, "max_lag": 8},
            },
        ],
        "metrics": ["mae", "bias", "estimate_drift", "validity_rate", "runtime"],
        "leaderboards": [
            {
                "name": "data_driven_example",
                "mode": "stress_test",
                "component_metrics": ["mae", "estimate_drift", "validity_rate", "runtime"],
                "weights": {"mae": 0.4, "estimate_drift": 0.3, "validity_rate": 0.2, "runtime": 0.1},
                "ranking_rule": "weighted_rank",
                "tie_break_rule": "best_primary_metric",
            }
        ],
        "report": {"formats": ["html", "csv"], "export_root": export_root},
        "execution": {"max_workers": 1},
        "seeds": {"global_seed": 7},
    }


def run_data_driven_example(export_root: str = "reports/data_driven_example") -> BenchmarkRunOutput:
    manifest = manifest_from_mapping(data_driven_manifest(export_root))
    return BenchmarkRunner().run(manifest, base_dir=Path.cwd())


def main() -> None:
    output = run_data_driven_example()
    print(f"run_id={output.run_id}")
    print(f"result_store={output.result_store_path}")
    if output.report_bundle and output.report_bundle.html_report_path:
        print(f"html_report={output.report_bundle.html_report_path}")
    if output.result_store_path:
        print(f"model_dir={Path(output.result_store_path) / 'ml_models'}")
        print(f"validate_output=lrdbench validate-output {output.result_store_path}")


if __name__ == "__main__":
    main()
