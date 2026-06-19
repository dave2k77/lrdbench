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
    """Abstract base for synthetic time-series generators.

    Each generator produces a :class:`SeriesRecord` from a parameter dictionary
    and an optional seed. The ``family`` property is the registry key used in
    manifest ``source`` blocks (e.g. ``fGn``, ``ARFIMA``).
    """

    @property
    @abstractmethod
    def family(self) -> str:
        """Registry key for this generator (e.g. ``'fGn'``, ``'ARFIMA'``)."""
        raise NotImplementedError

    @property
    @abstractmethod
    def version(self) -> str:
        """Human-readable version string for provenance tracking."""
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
        """Generate a single synthetic record.

        Args:
            record_id: Stable identifier for the record.
            params: Generator-specific parameters (e.g. ``{'H': 0.75, 'n': 1024}``).
            seed: Optional RNG seed for reproducibility.
            manifest_id: Manifest identifier to embed in provenance.

        Returns:
            A fully populated :class:`SeriesRecord` including truth and provenance.
        """
        raise NotImplementedError


class BaseContamination(ABC):
    """Abstract base for contamination operators.

    A contamination operator transforms a :class:`SeriesRecord` into a new,
    modified record (e.g. by adding outliers, level shifts, or trends).
    The original record must remain untouched; the returned record should
    carry an updated :attr:`contamination_history`.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Registry key for this operator (e.g. ``'outliers'``, ``'level_shift'``)."""
        raise NotImplementedError

    @property
    @abstractmethod
    def family(self) -> str:
        """Broad operator category (e.g. ``'artefact'``, ``'trend'``)."""
        raise NotImplementedError

    @property
    @abstractmethod
    def version(self) -> str:
        """Human-readable version string for provenance tracking."""
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
        """Apply contamination to ``record`` and return a new record.

        Args:
            record: The clean input record.
            params: Operator-specific parameters (e.g. ``{'rate': 0.05}``).
            seed: Optional RNG seed for stochastic operators.
            manifest_id: Manifest identifier to embed in provenance.
            new_record_id: Identifier for the resulting contaminated record.

        Returns:
            A new :class:`SeriesRecord` with updated values, annotations, and
            contamination history.
        """
        raise NotImplementedError


class BasePreprocessing(ABC):
    """Abstract base for preprocessing and correction operators.

    A preprocessing operator transforms a :class:`SeriesRecord` into a new
    record before estimation. Unlike contaminations, these operators represent
    correction hypotheses, including empirical corrections such as rolling
    z-scoring and simulation oracles that use latent components.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Registry key for this operator (e.g. ``'rolling_zscore'``)."""
        raise NotImplementedError

    @property
    @abstractmethod
    def family(self) -> str:
        """Broad correction category (e.g. ``'empirical_variance'``)."""
        raise NotImplementedError

    @property
    @abstractmethod
    def kind(self) -> str:
        """Correction kind, normally ``'empirical'`` or ``'oracle'``."""
        raise NotImplementedError

    @property
    @abstractmethod
    def version(self) -> str:
        """Human-readable version string for provenance tracking."""
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
        """Apply preprocessing to ``record`` and return a new record."""
        raise NotImplementedError


class BaseEstimator(ABC):
    """Abstract base for long-range dependence estimators.

    All estimators enrolled in a benchmark must implement this interface.
    The :meth:`fit` method receives a :class:`SeriesRecord` and must return
    an :class:`EstimateResult` containing at minimum a point estimate and
    a validity flag.
    """

    @property
    @abstractmethod
    def spec(self) -> Any:
        """The estimator's specification (normally an :class:`EstimatorSpec`)."""
        raise NotImplementedError

    @abstractmethod
    def fit(self, record: SeriesRecord) -> EstimateResult:
        """Compute an estimate for the given record.

        Args:
            record: The time-series record to analyse.

        Returns:
            An :class:`EstimateResult` with ``point``, ``valid``, and optional
            confidence intervals, diagnostics, and runtime.
        """
        raise NotImplementedError


class BaseEvaluator(ABC):
    """Abstract base for mode-specific metric evaluation.

    Implementations compute metrics (e.g. bias, MAE, coverage) from the
    aligned records and estimates produced by the benchmark loop.
    """

    @abstractmethod
    def evaluate(
        self,
        manifest: BenchmarkManifest,
        records: Sequence[SeriesRecord],
        estimates: Sequence[EstimateResult],
    ) -> MetricBundle:
        """Evaluate all admissible metrics for the current benchmark mode.

        Args:
            manifest: The validated benchmark manifest.
            records: Materialised source records.
            estimates: Estimator outputs aligned to ``records``.

        Returns:
            A :class:`MetricBundle` containing per-record and aggregate values.
        """
        raise NotImplementedError


class BaseLeaderboardBuilder(ABC):
    """Abstract base for composite ranking (leaderboard) construction.

    Leaderboards aggregate multiple metrics into a single ranking table,
    typically using weighted ranks or weighted scores.
    """

    @abstractmethod
    def build(
        self,
        manifest: BenchmarkManifest,
        metrics: MetricBundle,
    ) -> tuple[Any, ...]:
        """Build leaderboard rows from the evaluated metric bundle.

        Args:
            manifest: The validated benchmark manifest.
            metrics: The metric bundle produced by the evaluator.

        Returns:
            A tuple of leaderboard row objects.
        """
        raise NotImplementedError


class BaseReporter(ABC):
    """Abstract base for report generation.

    Reporters turn metrics and leaderboards into human-readable artefacts
    such as HTML pages, CSV tables, LaTeX snippets, and figures.
    """

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
        """Generate all requested report artefacts.

        Args:
            manifest: The validated benchmark manifest.
            metrics: The evaluated metric bundle.
            leaderboards: Leaderboard rows from the builder.
            report_spec: Specification of desired formats, figures, and tables.
            run_id: Unique identifier for this benchmark run.

        Returns:
            A :class:`ReportBundle` containing paths and metadata for every
            generated artefact.
        """
        raise NotImplementedError


class BaseResultStore(ABC):
    """Abstract base for persisting benchmark outputs.

    Result stores write the raw data of a run (records, estimates, metrics,
    leaderboards, and artefacts) to a structured backend such as a directory
    of CSV files.
    """

    @abstractmethod
    def write_run_metadata(self, manifest: BenchmarkManifest, run_id: str) -> None:
        """Persist manifest metadata and environment snapshot."""
        raise NotImplementedError

    @abstractmethod
    def write_records(self, records: Sequence[SeriesRecord]) -> None:
        """Persist the materialised source records."""
        raise NotImplementedError

    @abstractmethod
    def write_estimates(self, estimates: Sequence[EstimateResult]) -> None:
        """Persist all estimator outputs."""
        raise NotImplementedError

    @abstractmethod
    def write_metrics(self, metrics: MetricBundle) -> None:
        """Persist evaluated metrics."""
        raise NotImplementedError

    @abstractmethod
    def write_leaderboards(self, rows: Sequence[Any]) -> None:
        """Persist leaderboard rows."""
        raise NotImplementedError

    @abstractmethod
    def write_artefacts(self, rows: Sequence[Any]) -> None:
        """Persist report artefact metadata."""
        raise NotImplementedError

    @abstractmethod
    def finalise(self) -> str:
        """Close the store and return the root path or identifier."""
        raise NotImplementedError
