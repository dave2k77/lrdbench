from __future__ import annotations

from lrdbench.runner import run_manifest_mapping


def test_estimator_variants_run_through_default_registry(tmp_path) -> None:
    out = run_manifest_mapping(
        {
            "manifest_id": "variant_run",
            "name": "variant run",
            "mode": "ground_truth",
            "source": {
                "type": "generator_grid",
                "generators": [
                    {"family": "fGn", "params": {"H": [0.5], "n": [96]}, "replicates": 1},
                ],
            },
            "estimators": [
                {
                    "name": "DFA",
                    "family": "time_domain",
                    "target_estimand": "hurst_scaling_proxy",
                    "params": {"n_bootstrap": 0},
                    "variants": [
                        {"name": "short", "params": {"min_scale": 8, "max_scale": 32}},
                        {"name": "long", "params": {"min_scale": 16, "max_scale": 48}},
                    ],
                }
            ],
            "metrics": ["parameter_variant_sensitivity", "max_variant_drift"],
            "report": {"formats": ["csv"], "export_root": str(tmp_path / "reports")},
            "seeds": {"global_seed": 11},
        },
        base_dir=tmp_path,
    )

    assert {e.estimator_name for e in out.estimates} == {"DFA::short", "DFA::long"}
    assert {
        m.metric_name
        for m in out.metrics.per_series
        if m.estimator_name == "DFA"
    } == {"parameter_variant_sensitivity", "max_variant_drift"}
    assert out.report_bundle is not None
    paths = {a.path for a in out.report_bundle.artefacts}
    assert any(path.endswith("scale_window_sensitivity.csv") for path in paths)
