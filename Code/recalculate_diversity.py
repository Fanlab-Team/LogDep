#!/usr/bin/env python
"""Recalculate the legacy Brain-grouped diversity diagnostic.

This script is retained for development traceability. The current common
experiment axis is calculated by ``ground_truth_diversity.py``.
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path
from statistics import fmean

from diversity_metrics import DATASETS, calculate_dataset, write_summary
from eval_brain import LEVELS


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RESULTS_ROOT = PROJECT_ROOT / "results" / "diversity"


def read_existing_calibration(path: Path) -> dict[str, dict[str, str]]:
    if not path.is_file():
        return {}
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        return {
            row["target_score"]: row
            for row in csv.DictReader(file)
            if row.get("target_score")
        }


def write_calibration(rows: list[dict[str, str]], path: Path) -> None:
    fields = [
        "target_score",
        "activation_ratio",
        "calibrated_slot_entropy",
        "actual_content_weighted_entropy_diversity",
        "avg_distinct_values_per_variable",
        "diversity_file",
        "data_dir",
        "next_test_data_dir",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Recalculate the content-only benchmark-axis LD values."
    )
    parser.add_argument("--levels", nargs="*", default=LEVELS)
    parser.add_argument("--datasets", nargs="*", default=DATASETS)
    parser.add_argument("--data-root", type=Path, default=PROJECT_ROOT / "data")
    parser.add_argument("--results-root", type=Path, default=DEFAULT_RESULTS_ROOT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    calibration_path = args.results_root / "calibration.csv"
    existing = read_existing_calibration(calibration_path)
    calibration_rows: list[dict[str, str]] = []

    for level in args.levels:
        target = "0." + level.split("_")[1]
        data_dir = args.data_root / f"diversity_{level}"
        output_file = (
            args.results_root / "content_diversity" / f"content_entropy_{level}.csv"
        )
        detail_dir = args.results_root / "content_diversity" / f"details_{level}"
        rows = []
        for dataset in args.datasets:
            log_file = data_dir / dataset / f"{dataset}.log"
            print(f"[LD {target}] {dataset}")
            rows.append(
                calculate_dataset(
                    dataset,
                    log_file,
                    details_dir=detail_dir,
                    scope="content",
                )
            )
        write_summary(rows, output_file)

        weighted_ld = fmean(row["weighted_entropy_diversity"] for row in rows)
        avg_distinct = fmean(row["avg_distinct_values_per_variable"] for row in rows)
        old = existing.get(target, {})
        calibration_rows.append(
            {
                "target_score": target,
                "activation_ratio": old.get("activation_ratio", target),
                "calibrated_slot_entropy": old.get("calibrated_slot_entropy", target),
                "actual_content_weighted_entropy_diversity": f"{weighted_ld:.10f}",
                "avg_distinct_values_per_variable": f"{avg_distinct:.10f}",
                "diversity_file": str(output_file.relative_to(PROJECT_ROOT)),
                "data_dir": str(data_dir.relative_to(PROJECT_ROOT)),
                "next_test_data_dir": str(data_dir.relative_to(PROJECT_ROOT)),
            }
        )
        print(f"  actual_content_weighted_entropy_diversity={weighted_ld:.10f}")

    write_calibration(calibration_rows, calibration_path)
    print(f"Saved calibration: {calibration_path}")


if __name__ == "__main__":
    main()
