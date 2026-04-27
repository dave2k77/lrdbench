from __future__ import annotations

from importlib import import_module
from pathlib import Path

import pytest

from lrdbench.output_contract import validate_output_contract

REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.integration
@pytest.mark.parametrize(
    "module_name",
    [
        "examples.quickstart_pure",
        "examples.quickstart_contaminated",
        "examples.quickstart_observational",
        "examples.custom_csv_data",
        "examples.custom_estimator_benchmark",
    ],
)
def test_tutorial_quickstart_examples_generate_valid_outputs(
    module_name: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.syspath_prepend(str(REPO_ROOT))

    module = import_module(module_name)
    module.main()

    stdout = capsys.readouterr().out
    result_store_lines = [
        line.removeprefix("result_store=")
        for line in stdout.splitlines()
        if line.startswith("result_store=")
    ]
    assert result_store_lines
    result_store_path = Path(result_store_lines[-1])
    assert result_store_path.is_dir()
    assert validate_output_contract(result_store_path) == []
    assert "html_report=" in stdout
    assert "validate_output=lrdbench validate-output" in stdout
