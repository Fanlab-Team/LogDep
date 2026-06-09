#!/usr/bin/env python
"""Calculate parser-independent LD from true template-group build reports."""

from __future__ import annotations

import argparse
from pathlib import Path
from statistics import fmean
from typing import Sequence

from build_datasets import DATASETS, normalized_entropy_from_counts, read_csv_rows, write_csv


PROJECT_ROOT = Path(__file__).resolve().parents[1]
LEVELS = [f"0_{index}" for index in range(1, 10)]
FORMULA = "sum_G(|G|^alpha * mean_p(H(X_G,p)/log|G|)) / sum_G(|G|^alpha)"


def project_path(path: Path) -> Path:
    return path if path.is_absolute() else PROJECT_ROOT / path


def target_from_level(level: str) -> float:
    return float(level.replace("_", "."))


def parse_counts(value: str) -> list[int]:
    return [int(part) for part in str(value).split() if part.strip()]


def count_lines(path: Path) -> int:
    if not path.is_file():
        return -1
    with path.open("r", encoding="utf-8", errors="ignore") as file:
        return sum(1 for _line in file)


def calculate_dataset(
    dataset: str,
    target_score: float,
    group_file: Path,
    data_file: Path,
    alpha: float,
) -> dict[str, object]:
    rows = read_csv_rows(group_file)
    weighted_sum = 0.0
    weight_sum = 0.0
    active_groups = 0
    active_group_ld: list[float] = []
    expected_lines = 0

    for row in rows:
        group_size = int(row.get("line_budget", 0) or 0)
        placeholder_count = int(row.get("placeholder_count", 0) or 0)
        active = int(row.get("active", 0) or 0) == 1
        expected_lines += group_size

        slot_ld = normalized_entropy_from_counts(parse_counts(row.get("value_counts", "")))
        group_ld = slot_ld if active and placeholder_count > 0 else 0.0
        group_weight = group_size**alpha if group_size > 0 else 0.0
        weighted_sum += group_weight * group_ld
        weight_sum += group_weight

        if active:
            active_groups += 1
            active_group_ld.append(group_ld)

    ground_truth_ld = weighted_sum / weight_sum if weight_sum else 0.0
    actual_lines = count_lines(data_file)
    return {
        "dataset": dataset,
        "target_score": f"{target_score:.1f}",
        "ground_truth_ld": f"{ground_truth_ld:.10f}",
        "target_error": f"{ground_truth_ld - target_score:.10f}",
        "group_count": len(rows),
        "active_groups": active_groups,
        "active_group_ratio": f"{(active_groups / len(rows)) if rows else 0.0:.10f}",
        "mean_active_group_ld": f"{fmean(active_group_ld) if active_group_ld else 0.0:.10f}",
        "alpha": f"{alpha:.4f}",
        "expected_lines": expected_lines,
        "actual_lines": actual_lines,
        "line_count_matches": int(actual_lines == expected_lines),
        "group_report": str(group_file.relative_to(PROJECT_ROOT)),
        "data_file": str(data_file.relative_to(PROJECT_ROOT)),
    }


def calculate_level(
    level: str,
    reports_root: Path,
    data_root: Path,
    data_prefix: str,
    output_root: Path,
    alpha: float,
    datasets: Sequence[str],
) -> dict[str, object]:
    target_score = target_from_level(level)
    rows = []
    for dataset in datasets:
        group_file = reports_root / f"level_{level}" / "template_groups" / f"{dataset}_groups.csv"
        data_file = data_root / f"{data_prefix}_{level}" / dataset / f"{dataset}.log"
        if not group_file.is_file():
            raise FileNotFoundError(f"Missing true-group report: {group_file}")
        rows.append(calculate_dataset(dataset, target_score, group_file, data_file, alpha))

    fields = list(rows[0].keys())
    level_file = output_root / f"level_{level}.csv"
    write_csv(level_file, rows, fields)

    values = [float(row["ground_truth_ld"]) for row in rows]
    errors = [abs(value - target_score) for value in values]
    return {
        "target_score": f"{target_score:.1f}",
        "actual_ground_truth_ld": f"{fmean(values):.10f}",
        "target_error": f"{fmean(values) - target_score:.10f}",
        "mean_absolute_dataset_error": f"{fmean(errors):.10f}",
        "minimum_dataset_ld": f"{min(values):.10f}",
        "maximum_dataset_ld": f"{max(values):.10f}",
        "datasets": len(rows),
        "alpha": f"{alpha:.4f}",
        "formula": FORMULA,
        "dataset_report": str(level_file.relative_to(PROJECT_ROOT)),
        "data_dir": str((data_root / f"{data_prefix}_{level}").relative_to(PROJECT_ROOT)),
    }


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Calculate the common experiment-axis LD from true template groups."
    )
    parser.add_argument(
        "--build-reports-root",
        type=Path,
        default=Path("results/ground_truth_diversity/build_reports"),
    )
    parser.add_argument("--data-root", type=Path, default=Path("data/gtld"))
    parser.add_argument("--data-prefix", default="diversity")
    parser.add_argument(
        "--output-root",
        type=Path,
        default=Path("results/ground_truth_diversity"),
    )
    parser.add_argument("--levels", nargs="*", default=LEVELS)
    parser.add_argument("--datasets", nargs="*", default=DATASETS)
    parser.add_argument("--alpha", type=float, default=0.5)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    reports_root = project_path(args.build_reports_root)
    data_root = project_path(args.data_root)
    output_root = project_path(args.output_root)
    datasets = [dataset for dataset in args.datasets if dataset in DATASETS]

    calibration_rows = []
    for level in args.levels:
        row = calculate_level(
            level,
            reports_root,
            data_root,
            args.data_prefix,
            output_root,
            args.alpha,
            datasets,
        )
        calibration_rows.append(row)
        print(
            f"[{level}] target={row['target_score']} "
            f"actual_GTLD={row['actual_ground_truth_ld']} "
            f"error={row['target_error']}"
        )

    calibration_file = output_root / "calibration.csv"
    write_csv(calibration_file, calibration_rows, list(calibration_rows[0].keys()))
    print(f"Saved Ground-truth LD calibration: {calibration_file}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
