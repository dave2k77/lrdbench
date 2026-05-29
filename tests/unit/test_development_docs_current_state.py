from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DOC = ROOT / "docs" / "current_research_next_steps.md"
HANDOFF = ROOT / "docs" / "development_handoff.md"
MKDOCS = ROOT / "mkdocs.yml"


def test_current_research_next_steps_doc_exists_with_required_sections() -> None:
    text = DOC.read_text(encoding="utf-8")

    required_sections = [
        "# Current Research Next Steps",
        "## Current project state",
        "## Dedicated local environment",
        "## Immediate next actions",
        "## Observational neural-data entry criteria",
        "## Verification commands",
    ]
    missing = [section for section in required_sections if section not in text]

    assert missing == []
    assert "PYTHONPATH=src .venv/Scripts/python.exe" in text
    assert "neural_classical_workstation" in text
    assert "synthetic truth-based claims" in text
    assert "stress-test degradation claims" in text
    assert "observational neural stability" in text


def test_current_research_next_steps_doc_is_linked_from_handoff_and_mkdocs_nav() -> None:
    handoff = HANDOFF.read_text(encoding="utf-8")
    mkdocs = MKDOCS.read_text(encoding="utf-8")

    assert "current_research_next_steps.md" in handoff
    assert "Current research next steps: current_research_next_steps.md" in mkdocs
