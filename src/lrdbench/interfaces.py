from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping, Sequence
from typing import Any

from lrdbench.schema import (
    BenchmarkManifest,
    EstimateResult,
    MetricBundle,
    ReportBundle,
    ReportSpec,
    SeriesRecord,
)


class BaseGenerator(ABC):
    @property
    @abstractmethod
    def family(self) -> str:
        raise NotImplementedError

    @property
    @abstractmethod
    def version(self) -> str:
        raise NotImplementedError

    @abstractmethod
    def generate(
        self,
        *,
        record_id: str,
        params: Mapping[str, Any],
        seed: int | None,
        manifest_id: str | None,
    ) -> SeriesRecord:
        raise NotImplementedError


class BaseContamination(ABC):
    """Contamination operator: SeriesRecord -> SeriesRecord (contract §1.11)."""

    @property
    @abstractmethod
    def name(self) -> str:
        raise NotImplementedError

    @property
    @abstractmethod
    def family(self) -> str:
        raise NotImplementedError

    @property
    @abstractmethod
    def version(self) -> str:
        raise NotImplementedError

    @abstractmethod
    def apply(
        self,
        record: SeriesRecord,
        *,
        params: Mapping[str, Any],
        seed: int | None,
        manifest_id: str | None,
        new_record_id: str,
    ) -> SeriesRecord:
        raise NotImplementedError


class BaseEstimator(ABC):
    @property
    @abstractmethod
    def spec(self) -> Any:
        raise NotImplementedError

    @abstractmethod
    def fit(self, record: SeriesRecord) -> EstimateResult:
        raise NotImplementedError


class BaseEvaluator(ABC):
    @abstractmethod
    def evaluate(
        self,
        manifest: BenchmarkManifest,
        records: Sequence[SeriesRecord],
        estimates: Sequence[EstimateResult],
    ) -> MetricBundle:
        raise NotImplementedError


class BaseLeaderboardBuilder(ABC):
    @abstractmethod
    def build(
        self,
        manifest: BenchmarkManifest,
        metrics: MetricBundle,
    ) -> tuple[Any, ...]:
        raise NotImplementedError


class BaseReporter(ABC):
    @abstractmethod
    def build(
        self,
        manifest: BenchmarkManifest,
        metrics: MetricBundle,
        leaderboards: Sequence[Any],
        *,
        report_spec: ReportSpec,
        run_id: str,
    ) -> ReportBundle:
        raise NotImplementedError


class BaseResultStore(ABC):
    @abstractmethod
    def write_run_metadata(self, manifest: BenchmarkManifest, run_id: str) -> None:
        raise NotImplementedError

    @abstractmethod
    def write_records(self, records: Sequence[SeriesRecord]) -> None:
        raise NotImplementedError

    @abstractmethod
    def write_estimates(self, estimates: Sequence[EstimateResult]) -> None:
        raise NotImplementedError

    @abstractmethod
    def write_metrics(self, metrics: MetricBundle) -> None:
        raise NotImplementedError

    @abstractmethod
    def write_leaderboards(self, rows: Sequence[Any]) -> None:
        raise NotImplementedError

    @abstractmethod
    def write_artefacts(self, rows: Sequence[Any]) -> None:
        raise NotImplementedError

    @abstractmethod
    def finalise(self) -> str:
        raise NotImplementedError
