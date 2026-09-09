"""Validate built distribution metadata and required assets without importing lrdbench."""

from __future__ import annotations

import argparse
import ast
import tarfile
import tomllib
import zipfile
from email.parser import BytesParser
from pathlib import Path


def check(dist: Path, tag: str | None = None) -> list[str]:
    root = Path(__file__).resolve().parents[1]
    config = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    wheels = list(dist.glob("*.whl"))
    sources = list(dist.glob("*.tar.gz"))
    if len(wheels) != 1 or len(sources) != 1:
        return [
            "Expected exactly one wheel and one source distribution in a fresh output directory"
        ]
    errors = []
    with zipfile.ZipFile(wheels[0]) as archive:
        wheel = {name: archive.read(name) for name in archive.namelist() if not name.endswith("/")}
    with tarfile.open(sources[0]) as archive:
        source = {}
        for member in archive.getmembers():
            if member.isfile():
                stream = archive.extractfile(member)
                if stream is not None:
                    source[member.name.split("/", 1)[1]] = stream.read()
    metadata_paths = [name for name in wheel if name.endswith(".dist-info/METADATA")]
    if len(metadata_paths) != 1 or "PKG-INFO" not in source:
        return ["Missing distribution metadata"]
    metadata = BytesParser().parsebytes(wheel[metadata_paths[0]])
    source_metadata = BytesParser().parsebytes(source["PKG-INFO"])
    for key, expected in (
        ("Name", config["project"]["name"]),
        ("Requires-Python", config["project"]["requires-python"]),
        ("Description-Content-Type", "text/markdown"),
    ):
        if metadata[key] != expected or source_metadata[key] != expected:
            errors.append(f"Metadata mismatch: {key}")
    init = wheel.get("lrdbench/__init__.py", b"")
    version = None
    for node in ast.parse(init).body:
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == "__version__" for t in node.targets
        ):
            version = ast.literal_eval(node.value)
    if not version or metadata["Version"] != version or source_metadata["Version"] != version:
        errors.append("Wheel, source and import versions differ")
    if tag is not None and tag != f"v{version}":
        errors.append(f"Release tag {tag!r} must equal v{version}")
    if set(metadata.get_all("Provides-Extra", [])) != set(
        config["project"]["optional-dependencies"]
    ):
        errors.append("Optional extras are missing from wheel metadata")
    if not any(
        name.endswith("/licenses/LICENSE") or name.endswith(".dist-info/LICENSE") for name in wheel
    ):
        errors.append("Wheel omits LICENSE")
    entrypoints = next(
        (body for name, body in wheel.items() if name.endswith(".dist-info/entry_points.txt")), b""
    )
    if b"lrdbench = lrdbench.cli.main:main" not in entrypoints:
        errors.append("Missing CLI entry point")
    for origin, destination in config["tool"]["hatch"]["build"]["targets"]["wheel"][
        "force-include"
    ].items():
        path = root / origin
        if not path.exists():
            errors.append(f"Missing configured asset source: {origin}")
            continue
        files = list(path.rglob("*")) if path.is_dir() else [path]
        for asset in files:
            if not asset.is_file():
                continue
            suffix = "/" + asset.relative_to(path).as_posix() if path.is_dir() else ""
            name = destination.removeprefix("src/") + suffix
            if wheel.get(name) != asset.read_bytes():
                errors.append(f"Missing or changed wheel asset: {name}")
            if source.get(asset.relative_to(root).as_posix()) != asset.read_bytes():
                errors.append(f"Missing or changed source asset: {asset}")
    for name in (
        "pyproject.toml",
        "README.md",
        "LICENSE",
        "mkdocs.yml",
        ".readthedocs.yaml",
        "scripts/check_docs.py",
        "scripts/check_dist.py",
        "docs/javascripts/mathjax.js",
        "docs/stylesheets/extra.css",
    ):
        if source.get(name) != (root / name).read_bytes():
            errors.append(f"Missing or changed source-distribution file: {name}")
    if any(
        "openneuro_ds002691_pilot/raw/" in name or name.endswith(".set")
        for name in [*source, *wheel]
    ):
        errors.append("Raw EEG source data must not be distributed")
    return errors


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dist", type=Path)
    parser.add_argument("--tag")
    args = parser.parse_args()
    errors = check(args.dist, args.tag)
    for error in errors:
        print(error)
    if errors:
        raise SystemExit(1)
    print(
        "Distribution audit passed: metadata, versions, CLI, licenses, source files and packaged assets."
    )
