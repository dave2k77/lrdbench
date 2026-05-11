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
from lrdbench.ml_training import prepare_data_driven_estimators
from lrdbench.observational_sources import load_observational_records
from lrdbench.registries import ContaminationRegistry, EstimatorRegistry, GeneratorRegistry
from lrdbench.reporter import SimpleHtmlCsvReporter
from lrdbench.result_store import CsvResultStore
from lrdbench.schema import (
    ArtefactRecord,
    BenchmarkManifest,
    BenchmarkRunOutput,
    PluginProvenanceRecord,
    ReportSpec,
    SeriesRecord,
)


def _stable_seed(global_seed: int, *parts: object) -> int:
    h = hashlib.sha256(repr(parts).encode("utf-8")).digest()
    return int.from_bytes(h[:4], "big") % (2**31 - 1)


def _record_id(manifest_id: str, family: str, params: dict[str, Any], rep: int) -> str:
    key = f"{manifest_id}|{family}|{sorted(params.items())}|{rep}"
    return hashlib.sha1(key.encode("utf-8")).hexdigest()[:20]


def _contam_record_id(manifest_id: str, clean_id: str, op_name: str, op_params: dict[str, Any]) -> str:
    key = f"{manifest_id}|{clean_id}|{op_name}|{sorted(op_params.items())}"
    return hashlib.sha1(key.encode("utf-8")).hexdigest()[:20]


