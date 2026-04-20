from __future__ import annotations

import hashlib
import itertools
import uuid
from collections.abc import Mapping
from dataclasses import replace
from pathlib import Path
from typing import Any

from lrdbench.defaults import (
    build_default_contamination_registry,
    build_default_estimator_registry,
    build_default_generator_registry,
)
from lrdbench.enums import BenchmarkMode
from lrdbench.evaluator import GroundTruthEvaluator, ObservationalEvaluator
from lrdbench.execution import collect_fit_jobs, run_fit_jobs
from lrdbench.interfaces import BaseEvaluator
from lrdbench.leaderboard import WeightedRankLeaderboardBuilder
from lrdbench.manifest import load_manifest, manifest_from_mapping
from lrdbench.observational_sources import load_observational_records
from lrdbench.registries import ContaminationRegistry, EstimatorRegistry, GeneratorRegistry
from lrdbench.reporter import SimpleHtmlCsvReporter
from lrdbench.result_store import CsvResultStore
from lrdbench.schema import BenchmarkManifest, BenchmarkRunOutput, ReportSpec, SeriesRecord


def _stable_seed(global_seed: int, *parts: object) -> int:
    h = hashlib.sha256(repr(parts).encode("utf-8")).digest()
    return int.from_bytes(h[:4], "big") % (2**31 - 1)


def _record_id(manifest_id: str, family: str, params: dict[str, Any], rep: int) -> str:
    key = f"{manifest_id}|{family}|{sorted(params.items())}|{rep}"
    return hashlib.sha1(key.encode("utf-8")).hexdigest()[:20]


def _contam_record_id(manifest_id: str, clean_id: str, op_name: str, op_params: dict[str, Any]) -> str:
    key = f"{manifest_id}|{clean_id}|{op_name}|{sorted(op_params.items())}"
    return hashlib.sha1(key.encode("utf-8")).hexdigest()[:20]


def _expand_generator_grid(source: dict[str, Any]) -> list[tuple[str, dict[str, Any], int]]:
    if source.get("type") != "generator_grid":
        raise ValueError("runner only supports source.type == generator_grid")
    out: list[tuple[str, dict[str, Any], int]] = []
    for block in source["generators"]:
        family = str(block["family"])
        params = dict(block["params"])
        reps = int(block.get("replicates", 1))
        keys = list(params)
        val_lists: list[list[Any]] = []
        for k in keys:
            v = params[k]
            val_lists.append(v if isinstance(v, list) else [v])
        for combo in itertools.product(*val_lists):
            pdict = dict(zip(keys, combo, strict=True))
            if family.upper() == "ARFIMA":
                p = int(pdict.get("p", 0))
                q = int(pdict.get("q", 0))
                if p != 0 or q != 0:
                    raise ValueError("ARFIMA generator supports only (0,d,0) in this release")
            for rep in range(reps):
                out.append((family, pdict, rep))
    return out


