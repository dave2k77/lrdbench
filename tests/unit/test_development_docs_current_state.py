from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
DOC = ROOT / "docs" / "current_research_next_steps.md"
HANDOFF = ROOT / "docs" / "development_handoff.md"
MKDOCS = ROOT / "mkdocs.yml"


def test_current_research_next_steps_doc_exists_with_required_sections() -> None:
    text = DOC.read_text(encoding="utf-8")

    required_sections = [
        "# Current research next steps",
        "## Current state",
        "## Next publication work",
        "## Library maintenance",
        "## Future observational work",
    ]
    missing = [section for section in required_sections if section not in text]

    assert missing == []
    assert "confirmation_benchmark.md" in text
    assert "python -m pytest" in text
    assert "neural_classical_workstation" in text
    assert "frozen environment" in text
    assert "archive identifier only after the deposit exists" in text
    assert "no known H target or accuracy/coverage ground truth" in text


def test_current_research_next_steps_doc_is_linked_from_handoff_and_mkdocs_nav() -> None:
    handoff = HANDOFF.read_text(encoding="utf-8")
    mkdocs = yaml.safe_load(MKDOCS.read_text(encoding="utf-8"))

    assert "current_research_next_steps.md" in handoff
    research = next(section["Research"] for section in mkdocs["nav"] if "Research" in section)
    assert any("current_research_next_steps.md" in item.values() for item in research)
