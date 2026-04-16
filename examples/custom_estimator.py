"""Placeholder: register a custom estimator via EstimatorRegistry (see src/lrdbench/defaults.py)."""

from __future__ import annotations


def main() -> None:
    # Implement BaseEstimator, then:
    #   reg = build_default_estimator_registry()
    #   reg.register("MY_EST", lambda spec: MyEstimator(spec))
    #   BenchmarkRunner(estimators=reg).run(manifest)
    raise SystemExit("See lrdbench.interfaces.BaseEstimator and lrdbench.defaults for wiring.")


if __name__ == "__main__":
    main()
