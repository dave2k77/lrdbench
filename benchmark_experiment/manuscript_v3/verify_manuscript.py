"""Reconcile manuscript assets against immutable exports and inspect OOXML.

Uses the bundled document Python. Rendering and page-by-page visual review are
separate mandatory checks; this does not infer visual quality from text.
"""

import argparse
import csv
import gzip
import hashlib
import json
import math
import re
from pathlib import Path
from zipfile import ZipFile

from lxml import etree
from pypdf import PdfReader

HERE = Path(__file__).resolve().parent
SOURCE = HERE.parent / "remediation/confirmation_audit/results"
KEY = ["scope", "cell", "domain", "interval_role", "method", "condition", "metric", "contrast"]


def readcsv(path):
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def main(docx, pdf):
    provenance = json.loads((SOURCE / "export_provenance.json").read_text(encoding="utf-8"))
    fullfiles = [
        f"{scope}_{kind}.csv.gz"
        for scope in ["accuracy", "stress", "intervals"]
        for kind in ["cells", "domains"]
    ]
    files = fullfiles + ["planned_contrasts.csv.gz"]
    maps = {}
    rowcounts = {}
    for name in files:
        assert (
            hashlib.sha256((SOURCE / name).read_bytes()).hexdigest() == provenance["files"][name]
        ), name
        rows = readcsv(SOURCE / name)
        rowcounts[name] = len(rows)
        maps[name] = {tuple(r[k] for k in KEY): r for r in rows}
        assert len(maps[name]) == len(rows), ("duplicate source key", name)
    assert sum(rowcounts[n] for n in fullfiles) == 118917
    evidence = readcsv(HERE / "tables/evidence_map.csv")
    for r in evidence:
        src = maps[r["source_file"]][tuple(r[k] for k in KEY)]
        for col in ["value", "ci_low", "ci_high"]:
            actual = float(r[col])
            expected = float(src[col])
            assert math.isclose(actual, expected, rel_tol=1e-13, abs_tol=1e-14), (
                r["evidence_id"],
                col,
            )
    for key, expected in [
        ("clean_fGn", 252),
        ("clean_ARFIMA", 189),
        ("clean_AR1", 252),
        ("coverage", 160),
        ("stress_fGn", 483),
        ("stress_ARFIMA", 483),
        ("stress_AR1", 483),
    ]:
        rows = readcsv(HERE / f"tables/figure_{key}_source.csv")
        assert len(rows) == expected, (key, len(rows))
    audit = json.loads((SOURCE / "audit_evidence.json").read_text(encoding="utf-8"))
    counts = audit["counts"]
    assert counts["parents"] == 33 * 2000 == 66000
    assert counts["descendants"] == 14 * 500 * 23 == 161000
    assert counts["point_fits"] == 21 * (66000 + 161000) == counts["valid_point_fits"] == 4767000
    assert counts["interval_parents"] == 7 * 2000 + 3 * 500 == 15500
    assert counts["interval_rows"] == counts["available_intervals"] == 15500 * 16 == 248000
    assert counts["physical_bootstrap_records"] == 15500 * 2 * 1999 == 61969000
    assert counts["statistic_attempts"] == counts["statistic_used"] == 15500 * 1999 * 9 == 278860500
    assert 15500 * 6 == 93000
    for f in ["statistic_failed", "statistic_invalid", "statistic_unattempted"]:
        assert counts[f] == 0
    intervals = maps["intervals_cells.csv.gz"]
    rows = list(intervals.values())
    for cell, successes, denominator in [
        ("AR1_0.8_n512", 1971, 2000),
        ("AR1_0.95_n512", 2000, 2000),
        ("AR1_0.95_n1024", 500, 500),
    ]:
        match = [
            r
            for r in rows
            if r["cell"] == cell and r["metric"] == "model_boundary_rate_all_attempts"
        ]
        assert len(match) == 1
        assert (
            float(match[0]["successes"]) == successes
            and float(match[0]["denominator"]) == denominator
        )
        for method in ["Higuchi", "GHE"]:
            c = [
                r
                for r in rows
                if r["cell"] == cell
                and r["method"] == method
                and r["condition"] == "unknown_fgn_centered_basic"
                and r["metric"] == "unconditional_coverage"
            ][0]
            assert float(c["value"]) == 0 and float(c["ci_high"]) > 0
    refs = json.loads((HERE / "references.json").read_text(encoding="utf-8"))
    text = (HERE / "manuscript.md").read_text(encoding="utf-8")
    assert {int(x) for x in re.findall(r"\[(\d+)\]", text)} == {r["id"] for r in refs}
    assert not re.search(r"\{\{\w+\}\}", text)
    ns = {
        "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
        "m": "http://schemas.openxmlformats.org/officeDocument/2006/math",
    }
    with ZipFile(docx) as z:
        doc = etree.fromstring(z.read("word/document.xml"))
        styles = etree.fromstring(z.read("word/styles.xml"))
        assert len(doc.findall(".//w:tbl", ns)) == 6
        assert len(doc.findall(".//m:oMath", ns)) == 6
        assert not styles.findall(".//w:pBdr", ns)
        assert not doc.findall(".//w:pBdr", ns)
        assert len(doc.findall(".//w:tblHeader", ns)) == 6
        assert len([n for n in z.namelist() if n.startswith("word/media/")]) == 5
    report = {
        "status": "passed",
        "source_run": provenance["run_identity_sha256"],
        "canonical_rows": 118917,
        "audited_inputs_verified": files,
        "evidence_rows_reconciled": len(evidence),
        "figure_cells_checked": 2302,
        "physical_tables": 6,
        "logical_tables": 5,
        "figures": 5,
        "references": 15,
        "native_equations": 6,
        "docx_sha256": hashlib.sha256(docx.read_bytes()).hexdigest(),
        "visual_review": "separate page-by-page check required",
    }
    if pdf:
        reader = PdfReader(pdf)
        report["rendered_pages"] = len(reader.pages)
        pageinfo = []
        for i, page in enumerate(reader.pages, 1):
            t = page.extract_text()
            assert len(t) > 80, ("unexpected blank page", i)
            assert "\ufffd" not in t, ("replacement glyph", i)
            pageinfo.append(
                {
                    "page": i,
                    "width_pt": float(page.mediabox.width),
                    "height_pt": float(page.mediabox.height),
                    "text_characters": len(t),
                    "start": t[:130],
                }
            )
        (HERE / "page_inventory.json").write_text(
            json.dumps(pageinfo, ensure_ascii=False, indent=2), encoding="utf-8", newline="\n"
        )
        report["pdf_sha256"] = hashlib.sha256(pdf.read_bytes()).hexdigest()
    (HERE / "verification.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8", newline="\n"
    )
    print(json.dumps(report))


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--docx", type=Path, required=True)
    p.add_argument("--pdf", type=Path)
    args = p.parse_args()
    main(args.docx.resolve(), args.pdf.resolve() if args.pdf else None)
