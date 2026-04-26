from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from importlib import resources
from pathlib import Path

_SUITE_SUFFIX = ".yaml"


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _source_suite_dir() -> Path:
    return _repo_root() / "configs" / "suites"


def _packaged_suite_dir() -> resources.abc.Traversable:
    return resources.files("lrdbench") / "configs" / "suites"


def list_public_suites() -> tuple[str, ...]:
    names = set()
    source_dir = _source_suite_dir()
    if source_dir.is_dir():
        names.update(path.stem for path in source_dir.glob(f"*{_SUITE_SUFFIX}"))
    packaged_dir = _packaged_suite_dir()
    if packaged_dir.is_dir():
        names.update(
            path.name.removesuffix(_SUITE_SUFFIX)
            for path in packaged_dir.iterdir()
            if path.is_file() and path.name.endswith(_SUITE_SUFFIX)
        )
    return tuple(sorted(names))


@contextmanager
def resolve_manifest_argument(value: str | Path) -> Iterator[Path]:
    path = Path(value)
    if path.is_file():
        yield path
        return

    name = str(value)
    if name.endswith(_SUITE_SUFFIX):
        name = name[: -len(_SUITE_SUFFIX)]

    source_candidate = _source_suite_dir() / f"{name}{_SUITE_SUFFIX}"
    if source_candidate.is_file():
        yield source_candidate
        return

    packaged_candidate = _packaged_suite_dir() / f"{name}{_SUITE_SUFFIX}"
    if packaged_candidate.is_file():
        with resources.as_file(packaged_candidate) as extracted:
            yield extracted
        return

    raise FileNotFoundError(f"manifest file or public suite not found: {value}")
