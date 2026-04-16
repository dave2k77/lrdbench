from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Generic, TypeVar

from lrdbench.interfaces import BaseContamination, BaseEstimator, BaseGenerator

if TYPE_CHECKING:
    from lrdbench.schema import EstimatorSpec

T = TypeVar("T")


class Registry(Generic[T]):
    def __init__(self) -> None:
        self._items: dict[str, T] = {}

    def register(self, name: str, obj: T) -> None:
        key = name.strip()
        if not key:
            raise ValueError("registry name must be non-empty")
        self._items[key] = obj

    def get(self, name: str) -> T:
        if name not in self._items:
            raise KeyError(f"unknown registry entry: {name!r}")
        return self._items[name]

    def list(self) -> tuple[str, ...]:
        return tuple(sorted(self._items))


class GeneratorRegistry(Registry[BaseGenerator]):
    pass


class ContaminationRegistry(Registry[BaseContamination]):
    pass


EstimatorBuilder = Callable[["EstimatorSpec"], BaseEstimator]


class EstimatorRegistry(Registry[EstimatorBuilder]):
    """Callable(spec: EstimatorSpec) -> BaseEstimator."""

    pass
