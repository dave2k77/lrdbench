from __future__ import annotations

import math
from collections import defaultdict
from fractions import Fraction
from itertools import groupby

from lrdbench.enums import OptimisationDirection
from lrdbench.interfaces import BaseLeaderboardBuilder
from lrdbench.metrics_catalog import METRIC_SPECS
from lrdbench.schema import BenchmarkManifest, LeaderboardRow, MetricBundle


class WeightedRankLeaderboardBuilder(BaseLeaderboardBuilder):
    def build(
        self,
        manifest: BenchmarkManifest,
        metrics: MetricBundle,
    ) -> tuple[LeaderboardRow, ...]:
        if not manifest.leaderboard_specs:
            return ()
        rows_out: list[LeaderboardRow] = []
        run_id = manifest.manifest_id
        eligible_estimators = {spec.name for spec in manifest.estimator_specs}
        specs = {**METRIC_SPECS, **{m.name: m for m in manifest.metric_specs}}

        agg_global = [m for m in metrics.aggregate if m.stratum.get("level") == "balanced_global"]
        for lb in manifest.leaderboard_specs:
            if lb.mode is not manifest.mode:
                continue
            if lb.ranking_rule != "weighted_rank":
                raise ValueError(f"unsupported ranking rule: {lb.ranking_rule!r}")
            if lb.tie_break_rule == "best_primary_metric":
                tie_metric = lb.component_metrics[0] if lb.component_metrics else None
            elif lb.tie_break_rule == "none":
                tie_metric = None
            elif lb.tie_break_rule in lb.component_metrics:
                tie_metric = lb.tie_break_rule
            else:
                raise ValueError(f"unsupported tie-break rule: {lb.tie_break_rule!r}")
            acc: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
            for m in agg_global:
                if (
                    m.metric_name not in lb.component_metrics
                    or m.value is None
                    or not math.isfinite(m.value)
                ):
                    continue
                if m.estimator_name not in eligible_estimators:
                    continue
                acc[m.estimator_name][m.metric_name].append(float(m.value))
            estimators = sorted(eligible_estimators)
            by_est: dict[str, dict[str, float | None]] = {}
            for e in estimators:
                by_est[e] = {}
                for comp in lb.component_metrics:
                    vals = acc[e].get(comp, [])
                    by_est[e][comp] = math.fsum(v / len(vals) for v in vals) if vals else None
            comp_metrics = lb.component_metrics
            comp_ranks: dict[str, dict[str, Fraction]] = {c: {} for c in comp_metrics}

            def value_key(
                name: str,
                comp: str,
                values: dict[str, dict[str, float | None]] = by_est,
            ) -> float:
                value = values[name][comp]
                if value is None:
                    return math.inf
                spec = specs.get(comp)
                direction = (
                    spec.optimisation_direction
                    if spec is not None
                    else OptimisationDirection.MINIMISE
                )
                if direction is OptimisationDirection.MAXIMISE:
                    return -value
                return value

            for comp in comp_metrics:
                ranks = {name: Fraction(len(estimators) + 1) for name in estimators}
                available = [name for name in estimators if by_est[name][comp] is not None]
                available.sort(key=lambda name: value_key(name, comp))
                position = 1
                for _, group in groupby(available, key=lambda name: value_key(name, comp)):
                    tied = list(group)
                    average_rank = Fraction(2 * position + len(tied) - 1, 2)
                    for name in tied:
                        ranks[name] = average_rank
                    position += len(tied)
                comp_ranks[comp] = ranks

            # Exact decimal weights prevent arithmetic-order artefacts in score ties.
            scores: dict[str, Fraction] = {}
            for e in estimators:
                s = Fraction(0)
                for comp in comp_metrics:
                    w = Fraction(str(lb.weights.get(comp, 0)))
                    s += w * comp_ranks[comp][e]
                scores[e] = s

            scientific_keys = {
                name: (scores[name], value_key(name, tie_metric) if tie_metric else 0.0)
                for name in estimators
            }
            sorted_est = sorted(scores, key=lambda name: (scientific_keys[name], name))
            previous_key: tuple[Fraction, float] | None = None
            rank = 0
            for position, ename in enumerate(sorted_est, start=1):
                key = scientific_keys[ename]
                if key != previous_key:
                    rank = position
                previous_key = key
                comp_vals: dict[str, float | None] = {c: by_est[ename].get(c) for c in comp_metrics}
                rows_out.append(
                    LeaderboardRow(
                        run_id=run_id,
                        estimator_name=ename,
                        rank=rank,
                        score=float(scores[ename]),
                        component_values=comp_vals,
                        metadata={
                            "leaderboard_name": lb.name,
                            "component_metrics": comp_metrics,
                            "tie_break_rule": lb.tie_break_rule,
                            "component_ranks": {
                                c: float(comp_ranks[c][ename]) for c in comp_metrics
                            },
                            "ranking_version": "2",
                            "missing_component_rank": len(estimators) + 1,
                        },
                    )
                )
        return tuple(rows_out)
