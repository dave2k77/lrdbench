# Rebuilt benchmark manuscript

This package rebuilds the paper from the audited confirmation experiment. The manuscript is a synthetic increment study; it contains no empirical EEG validation, calibrated LRD test or universal estimator ranking. The original draft and design PDFs are unchanged.

The editable deliverable is `lrdbench-manuscript-v3.docx` in the workspace's `rebuilt-manuscript` directory. Its main text is approximately 5,800 words including abstract, references excluded. It contains four main tables, two main figures, a methods supplement and three complete stress-profile figures. Table S1 occupies two physical tables across two pages.

## Sources and generation

- `manuscript.template.md` is the editable prose source, with named numeric insertions and explicit table, figure and equation placement commands.
- `manuscript.md` is the resolved typesetting source. Placement commands are consumed by the Word builder; this is not a separate finished reading edition.
- `prepare_assets.py` checks the audited export hashes, inserts numeric statements, and generates the tables and PNG/SVG figures. It imports no producer modules and reruns no benchmark fits. `tables/evidence_map.csv` maps all insertions and figure/table values to their source rows.
- `build_docx.py` builds the Word document with editable text, tables and native equations, using `document_data.json`, `references.json` and `equations.omml.json`.
- `build_equations.py` is an optional regeneration utility using Microsoft's installed MathML transform. The resulting OMML is included, so Office is not needed for ordinary document rebuilding.
- `verify_manuscript.py` reconciles the source rows, checks all seven compressed export hashes, tests workload identities and boundary/coverage counts, and checks the Word structure. Visual review is separate.
- `verification.json` records the passing checks for the delivered Word file; `visual_review.json` records the completed 24-page visual review and exact artifact hashes.
- `references.json` records DOI links, the primary pages consulted, and limits to full-text access. No performance conclusion is borrowed from an inaccessible article.
- `claim_closure.csv` maps the 13 legacy manuscript dispositions to the new text. The original audit claim ledger remains unchanged.

Inputs are read from `../remediation/confirmation_audit/results/` and `../remediation/protocol-v1/`. The six complete cell/domain exports contain all 118,917 canonical rows. The additional planned-contrast export overlaps those rows. Do not add its row count to the canonical total.

The producer revision is `9c02d04`, the results-audit revision is `b3d0648`, and the run identity is `43d0a7f75c8afab6d32ab6fd1f2ff8db49cca59e36971e2b74404173f4cbfcf2`. The canonical summary hash is `95b8e938fb98a674c7ba2e92b7d59ed0f909ffd6ae2e8585c90a0f23f7c01504`. These are local provenance identifiers, not a public archival DOI.

## Rebuilding

Run `prepare_assets.py` using the pinned scientific environment (NumPy, pandas and Matplotlib). In the current workspace this is `tmp/calibration-locked-venv/Scripts/python.exe`. Use the Codex bundled document Python for `build_docx.py` and `verify_manuscript.py` (python-docx, lxml and pypdf). From the workspace root:

```powershell
& '.\tmp\calibration-locked-venv\Scripts\python.exe' 'lrdbench\benchmark_experiment\manuscript_v3\prepare_assets.py'
& $documentPython 'lrdbench\benchmark_experiment\manuscript_v3\build_docx.py' --output 'rebuilt-manuscript\lrdbench-manuscript-v3.docx'
& $documentPython 'lrdbench\benchmark_experiment\manuscript_v3\verify_manuscript.py' --docx 'rebuilt-manuscript\lrdbench-manuscript-v3.docx'
```

Set `$documentPython` to the bundled Python path returned by the workspace dependency loader. The build separates the scientific plotting environment from the document environment; the latter need not contain pandas or Matplotlib. A supplied path containing spaces must be quoted as above. Word archive timestamps can vary between builds; evidence hashes identify the exact delivered file, while the numeric source values and declared settings remain fixed.

Render with the documents skill's `render_docx.py` at 160 DPI, then inspect every page. This workstation used a signed LibreOffice 24.8.7.2 package extracted locally under `tmp/manuscript-renderer/LibreOffice`, without systemwide installation. Its `program` directory was added to the Python process PATH before running the canonical renderer, because the managed Python startup resets an inherited shell PATH. Intermediate rendered PDFs and page PNGs remain under `tmp/manuscript-qa`, outside this source package. After rendering, pass the PDF path to `verify_manuscript.py --pdf ...` for page inventory and content checks; these do not replace visual review.

## Editorial and release status

The draft uses the supplied author name and affiliation and a general single-column manuscript format. A target journal, corresponding-author contact, funding and competing-interest statements were not supplied. These must be completed from the author's information before submission. No declarations were invented.

Status reviewed 9 September 2026: the source revisions and complete summary exports are now public on `main`, merged in [PR #3](https://github.com/dave2k77/lrdbench/pull/3). The full raw confirmation archive has not been deposited publicly and remains in its verified production location. The delivered draft dated 8 September and its compact source ZIP preserve their original build state; their availability wording predates the merge and must be updated during the next editorial revision. The compact ZIP includes summary exports, not the much larger raw per-record bootstrap archive. Public deposition and journal-specific formatting remain publication work. See the [current confirmation guide](../../docs/confirmation_benchmark.md).
