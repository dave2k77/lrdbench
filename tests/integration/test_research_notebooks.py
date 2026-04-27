from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
NOTEBOOKS = sorted((REPO_ROOT / "notebooks").glob("*.ipynb"))


def _source(cell: dict[str, Any]) -> str:
    src = cell.get("source", "")
    if isinstance(src, list):
        return "".join(src)
    return str(src)


@pytest.mark.integration
@pytest.mark.parametrize("notebook_path", NOTEBOOKS, ids=lambda p: p.name)
def test_research_notebooks_are_clean_and_executable(
    notebook_path: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.syspath_prepend(str(REPO_ROOT))

    nb = json.loads(notebook_path.read_text(encoding="utf-8"))
    assert nb["nbformat"] == 4

    namespace: dict[str, Any] = {
        "__name__": "__notebook__",
        "get_ipython": lambda: SimpleNamespace(run_line_magic=lambda *args, **kwargs: None),
    }
    for index, cell in enumerate(nb["cells"]):
        if cell["cell_type"] == "code":
            assert cell.get("outputs", []) == []
            assert cell.get("execution_count") is None
            code = _source(cell)
            compiled = compile(code, f"{notebook_path.name}::cell_{index}", "exec")
            exec(compiled, namespace)
