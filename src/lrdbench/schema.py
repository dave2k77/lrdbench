from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from lrdbench.enums import BenchmarkMode, OptimisationDirection, SourceType


@dataclass(frozen=True)
class TruthSpec:
    process_family: str
    generating_params: Mapping[str, Any]
    target_estimand: str
    target_value: float | None
    validity_domain: Mapping[str, Any] = field(default_factory=dict)
    notes: str | None = None


@dataclass(frozen=True)
class TransformationRecord:
    name: str
    family: str
    params: Mapping[str, Any]
    severity: str | None = None
    version: str | None = None
    parent_id: str | None = None
    notes: str | None = None


@dataclass(frozen=True)
class ProvenanceRecord:
    record_id: str
    parent_id: str | None
    manifest_id: str | None
    created_at: str
    source_version: str | None = None
    software_version: str | None = None
    git_commit: str | None = None
    seed: int | None = None


@dataclass(frozen=True)
class SeriesRecord:
    record_id: str
    values: np.ndarray
    time_axis: np.ndarray | None
    sampling_rate: float | None
    source_type: SourceType
    source_name: str
    truth: TruthSpec | None = None
    contamination_history: tuple[TransformationRecord, ...] = ()
    preprocessing_history: tuple[TransformationRecord, ...] = ()
    annotations: Mapping[str, Any] = field(default_factory=dict)
    provenance: ProvenanceRecord | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "values", np.asarray(self.values, dtype=float))
        if self.time_axis is not None:
            object.__setattr__(self, "time_axis", np.asarray(self.time_axis, dtype=float))


@dataclass(frozen=True)
class EstimatorSpec:
    name: str
    family: str
    target_estimand: str
    assumptions: tuple[str, ...]
    supports_ci: bool
    supports_diagnostics: bool
    input_requirements: Mapping[str, Any] = field(default_factory=dict)
    parameter_schema: Mapping[str, Any] = field(default_factory=dict)
    reference_citations: tuple[str, ...] = ()
    version: str | None = None


@dataclass(frozen=True)
class EstimateResult:
    record_id: str
    estimator_name: str
    point: float | None
    ci_low: float | None = None
    ci_high: float | None = None
    stderr: float | None = None
    diagnostics: Mapping[str, Any] = field(default_factory=dict)
    runtime_seconds: float | None = None
    valid: bool = True
    warnings: tuple[str, ...] = ()
    failure_reason: str | None = None
    estimator_version: str | None = None
    # Phase 2: symmetric bootstrap CIs per nominal level (alpha, lo, hi), alpha in (0,1)
    bootstrap_cis: tuple[tuple[float, float, float], ...] = ()


@dataclass(frozen=True)
class MetricSpec:
    name: str
    symbol: str
    requires_truth: bool
    admissible_modes: tuple[BenchmarkMode, ...]
    aggregation_rule: str
    optimisation_direction: OptimisationDirection
    unit: str | None = None
    null_policy: str = "explicit_null"
    # Nominal levels (e.g. 0.95) for coverage / ci_width / coverage_error; empty () uses defaults in evaluator
    nominal_levels: tuple[float, ...] = ()
    parameters: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class MetricValue:
    run_id: str
    record_id: str | None
    estimator_name: str
    metric_name: str
    value: float | None
    stratum: Mapping[str, Any] = field(default_factory=dict)
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class MetricBundle:
    per_series: tuple[MetricValue, ...]
    aggregate: tuple[MetricValue, ...]
    uncertainty: tuple[MetricValue, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class LeaderboardSpec:
    mode: BenchmarkMode
    component_metrics: tuple[str, ...]
    weights: Mapping[str, float]
    ranking_rule: str = "weighted_rank"
    tie_break_rule: str = "best_primary_metric"
    name: str | None = None


@dataclass(frozen=True)
class LeaderboardRow:
    run_id: str
    estimator_name: str
    rank: int
    score: float
    component_values: Mapping[str, float | None]
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ReportSpec:
    formats: tuple[str, ...]
    leaderboards: tuple[LeaderboardSpec, ...]
    figure_set: tuple[str, ...] = ()
    table_set: tuple[str, ...] = ()
    include_raw_exports: bool = True
    include_provenance: bool = True
    include_environment: bool = True
    export_root: str = "reports"
    naming_policy: str = "deterministic"
    compression_policy: str | None = None


@dataclass(frozen=True)
class ArtefactRecord:
    artefact_id: str
    run_id: str
    artefact_type: str
    format: str
    path: str
    hash: str | None = None
    created_at: str | None = None
    depends_on: tuple[str, ...] = ()


@dataclass(frozen=True)
class ReportBundle:
    run_id: str
    summary_table_path: str | None = None
    leaderboard_paths: tuple[str, ...] = ()
    figure_paths: tuple[str, ...] = ()
    latex_table_paths: tuple[str, ...] = ()
    html_report_path: str | None = None
    markdown_report_path: str | None = None
    manifest_copy_path: str | None = None
    result_store_path: str | None = None
    artefacts: tuple[ArtefactRecord, ...] = ()


@dataclass(frozen=True)
class BenchmarkManifest:
    manifest_id: str
    name: str
    mode: BenchmarkMode
    source_spec: Mapping[str, Any]
    contamination_spec: Mapping[str, Any] = field(default_factory=dict)
    segmentation_spec: Mapping[str, Any] = field(default_factory=dict)
    preprocessing_spec: Mapping[str, Any] = field(default_factory=dict)
    estimator_specs: tuple[EstimatorSpec, ...] = ()
    metric_specs: tuple[MetricSpec, ...] = ()
    leaderboard_specs: tuple[LeaderboardSpec, ...] = ()
    report_spec: ReportSpec | None = None
    execution_spec: Mapping[str, Any] = field(default_factory=dict)
    uncertainty_spec: Mapping[str, Any] = field(default_factory=dict)
    seed_spec: Mapping[str, Any] = field(default_factory=dict)
    raw_yaml: Mapping[str, Any] | None = None


@dataclass(frozen=True)
class BenchmarkRunOutput:
    run_id: str
    records: tuple[SeriesRecord, ...]
    estimates: tuple[EstimateResult, ...]
    metrics: MetricBundle
    leaderboards: tuple[LeaderboardRow, ...]
    report_bundle: ReportBundle | None
    result_store_path: str | None = None
