"""Check built documentation against navigation, search and export-contract sources."""

from __future__ import annotations

import json
import sys
from contextlib import suppress
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit

import yaml


class Page(HTMLParser):
    def __init__(self, text: str):
        super().__init__()
        self.ids: set[str] = set()
        self.links: list[str] = []
        self.h1 = 0
        self.code: list[str] = []
        self._code: list[str] | None = None
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if "id" in attrs:
            self.ids.add(attrs["id"])
        if tag == "h1":
            self.h1 += 1
        if tag == "a" and "href" in attrs:
            self.links.append(attrs["href"])
        if tag == "code":
            self._code = []

    def handle_data(self, data):
        if self._code is not None:
            self._code.append(data)

    def handle_endtag(self, tag):
        if tag == "code" and self._code is not None:
            self.code.append("".join(self._code))
            self._code = None


def nav_paths(items):
    for item in items:
        for value in item.values():
            if isinstance(value, str):
                yield value
            else:
                yield from nav_paths(value)


def check(site: Path, base_path: str = "/") -> list[str]:
    root = Path(__file__).resolve().parents[1]
    config = yaml.safe_load((root / "mkdocs.yml").read_text(encoding="utf-8"))
    sources = {p.relative_to(root / "docs").as_posix() for p in (root / "docs").rglob("*.md")}
    nav = list(nav_paths(config["nav"]))
    errors = []
    if set(nav) != sources or len(nav) != len(set(nav)):
        errors.append(
            f"Navigation mismatch: missing={sources - set(nav)}, extra={set(nav) - sources}, duplicates={len(nav) - len(set(nav))}"
        )
    pages = {p.resolve(): Page(p.read_text(encoding="utf-8")) for p in site.rglob("*.html")}
    if not pages:
        return errors + ["No built HTML pages found"]
    for path, page in pages.items():
        if page.h1 != 1:
            errors.append(f"{path.relative_to(site)}: expected one H1, found {page.h1}")
        for href in page.links:
            url = urlsplit(href)
            if url.scheme or url.netloc:
                continue
            local_path = unquote(url.path)
            if local_path.startswith(base_path) and base_path != "/":
                local_path = "/" + local_path[len(base_path) :]
            target = (
                (
                    site / local_path.lstrip("/")
                    if local_path.startswith("/")
                    else path.parent / local_path
                )
                if url.path
                else path
            )
            if target.is_dir():
                target /= "index.html"
            target = target.resolve()
            if not target.exists():
                errors.append(f"{path.relative_to(site)}: missing local link {href}")
            elif (
                url.fragment and target in pages and unquote(url.fragment) not in pages[target].ids
            ):
                errors.append(f"{path.relative_to(site)}: missing anchor {href}")
    contract = json.loads((root / "configs/contracts/public_output_contract.json").read_text())
    contract_page = pages.get((site / "output_contract/index.html").resolve())
    candidates = []
    for code in contract_page.code if contract_page else []:
        with suppress(ValueError):
            candidates.append(json.loads(code))
    if contract not in candidates:
        errors.append("Rendered output contract differs from tracked JSON")
    search = json.loads((site / "search/search_index.json").read_text(encoding="utf-8"))
    locations = [entry["location"] for entry in search["docs"]]
    for name in sources:
        source = (root / "docs" / name).read_text(encoding="utf-8")
        if source.startswith("---"):
            meta = yaml.safe_load(source.split("---", 2)[1]) or {}
            if meta.get("search", {}).get("exclude") and any(
                loc.startswith(name[:-3] + "/") for loc in locations
            ):
                errors.append(f"Historical page still indexed: {name}")
    for name in (
        "parameter_glossary",
        "interpretation_semantics",
        "tutorials/estimand_triangle_and_discrimination",
    ):
        text = (site / name / "index.html").read_text(encoding="utf-8")
        if (
            'class="arithmatex"' not in text
            or "mathjax@3.2.2" not in text
            or "javascripts/mathjax.js" not in text
        ):
            errors.append(f"Missing math markup/assets: {name}")
    return errors


if __name__ == "__main__":
    site = Path(sys.argv[1] if len(sys.argv) > 1 else "site").resolve()
    base_path = sys.argv[2] if len(sys.argv) > 2 else "/"
    if not (base_path.startswith("/") and base_path.endswith("/")):
        raise SystemExit("Base path must start and end with '/'")
    errors = check(site, base_path)
    for error in errors:
        print(error)
    if errors:
        raise SystemExit(1)
    print(
        "Documentation audit passed: navigation, H1 headings, local links/anchors, contract, math assets and search exclusions."
    )
