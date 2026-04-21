"""Placeholder: point a manifest at your CSV via source.type csv_series_index (see smoke_observational.yaml)."""

from __future__ import annotations


def main() -> None:
    # Build configs/suites/my_run.yaml with:
    #   mode: observational
    #   source:
    #     type: csv_series_index
    #     series: [{ record_id: "a", path: "relative/to/manifest/dir.csv", value_column: "value" }]
    # Then: lrdbench run configs/suites/my_run.yaml
    raise SystemExit("Copy smoke_observational.yaml and adjust paths.")


if __name__ == "__main__":
    main()
