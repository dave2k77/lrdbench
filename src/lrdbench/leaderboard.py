from __future__ import annotations

from collections import defaultdict

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

        agg_global = [m for m in metrics.aggregate if m.stratum.get("level") == "balanced_global"]
        for lb in manifest.leaderboard_specs:
            if lb.mode is not manifest.mode:
                continue
            acc: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
            for m in agg_global:
                if m.metric_name not in lb.component_metrics or m.value is None:
                    continue
                if m.estimator_name not in eligible_estimators:
                    continue
                acc[m.estimator_name][m.metric_name].append(float(m.value))
            estimators = sorted(acc)
            by_est: dict[str, dict[str, float | None]] = {}
            for e in estimators:
                by_est[e] = {}
                for comp in lb.component_metrics:
                    vals = acc[e].get(comp, [])
                    by_est[e][comp] = (sum(vals) / len(vals)) if vals else None
            comp_metrics = lb.component_metrics
            comp_ranks: dict[str, dict[str, int]] = {c: {} for c in comp_metrics}

            for comp in comp_metrics:
                spec = METRIC_SPECS.get(comp)
                direction = (
                    spec.optimisation_direction
                    if spec is not None
                    else OptimisationDirection.MINIMISE
                )
                pairs = [(e, by_est[e].get(comp)) for e in estimators]
                if direction is OptimisationDirection.MAXIMISE:
                    sorted_pairs = sorted(
                        pairs,
                        key=lambda ev: (
                            float("-inf") if ev[1] is None else -float(ev[1]),
                            ev[0],
                        ),
                    )
                else:
                    sorted_pairs = sorted(
                        pairs,
                        key=lambda ev: (
                            float("inf") if ev[1] is None else float(ev[1]),
                            ev[0],
                        ),
                    )
                for rank_pos, (ename, _) in enumerate(sorted_pairs, start=1):
                    comp_ranks[comp][ename] = rank_pos

            scores: dict[str, float] = {}
            for e in estimators:
                s = 0.0
                for comp in comp_metrics:
                    w = float(lb.weights.get(comp, 0.0))
                    s += w * float(comp_ranks[comp].get(e, len(estimators) + 1))
                scores[e] = s

            sorted_est = sorted(scores, key=lambda x: (scores[x], x))
            for position, ename in enumerate(sorted_est, start=1):
                comp_vals: dict[str, float | None] = {c: by_est[ename].get(c) for c in comp_metrics}
                rows_out.append(
                    LeaderboardRow(
                        run_id=run_id,
                        estimator_name=ename,
                        rank=position,
                        score=float(scores[ename]),
                        component_values=comp_vals,
                        metadata={
                            "leaderboard_name": lb.name,
                            "component_metrics": comp_metrics,
                            "tie_break_rule": lb.tie_break_rule,
                        },
                    )
                )
        return tuple(rows_out)
