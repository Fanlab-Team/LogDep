"""Build the paper-facing all-parser metrics table from parser summaries."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path
from statistics import fmean

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "results" / "final_metrics"
PARSER_SOURCES = (
    ("Brain", PROJECT_ROOT / "results/parser_runs/gtld/parser_eval/per_parser/brain.csv"),
    ("Drain", PROJECT_ROOT / "results/parser_runs/gtld/parser_eval/per_parser/drain.csv"),
    ("Spell", PROJECT_ROOT / "results/parser_runs/gtld/parser_eval/per_parser/spell.csv"),
    ("Logram", PROJECT_ROOT / "results/parser_runs/gtld/parser_eval/per_parser/logram.csv"),
    ("LILAC", PROJECT_ROOT / "results/parser_runs/gtld/parser_eval/per_parser/lilac.csv"),
    (
        "LogDep",
        PROJECT_ROOT / "results/parser_runs/gtld/parser_eval/per_parser/logdepfull.csv",
    ),
)
OUTPUT_FIELDS = (
    "parser",
    "target_diversity",
    "actual_ground_truth_ld",
    "PA",
    "PTA",
    "RTA",
)
METRIC_FIELDS = ("PA", "PTA", "RTA")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build the final all-parser PA/PTA/RTA CSV and Excel tables."
    )
    parser.add_argument(
        "--output-csv",
        type=Path,
        default=DEFAULT_OUTPUT_DIR / "all_metrics.csv",
        help="Output CSV path.",
    )
    parser.add_argument(
        "--output-xlsx",
        type=Path,
        default=DEFAULT_OUTPUT_DIR / "all_metrics.xlsx",
        help="Output Excel path.",
    )
    return parser.parse_args()


def load_parser_rows(parser_name: str, source: Path) -> list[dict[str, str]]:
    if not source.is_file():
        raise FileNotFoundError(f"Missing source for {parser_name}: {source}")

    with source.open("r", encoding="utf-8-sig", newline="") as file:
        rows = [
            row
            for row in csv.DictReader(file)
            if row.get("target_diversity", "").strip().upper() != "AVERAGE"
        ]

    rows.sort(key=lambda row: float(row["target_diversity"]))
    if len(rows) != 9:
        raise ValueError(
            f"{parser_name} must contain 9 diversity-level rows, found {len(rows)}"
        )

    output_rows: list[dict[str, str]] = []
    for row in rows:
        output_rows.append(
            {
                "parser": parser_name,
                "target_diversity": row["target_diversity"],
                "actual_ground_truth_ld": row.get("actual_ground_truth_ld")
                or row.get("actual_content_weighted_entropy_diversity", ""),
                **{metric: f"{float(row[metric]):.4f}" for metric in METRIC_FIELDS},
            }
        )

    output_rows.append(
        {
            "parser": parser_name,
            "target_diversity": "AVERAGE",
            "actual_ground_truth_ld": "",
            **{
                metric: f"{fmean(float(row[metric]) for row in rows):.4f}"
                for metric in METRIC_FIELDS
            },
        }
    )
    return output_rows


def write_csv(rows: list[dict[str, str]], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=OUTPUT_FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def write_xlsx(rows: list[dict[str, str]], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    dataframe = pd.DataFrame(rows, columns=OUTPUT_FIELDS)
    dataframe.to_excel(output_path, index=False, sheet_name="all_metrics")


def main() -> None:
    args = parse_args()
    rows = [
        row
        for parser_name, source in PARSER_SOURCES
        for row in load_parser_rows(parser_name, source)
    ]

    output_csv = args.output_csv.resolve()
    write_csv(rows, output_csv)
    print(f"Saved CSV: {output_csv}")

    if str(args.output_xlsx):
        output_xlsx = args.output_xlsx.resolve()
        write_xlsx(rows, output_xlsx)
        print(f"Saved Excel: {output_xlsx}")


if __name__ == "__main__":
    main()
