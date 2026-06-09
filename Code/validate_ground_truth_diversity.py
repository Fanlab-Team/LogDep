#!/usr/bin/env python
"""Validate the parser-independent Ground-truth LD benchmark artifacts."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence

from build_datasets import DATASETS, read_csv_rows
from ground_truth_diversity import LEVELS, project_path


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate Ground-truth LD datasets and reports.")
    parser.add_argument("--data-root", type=Path, default=Path("data/gtld"))
    parser.add_argument(
        "--results-root",
        type=Path,
        default=Path("results/ground_truth_diversity"),
    )
    parser.add_argument("--levels", nargs="*", default=LEVELS)
    parser.add_argument("--datasets", nargs="*", default=DATASETS)
    parser.add_argument("--tolerance", type=float, default=0.005)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    data_root = project_path(args.data_root)
    results_root = project_path(args.results_root)
    datasets = [dataset for dataset in args.datasets if dataset in DATASETS]
    errors: list[str] = []

    calibration_file = results_root / "calibration.csv"
    calibration = read_csv_rows(calibration_file)
    calibration_by_target = {row["target_score"]: row for row in calibration}
    for level in args.levels:
        target = f"{float(level.replace('_', '.')):.1f}"
        row = calibration_by_target.get(target)
        if row is None:
            errors.append(f"Missing calibration row for {target}")
            continue
        target_error = abs(float(row["target_error"]))
        if target_error > args.tolerance:
            errors.append(f"GTLD target error {target_error:.6f} exceeds tolerance at {target}")

        level_report = results_root / f"level_{level}.csv"
        for dataset_row in read_csv_rows(level_report):
            if dataset_row.get("dataset") in datasets and dataset_row.get("line_count_matches") != "1":
                errors.append(f"Line-count mismatch: {level} {dataset_row.get('dataset')}")

        for dataset in datasets:
            dataset_dir = data_root / f"diversity_{level}" / dataset
            files = [path.name for path in dataset_dir.iterdir() if path.is_file()]
            if files != [f"{dataset}.log"]:
                errors.append(
                    f"Parser input directory contains non-raw artifacts: {dataset_dir} -> {files}"
                )

    for dataset in datasets:
        previous_active: set[str] = set()
        for level in args.levels:
            group_file = (
                results_root
                / "build_reports"
                / f"level_{level}"
                / "template_groups"
                / f"{dataset}_groups.csv"
            )
            active = {
                row["event_id"]
                for row in read_csv_rows(group_file)
                if row.get("active") == "1"
            }
            if not previous_active.issubset(active):
                errors.append(f"Active true-template groups are not nested: {dataset} at {level}")
            previous_active = active

    if errors:
        for error in errors:
            print(f"[FAIL] {error}")
        return 1

    print(
        f"[PASS] {len(args.levels)} levels x {len(datasets)} datasets: "
        "GTLD targets, line counts, raw-only parser inputs, and nested groups are valid."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