def _expand_contamination_grid(contamination: Mapping[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    out: list[tuple[str, dict[str, Any]]] = []
    for block in contamination.get("operators", []):
        name = str(block["name"])
        params = dict(block["params"])
        keys = list(params)
        val_lists: list[list[Any]] = []
        for k in keys:
            v = params[k]
            val_lists.append(v if isinstance(v, list) else [v])
        for combo in itertools.product(*val_lists):
            out.append((name, dict(zip(keys, combo, strict=True))))
    return out


class BenchmarkRunner:
    """Thin orchestrator: generate → estimate → evaluate → leaderboard → persist → report."""

    def __init__(
        self,
        *,
        generators: GeneratorRegistry | None = None,
        estimators: EstimatorRegistry | None = None,
        contaminations: ContaminationRegistry | None = None,
    ) -> None:
        self.generators = generators or build_default_generator_registry()
        self.estimators = estimators or build_default_estimator_registry()
        self.contaminations = contaminations or build_default_contamination_registry()
        self._gt_evaluator = GroundTruthEvaluator()
        self._leaderboard = WeightedRankLeaderboardBuilder()
        self._reporter = SimpleHtmlCsvReporter()

    def run(
        self,
        manifest: BenchmarkManifest,
        *,
        manifest_path: Path | None = None,
        base_dir: Path | None = None,
    ) -> BenchmarkRunOutput:
        if manifest.mode not in (
            BenchmarkMode.GROUND_TRUTH,
            BenchmarkMode.STRESS_TEST,
            BenchmarkMode.OBSERVATIONAL,
        ):
            raise NotImplementedError(
                f"mode {manifest.mode.value!r} is not implemented in this release "
                f"(supported: ground_truth, stress_test, observational)"
            )
        run_id = str(uuid.uuid4())
        global_seed = int(manifest.seed_spec.get("global_seed", 0))

        resolve_dir = (
            base_dir
            if base_dir is not None
            else (manifest_path.parent if manifest_path is not None else Path.cwd())
        )

        if manifest.mode is BenchmarkMode.GROUND_TRUTH:
            records = self._generate_records_ground_truth(manifest, global_seed)
            evaluator: BaseEvaluator = self._gt_evaluator
        elif manifest.mode is BenchmarkMode.STRESS_TEST:
            records = self._generate_records_stress_test(manifest, global_seed)
            evaluator = self._gt_evaluator
        else:
            records = load_observational_records(
                manifest, base_dir=resolve_dir, global_seed=global_seed
            )
            evaluator = ObservationalEvaluator(self.estimators)

        estimates = run_fit_jobs(
            collect_fit_jobs(records, manifest.estimator_specs),
            estimators=self.estimators,
            execution_spec=dict(manifest.execution_spec),
            cwd=resolve_dir,
        )

        metrics = evaluator.evaluate(manifest, records, estimates)
        boards = self._leaderboard.build(manifest, metrics)

        report_spec = manifest.report_spec or ReportSpec(
            formats=("html", "csv"),
            leaderboards=tuple(manifest.leaderboard_specs),
        )
        if not report_spec.leaderboards and manifest.leaderboard_specs:
            report_spec = replace(report_spec, leaderboards=tuple(manifest.leaderboard_specs))
        export_root = Path(report_spec.export_root)
        store_root = export_root / run_id
        store = CsvResultStore(store_root)
        store.write_run_metadata(manifest, run_id)
        store.write_records(records)
        store.write_estimates(estimates)
        store.write_metrics(metrics)
        store.write_leaderboards(boards)
        store_path = store.finalise()

        bundle = self._reporter.build(
            manifest,
            metrics,
            boards,
            report_spec=report_spec,
            run_id=run_id,
        )

        bundle = replace(bundle, result_store_path=store_path)

        return BenchmarkRunOutput(
            run_id=run_id,
            records=tuple(records),
            estimates=tuple(estimates),
            metrics=metrics,
            leaderboards=boards,
            report_bundle=bundle,
            result_store_path=store_path,
        )

    def _generate_records_ground_truth(
        self, manifest: BenchmarkManifest, global_seed: int
    ) -> list[SeriesRecord]:
        triples = _expand_generator_grid(dict(manifest.source_spec))
        records: list[SeriesRecord] = []
        for family, params, rep in triples:
            gen = self.generators.get(family)
            rid = _record_id(manifest.manifest_id, family, params, rep)
            seed = _stable_seed(global_seed, manifest.manifest_id, family, params, rep)
            rec = gen.generate(
                record_id=rid,
                params=params,
                seed=seed,
                manifest_id=manifest.manifest_id,
            )
            records.append(rec)
        return records

    def _generate_records_stress_test(
        self, manifest: BenchmarkManifest, global_seed: int
    ) -> list[SeriesRecord]:
        triples = _expand_generator_grid(dict(manifest.source_spec))
        scenarios = _expand_contamination_grid(dict(manifest.contamination_spec))
        records: list[SeriesRecord] = []
        for family, params, rep in triples:
            gen = self.generators.get(family)
            rid = _record_id(manifest.manifest_id, family, params, rep)
            seed = _stable_seed(global_seed, manifest.manifest_id, family, params, rep)
            rec = gen.generate(
                record_id=rid,
                params=params,
                seed=seed,
                manifest_id=manifest.manifest_id,
            )
            clean = replace(
                rec,
                annotations={
                    **dict(rec.annotations),
                    "stress_role": "clean",
                    "pair_group_id": rec.record_id,
                    "contamination_operator": "clean",
                    "contamination_family": "clean",
                    "contamination_severity": "clean",
                },
            )
            records.append(clean)
            for op_name, op_params in scenarios:
                op = self.contaminations.get(op_name)
                nid = _contam_record_id(manifest.manifest_id, clean.record_id, op_name, op_params)
                cseed = _stable_seed(
                    global_seed,
                    manifest.manifest_id,
                    "contam",
                    clean.record_id,
                    op_name,
                    tuple(sorted(op_params.items())),
                )
                contaminated = op.apply(
                    clean,
                    params=op_params,
                    seed=cseed,
                    manifest_id=manifest.manifest_id,
                    new_record_id=nid,
                )
                records.append(contaminated)
        return records


def run_manifest_path(path: str | Path) -> BenchmarkRunOutput:
    p = Path(path)
    manifest = load_manifest(p)
    return BenchmarkRunner().run(manifest, manifest_path=p)


def run_manifest_mapping(data: dict[str, Any], *, base_dir: Path | None = None) -> BenchmarkRunOutput:
    manifest = manifest_from_mapping(data)
    return BenchmarkRunner().run(manifest, base_dir=base_dir or Path.cwd())
