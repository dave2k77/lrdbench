"""Versioned research archives with bounded, atomic chunk transactions."""

from __future__ import annotations

import gzip
import io
import json
import os
import uuid
from pathlib import Path

import numpy as np

try:
    from . import run_calibration as shared
except ImportError:
    import run_calibration as shared

SCHEMA = 1
FILES = {"signals.npz", "draws.npz", "metadata.json.gz", "points.jsonl.gz"}


def inside(root, path):
    root, path = Path(root).resolve(), Path(path).resolve()
    if path == root or not path.is_relative_to(root):
        raise ValueError("Archive operation must stay inside its output directory.")
    return path


def write_json_gz(path, value):
    with path.open("wb") as raw:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as zipped:
            zipped.write(shared.canonical(shared.finite_json(value)).encode("utf-8"))
        raw.flush()
        os.fsync(raw.fileno())


def read_json_gz(path):
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        return json.load(handle)


def write_points(path, rows):
    with path.open("wb") as raw:
        with (
            gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as zipped,
            io.TextIOWrapper(zipped, encoding="utf-8", newline="\n") as handle,
        ):
            for row in rows:
                handle.write(shared.canonical(shared.finite_json(row)) + "\n")
        raw.flush()
        os.fsync(raw.fileno())


def read_points(folder):
    with gzip.open(folder / "points.jsonl.gz", "rt", encoding="utf-8") as handle:
        for line in handle:
            yield json.loads(line)


def write_arrays(path, **arrays):
    with path.open("wb") as handle:
        np.savez_compressed(handle, **arrays)
        handle.flush()
        os.fsync(handle.fileno())


def atomic_json(path, value):
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(shared.finite_json(value), indent=2, allow_nan=False) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def begin(output, chunk_id):
    """Keep an interrupted uncommitted chunk as evidence, then recompute it."""
    pending = inside(output, output / "pending" / chunk_id)
    final = inside(output, output / "chunks" / chunk_id)
    if final.exists():
        raise ValueError("A committed chunk cannot be overwritten.")
    if pending.exists():
        abandoned = inside(output, output / "abandoned" / f"{chunk_id}_{uuid.uuid4().hex}")
        abandoned.parent.mkdir(exist_ok=True)
        os.replace(pending, abandoned)
    pending.mkdir(parents=True)
    return pending


def seal(output, chunk_id, *, identity_sha, counts, fault=None):
    pending = inside(output, output / "pending" / chunk_id)
    if {p.name for p in pending.iterdir()} != FILES:
        raise ValueError("Incomplete chunk cannot be committed.")
    receipt = {
        "schema_version": SCHEMA,
        "chunk_id": chunk_id,
        "run_identity_sha256": identity_sha,
        "counts": counts,
        "files": {
            name: {
                "sha256": shared.file_hash(pending / name),
                "bytes": (pending / name).stat().st_size,
            }
            for name in sorted(FILES)
        },
    }
    atomic_json(pending / "receipt.json", {"sha256": shared.digest(receipt), "receipt": receipt})
    verify(pending, identity_sha, chunk_id)
    if fault:
        fault("before_commit", chunk_id)
    final = inside(output, output / "chunks" / chunk_id)
    final.parent.mkdir(exist_ok=True)
    os.replace(pending, final)
    if fault:
        fault("after_commit", chunk_id)
    return receipt


def verify(folder, identity_sha, chunk_id=None):
    """Read-only verification; corruption never silently triggers replacement."""
    if {p.name for p in folder.iterdir()} != FILES | {"receipt.json"}:
        raise ValueError("Committed chunk file set is incomplete or unexpected.")
    envelope = json.loads((folder / "receipt.json").read_text(encoding="utf-8"))
    receipt = envelope["receipt"]
    if (
        envelope["sha256"] != shared.digest(receipt)
        or receipt["schema_version"] != SCHEMA
        or receipt["run_identity_sha256"] != identity_sha
        or (chunk_id is not None and receipt["chunk_id"] != chunk_id)
        or set(receipt["files"]) != FILES
    ):
        raise ValueError("Chunk identity or receipt mismatch.")
    for name, info in receipt["files"].items():
        path = folder / name
        if path.stat().st_size != info["bytes"] or shared.file_hash(path) != info["sha256"]:
            raise ValueError(f"Committed chunk checksum mismatch: {name}")
    return receipt
