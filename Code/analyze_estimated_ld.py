#!/usr/bin/env python
"""Compare LogDep runtime Estimated LD with the offline Ground-truth LD axis."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path
from statistics import fmean
from typing import Sequence

from build_datasets import DATASETS, read_csv_rows, write_csv
from ground_truth_diversity import LEVELS, project_path


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Analyze LogDep Estimated LD errors.")
    parser.add_argument(
        "--ground-truth-root",
        type=Path,
        default=Path("results/ground_truth_diversity"),
    )
    parser.add_argument(
        "--logdep-run-root",
        type=Path,
        default=Path("results/parser_runs/gtld/parser_eval/LogDepFull"),
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=Path("results/parser_runs/gtld/estimated_ld_analysis"),
    )
    parser.add_argument("--levels", nargs="*", default=LEVELS)
    parser.add_argument("--datasets", nargs="*", default=DATASETS)
    parser.add_argument("--trigger-ld", type=float, default=0.35)
    parser.add_argument("--strict", action="store_true")
    return parser.parse_args(argv)


def read_iteration(path: Path) -> dict[str, str] | None:
    if not path.is_file():
        return None
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        return next(csv.DictReader(file), None)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    ground_truth_root = project_path(args.ground_truth_root)
    logdep_run_root = project_path(args.logdep_run_root)
    output_root = project_path(args.output_root)
    datasets = [dataset for dataset in args.datasets if dataset in DATASETS]

    detail_rows: list[dict[str, object]] = []
    summary_rows: list[dict[str, object]] = []
    for level in args.levels:
        target_score = float(level.replace("_", "."))
        gt_rows = {
            row["dataset"]: row
            for row in read_csv_rows(ground_truth_root / f"level_{level}.csv")
        }
        level_details = []
        for dataset in datasets:
            iteration_file = (
                logdep_run_root
                / f"diversity_{level}"
                / dataset
                / f"{dataset}_logdepfull_iterations.csv"
            )
            iteration = read_iteration(iteration_file)
            if iteration is None:
                if args.strict:
                    raise FileNotFoundError(f"Missing LogDep iteration report: {iteration_file}")
                continue

            ground_truth_ld = float(gt_rows[dataset]["ground_truth_ld"])
            estimated_ld = float(iteration["estimated_ld"])
            error = estimated_ld - ground_truth_ld
            row = {
                "target_score": f"{target_score:.1f}",
                "dataset": dataset,
                "ground_truth_ld": f"{ground_truth_ld:.10f}",
                "estimated_ld": f"{estimated_ld:.10f}",
                "signed_error": f"{error:.10f}",
                "absolute_error": f"{abs(error):.10f}",
                "ground_truth_low_diversity": int(ground_truth_ld <= args.trigger_ld),
                "estimated_low_diversity": int(estimated_ld <= args.trigger_ld),
                "trigger_agrees": int(
                    (ground_truth_ld <= args.trigger_ld) == (estimated_ld <= args.trigger_ld)
                ),
                "ld_source": iteration.get("ld_source", ""),
                "iteration_file": str(iteration_file.relative_to(project_path(Path(".")))),
            }
            detail_rows.append(row)
            level_details.append(row)

        if level_details:
            summary_rows.append(
                {
                    "target_score": f"{target_score:.1f}",
                    "datasets": len(level_details),
                    "mean_ground_truth_ld": f"{fmean(float(row['ground_truth_ld']) for row in level_details):.10f}",
                    "mean_estimated_ld": f"{fmean(float(row['estimated_ld']) for row in level_details):.10f}",
                    "mean_absolute_error": f"{fmean(float(row['absolute_error']) for row in level_details):.10f}",
                    "trigger_agreement": f"{fmean(float(row['trigger_agrees']) for row in level_details):.10f}",
                    "trigger_ld": f"{args.trigger_ld:.4f}",
                }
            )

    if not detail_rows:
        raise FileNotFoundError(f"No LogDepFull iteration reports found under {logdep_run_root}")

    write_csv(output_root / "details.csv", detail_rows, list(detail_rows[0].keys()))
    write_csv(output_root / "summary.csv", summary_rows, list(summary_rows[0].keys()))
    print(f"Saved Estimated LD analysis: {output_root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
