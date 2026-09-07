"""Run the validated fixed experiment, then produce its canonical summaries.

This orchestration wrapper is covered by the release evidence manifest. It adds
no scientific settings and does not change the frozen execution-source identity.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))


def main():
    from benchmark_experiment.remediation import run_confirmation as engine
    from benchmark_experiment.remediation import summarize_confirmation as reporting

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    output = args.output.resolve()
    frozen = engine.load_lock()
    identity = engine.run_identity(frozen, rehearsal=False)
    engine.check_release(identity)
    capacity = engine.disk_check(output, initial=not (output / "run.json").exists())
    if args.dry_run:
        print(
            json.dumps(
                {
                    "runtime_sha256": identity["runtime_sha256"],
                    "workload": frozen["design"]["workload"],
                    "disk": capacity,
                    "generated_inputs": 0,
                },
                indent=2,
            )
        )
        return
    guard = output.with_name(output.name + "-job-guard")
    guard.mkdir(parents=True, exist_ok=True)
    state_path = output.with_name(output.name + "-job.json")
    with engine.shared.exclusive_run(guard):
        state = {
            "pid": os.getpid(),
            "output": str(output),
            "started_utc": dt.datetime.now(dt.UTC).isoformat(),
            "runtime_sha256": identity["runtime_sha256"],
            "scientific_design_sha256": frozen["sha256"],
            "stage": "running_fixed_confirmation_fits",
        }
        engine.store.atomic_json(state_path, state)
        try:
            result = engine.run(output)
            if not result["complete"]:
                raise RuntimeError("The full executor returned an incomplete fixed run.")
            state.update(stage="building_canonical_summaries", fit_counts=result["counts"])
            engine.store.atomic_json(state_path, state)
            summary = reporting.summarize(output)
            state.update(
                stage="fits_and_summaries_complete_independent_full_run_audit_pending",
                completed_utc=dt.datetime.now(dt.UTC).isoformat(),
                summary_groups=summary["groups"],
                summary_rows=summary["summary_rows"],
            )
            engine.store.atomic_json(state_path, state)
            print(json.dumps(state, indent=2), flush=True)
        except BaseException as exc:
            state.update(
                stage="stopped_requires_resume_or_investigation",
                stopped_utc=dt.datetime.now(dt.UTC).isoformat(),
                error=f"{type(exc).__name__}: {exc}",
            )
            engine.store.atomic_json(state_path, state)
            raise


if __name__ == "__main__":
    main()