def _file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _ml_model_artefacts(run_id: str, export_root: Path) -> tuple[ArtefactRecord, ...]:
    model_dir = export_root / run_id / "ml_models"
    if not model_dir.is_dir():
        return ()
    out: list[ArtefactRecord] = []
    for path in sorted(model_dir.iterdir()):
        if not path.is_file():
            continue
        out.append(
            ArtefactRecord(
                artefact_id=f"{run_id}_ml_model_{path.stem}",
                run_id=run_id,
                artefact_type="ml_model" if path.suffix != ".json" else "ml_training_summary",
                format=path.suffix.lstrip(".") or "binary",
                path=str(path.as_posix()),
                hash=_file_sha256(path),
            )
        )
    return tuple(out)


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
    """Orchestrate a complete benchmark run.

    The runner implements the full benchmark loop:

    1. Load and validate the manifest.
    2. Materialise records from generators or observational sources.
    3. Optionally train data-driven estimators.
    4. Fit every enrolled estimator to every record.
    5. Evaluate mode-appropriate metrics.
    6. Build leaderboards.
    7. Persist results to a :class:`CsvResultStore`.
    8. Generate HTML/CSV/LaTeX report artefacts.

    Example::

        from lrdbench.runner import BenchmarkRunner
        from lrdbench.manifest import load_manifest

        runner = BenchmarkRunner()
        manifest = load_manifest("my_suite.yaml")
        output = runner.run(manifest)
        print(output.run_id)
    """

    def __init__(
        self,
        *,
        generators: GeneratorRegistry | None = None,
        estimators: EstimatorRegistry | None = None,
        contaminations: ContaminationRegistry | None = None,
        discover_plugins: bool = True,
    ) -> None:
        self.generators = generators or build_default_generator_registry()
        self.contaminations = contaminations or build_default_contamination_registry()
        self._plugin_provenance: list[PluginProvenanceRecord] = []
        if estimators is not None:
            self.estimators = estimators
        elif discover_plugins:
            from lrdbench.plugin_loader import build_estimator_registry_with_plugins

            reg, results = build_estimator_registry_with_plugins()
            self.estimators = reg
            self._plugin_provenance = [
                PluginProvenanceRecord(
                    plugin_name=r.plugin_name,
                    module_name_or_path=r.module_name_or_path,
                    entry_point_name=r.entry_point_name,
                    version=r.version,
                    status=r.status,
                    failure_reason=r.failure_reason,
                    source_hash=r.source_hash,
                )
                for r in results
            ]
        else:
            self.estimators = build_default_estimator_registry()
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
        """Execute the full benchmark loop for ``manifest``.

        Args:
            manifest: A validated :class:`BenchmarkManifest`.
            manifest_path: Path to the manifest file, used to resolve
                relative paths (e.g. observational CSV files).
            base_dir: Alternative directory for relative path resolution.
                If ``None``, defaults to ``manifest_path.parent`` or
                :obj:`Path.cwd()`.

        Returns:
            A :class:`BenchmarkRunOutput` containing the run ID, records,
            estimates, metrics, leaderboards, and report bundle.

        Raises:
            NotImplementedError: If the manifest mode is not supported.
            ValueError: If the manifest requests unsupported generator
                parameters (e.g. ARFIMA with ``p != 0`` or ``q != 0``).
        """
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

        report_spec = manifest.report_spec or ReportSpec(
            formats=("html", "csv"),
            leaderboards=tuple(manifest.leaderboard_specs),
        )
        if not report_spec.leaderboards and manifest.leaderboard_specs:
            report_spec = replace(report_spec, leaderboards=tuple(manifest.leaderboard_specs))
        export_root = Path(report_spec.export_root)

        manifest = prepare_data_driven_estimators(
            manifest,
            generators=self.generators,
            contaminations=self.contaminations,
            run_id=run_id,
            artefact_root=export_root,
            global_seed=global_seed,
        )

        estimates = run_fit_jobs(
            collect_fit_jobs(records, manifest.estimator_specs),
            estimators=self.estimators,
            execution_spec=dict(manifest.execution_spec),
            cwd=resolve_dir,
        )

        metrics = evaluator.evaluate(manifest, records, estimates)
        boards = self._leaderboard.build(manifest, metrics)

        store_root = export_root / run_id
        store = CsvResultStore(store_root)
        store.write_run_metadata(manifest, run_id)
        store.write_records(records)
        store.write_estimates(estimates)
        store.write_metrics(metrics)
        store.write_leaderboards(boards)

        bundle = self._reporter.build(
            manifest,
            metrics,
            boards,
            report_spec=report_spec,
            run_id=run_id,
        )
        model_artefacts = _ml_model_artefacts(run_id, export_root)
        if model_artefacts:
            bundle = replace(bundle, artefacts=tuple(bundle.artefacts) + model_artefacts)

        store.write_plugin_provenance(self._plugin_provenance)
        store.write_artefacts(bundle.artefacts)
        store_path = store.finalise()
        bundle = replace(bundle, result_store_path=store_path)

        return BenchmarkRunOutput(
            run_id=run_id,
            records=tuple(records),
            estimates=tuple(estimates),
            metrics=metrics,
            leaderboards=boards,
            report_bundle=bundle,
            result_store_path=store_path,
            plugin_provenance=tuple(self._plugin_provenance),
        )

    def preview(
        self,
        manifest: BenchmarkManifest,
        *,
        manifest_path: Path | None = None,
        base_dir: Path | None = None,
    ) -> dict[str, object]:
        """Dry-run preview: materialise records and report grid size without fitting.

        Returns:
            Dictionary with ``mode``, ``n_records``, ``n_estimators``,
            ``n_fit_jobs``, ``n_clean``, ``n_contaminated``, and ``global_seed``.
        """
        if manifest.mode not in (
            BenchmarkMode.GROUND_TRUTH,
            BenchmarkMode.STRESS_TEST,
            BenchmarkMode.OBSERVATIONAL,
        ):
            raise NotImplementedError(
                f"mode {manifest.mode.value!r} is not implemented in this release "
                f"(supported: ground_truth, stress_test, observational)"
            )
        global_seed = int(manifest.seed_spec.get("global_seed", 0))
        resolve_dir = (
            base_dir
            if base_dir is not None
            else (manifest_path.parent if manifest_path is not None else Path.cwd())
        )

        if manifest.mode is BenchmarkMode.GROUND_TRUTH:
            records = self._generate_records_ground_truth(manifest, global_seed)
        elif manifest.mode is BenchmarkMode.STRESS_TEST:
            records = self._generate_records_stress_test(manifest, global_seed)
        else:
            records = load_observational_records(
                manifest, base_dir=resolve_dir, global_seed=global_seed
            )

        n_records = len(records)
        n_estimators = len(manifest.estimator_specs)
        n_clean = sum(1 for r in records if r.annotations.get("stress_role") != "contaminated")
        n_contaminated = n_records - n_clean
        return {
            "mode": manifest.mode.value,
            "n_records": n_records,
            "n_estimators": n_estimators,
            "n_fit_jobs": n_records * n_estimators,
            "n_clean": n_clean,
            "n_contaminated": n_contaminated,
            "global_seed": global_seed,
        }

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


def run_manifest_path(path: str | Path, *, discover_plugins: bool = True) -> BenchmarkRunOutput:
    """Convenience entry-point: load a manifest from disk and run it.

    Args:
        path: Filesystem path to a YAML manifest.
        discover_plugins: Whether to auto-discover third-party estimator
            plugins via environment variables.

    Returns:
        The completed benchmark run output.
    """
    p = Path(path)
    manifest = load_manifest(p)
    return BenchmarkRunner(discover_plugins=discover_plugins).run(manifest, manifest_path=p)


def run_manifest_mapping(
    data: dict[str, Any], *, base_dir: Path | None = None, discover_plugins: bool = True
) -> BenchmarkRunOutput:
    """Convenience entry-point: run a benchmark from an in-memory dictionary.

    This is useful for programmatic benchmark construction or testing.

    Args:
        data: Dictionary matching the manifest schema.
        base_dir: Directory used to resolve relative paths (e.g. CSV files).
        discover_plugins: Whether to auto-discover third-party estimator
            plugins via environment variables.

    Returns:
        The completed benchmark run output.
    """
    manifest = manifest_from_mapping(data)
    return BenchmarkRunner(discover_plugins=discover_plugins).run(
        manifest, base_dir=base_dir or Path.cwd()
    )
