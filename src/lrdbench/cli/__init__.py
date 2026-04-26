from __future__ import annotations

from collections.abc import Sequence


def main(argv: Sequence[str] | None = None) -> int:
    from lrdbench.cli.main import main as _main

    return _main(list(argv) if argv is not None else None)


__all__ = ["main"]
