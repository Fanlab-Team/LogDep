#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Evaluate Brain on the entropy-target diversity datasets.

This uses the shared experiment standard:
  - input datasets: data/gtld/diversity_0_1 ... 0_9
  - ground truth: corrected templates from data/raw_2k
  - x-axis: offline parser-independent Ground-truth LD
  - metrics: PA, PTA, RTA with the same template token matching rule

Brain itself writes its grouped templates to ../log_after_group. This script
copies those outputs into a dedicated result directory and calculates metrics
from them.
"""

from __future__ import annotations

import argparse
import csv
import datetime
import os
import re
import shutil
import sys
from pathlib import Path
from typing import Iterable, Sequence

import pandas as pd


SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(SCRIPT_DIR))

import brain_parser as Ba
from diversity_metrics import (
    BENCHMARK_SETTINGS,
    DATASETS,
    extract_content_lines,
    find_log_file,
    read_lines,
)


LEVELS = ["0_1", "0_2", "0_3", "0_4", "0_5", "0_6", "0_7", "0_8", "0_9"]


def message_split(message: str) -> list[str]:
    punc = "!\"#$%&'()+,-/:;=?@.[\\]^_`{|}~"
    splitters = "\\s\\" + "\\".join(punc)
    splitter_regex = re.compile("([{}]+)".format(splitters))
    tokens = re.split(splitter_regex, str(message))
    tokens = [token for token in tokens if token != ""]
    tokens = post_process_tokens(tokens, punc)
    tokens = [token.strip() for token in tokens if token.strip()]
    tokens = [
        token
        for idx, token in enumerate(tokens)
        if not (token == "<*>" and idx > 0 and tokens[idx - 1] == "<*>")
    ]
    return tokens


def post_process_tokens(tokens: list[str], punc: str) -> list[str]:
    excluded_str = ["=", "|", "(", ")"]
    for i, token in enumerate(tokens):
        if "<*>" in token or "*" == token:
            tokens[i] = "<*>"
            continue
        new_str = ""
        for char in token:
            if (char not in punc and char != " ") or char in excluded_str:
                new_str += char
        tokens[i] = new_str
    return tokens


def is_match(generated_template: str, standard_template: str) -> bool:
    return message_split(generated_template) == message_split(standard_template)


def read_standard_templates(dataset: str, standard_root: Path) -> list[str]:
    path = standard_root / dataset / f"{dataset}_2k.log_templates_corrected.csv"
    df = pd.read_csv(path)
    return df["EventTemplate"].dropna().astype(str).tolist()


def parse_line_indices(value: str) -> list[int]:
    indices = []
    for part in str(value).split(","):
        part = part.strip()
        if part:
            try:
                indices.append(int(part))
            except ValueError:
                pass
    return indices


def read_brain_groups(group_file: Path) -> list[tuple[str, int]]:
    last_error: Exception | None = None
    for encoding in ("gbk", "utf-8-sig", "utf-8", "latin-1"):
        try:
            with group_file.open("r", encoding=encoding, newline="") as f:
                reader = csv.DictReader(f)
                fieldnames = reader.fieldnames or []
                template_keys = ("\u6a21\u677f", "妯℃澘", "template")
                line_id_keys = ("\u53e5\u5b50\u6807\u53f7", "鍙ュ瓙鏍囧彿", "line_ids")
                template_key = next(
                    (key for key in template_keys if key in fieldnames),
                    fieldnames[0] if fieldnames else None,
                )
                line_id_key = next(
                    (key for key in line_id_keys if key in fieldnames),
                    fieldnames[1] if len(fieldnames) > 1 else None,
                )
                rows = []
                for row in reader:
                    template = (row.get(template_key) or "").strip() if template_key else ""
                    line_ids = (row.get(line_id_key) or "") if line_id_key else ""
                    if template:
                        rows.append((template, len(parse_line_indices(line_ids))))
                return rows
        except UnicodeDecodeError as exc:
            last_error = exc
            continue
    if last_error:
        raise last_error
    return []


def calculate_pa(generated: list[tuple[str, int]], standard: list[str]) -> float:
    total_count = sum(count for _, count in generated)
    if total_count <= 0:
        return 0.0
    correct_count = 0
    for template, count in generated:
        if any(is_match(template, std) for std in standard):
            correct_count += count
    return correct_count / total_count


def calculate_pta(generated: list[tuple[str, int]], standard: list[str]) -> float:
    if not generated:
        return 0.0
    correct_count = 0
    for template, _count in generated:
        for std in standard:
            if is_match(template, std):
                correct_count += 1
                break
    return correct_count / len(generated)


def calculate_rta(generated: list[tuple[str, int]], standard: list[str]) -> float:
    if not standard:
        return 0.0
    generated_templates = [template for template, _count in generated]
    covered = 0
    for std in standard:
        if any(is_match(gen, std) for gen in generated_templates):
            covered += 1
    return covered / len(standard)


def write_brain_template_with_idx(generated: list[tuple[str, int]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        for template, count in generated:
            f.write(f"{template} {count}\n")


def resolve_standard_root(arg_value: str | None) -> Path:
    candidates: list[Path] = []
    if arg_value:
        candidates.append(Path(arg_value))
    candidates.extend(
        [
            PROJECT_ROOT / "data" / "raw_2k",
        ]
    )
    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise FileNotFoundError("Cannot find corrected ground truth templates under data/raw_2k.")


def run_brain_for_dataset(dataset: str, data_dir: Path, output_dir: Path) -> dict[str, object]:
    setting = BENCHMARK_SETTINGS[dataset]
    log_file = find_log_file(dataset, data_dir, data_dir.name, flat=False)
    raw_lines = read_lines(log_file)
    content_lines, parse_failures = extract_content_lines(dataset, raw_lines)

    (PROJECT_ROOT / "log_after_group").mkdir(parents=True, exist_ok=True)
    os.chdir(SCRIPT_DIR)
    start = datetime.datetime.now()
    Ba.parse_E(
        content_lines,
        setting["regex"],
        dataset,
        setting["theshold"],
        setting["delimiter"],
        setting["tag"],
        start,
        efficiency=False,
    )

    source_group_file = PROJECT_ROOT / "log_after_group" / f"{dataset}_template.csv"
    saved_group_file = output_dir / dataset / f"{dataset}_brain_template_groups.csv"
    saved_group_file.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source_group_file, saved_group_file)

    generated = read_brain_groups(saved_group_file)
    template_with_idx = output_dir / dataset / f"{dataset}_brain_new_template_with_idx.csv"
    write_brain_template_with_idx(generated, template_with_idx)

    return {
        "dataset": dataset,
        "source_file": str(log_file),
        "group_file": str(saved_group_file),
        "template_file": str(template_with_idx),
        "raw_lines": len(raw_lines),
        "content_parse_failures": parse_failures,
        "generated_templates": len(generated),
        "generated_template_line_count": sum(count for _, count in generated),
        "generated": generated,
    }


def read_actual_diversity(
    level: str,
    calibration_file: str | Path = "results/ground_truth_diversity/calibration.csv",
) -> float | None:
    calibration_path = Path(calibration_file)
    if not calibration_path.is_absolute():
        calibration_path = PROJECT_ROOT / calibration_path
    if not calibration_path.exists():
        return None
    target = f"{float(level.replace('_', '.')):.1f}"
    with calibration_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get("target_score") == target:
                for field in (
                    "actual_ground_truth_ld",
                    "actual_content_weighted_entropy_diversity",
                ):
                    value = row.get(field)
                    if value:
                        return float(value)
    return None


def evaluate_level(level: str, args: argparse.Namespace, standard_root: Path) -> dict[str, object]:
    data_dir = PROJECT_ROOT / args.data_root / f"{args.data_prefix}_{level}"
    output_dir = PROJECT_ROOT / args.output_root / f"diversity_{level}"
    output_dir.mkdir(parents=True, exist_ok=True)

    rows = []
    metrics_sum = {"PA": 0.0, "PTA": 0.0, "RTA": 0.0}
    success_count = 0
    for dataset in DATASETS:
        print(f"[{level}] Brain parsing {dataset} ...")
        try:
            parsed = run_brain_for_dataset(dataset, data_dir, output_dir)
            standard = read_standard_templates(dataset, standard_root)
            generated = parsed.pop("generated")
            pa = calculate_pa(generated, standard)
            pta = calculate_pta(generated, standard)
            rta = calculate_rta(generated, standard)
            rows.append(
                {
                    "dataset": dataset,
                    "PA": f"{pa:.4f}",
                    "PTA": f"{pta:.4f}",
                    "RTA": f"{rta:.4f}",
                    "raw_lines": parsed["raw_lines"],
                    "content_parse_failures": parsed["content_parse_failures"],
                    "generated_templates": parsed["generated_templates"],
                    "generated_template_line_count": parsed["generated_template_line_count"],
                    "source_file": parsed["source_file"],
                    "template_file": parsed["template_file"],
                    "group_file": parsed["group_file"],
                }
            )
            metrics_sum["PA"] += pa
            metrics_sum["PTA"] += pta
            metrics_sum["RTA"] += rta
            success_count += 1
        except Exception as exc:
            rows.append(
                {
                    "dataset": dataset,
                    "PA": "ERROR",
                    "PTA": "ERROR",
                    "RTA": "ERROR",
                    "raw_lines": "",
                    "content_parse_failures": "",
                    "generated_templates": "",
                    "generated_template_line_count": "",
                    "source_file": "",
                    "template_file": "",
                    "group_file": str(exc),
                }
            )

    avg = {
        "dataset": "AVERAGE",
        "PA": f"{(metrics_sum['PA'] / success_count):.4f}" if success_count else "ERROR",
        "PTA": f"{(metrics_sum['PTA'] / success_count):.4f}" if success_count else "ERROR",
        "RTA": f"{(metrics_sum['RTA'] / success_count):.4f}" if success_count else "ERROR",
        "raw_lines": "",
        "content_parse_failures": "",
        "generated_templates": "",
        "generated_template_line_count": "",
        "source_file": "",
        "template_file": "",
        "group_file": "",
    }
    rows.append(avg)

    eval_csv = output_dir / "metrics.csv"
    fieldnames = list(rows[0].keys())
    with eval_csv.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    actual_ground_truth_ld = read_actual_diversity(level, args.calibration_file)
    return {
        "target_diversity": "0." + level.split("_")[1],
        "actual_ground_truth_ld": actual_ground_truth_ld,
        # Deprecated alias retained so old table-building scripts keep working.
        "actual_content_weighted_entropy_diversity": actual_ground_truth_ld,
        "PA": avg["PA"],
        "PTA": avg["PTA"],
        "RTA": avg["RTA"],
        "eval_csv": str(eval_csv),
        "result_dir": str(output_dir),
        "success_count": success_count,
    }


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate Brain on 0.1-0.9 diversity datasets.")
    parser.add_argument("--data-root", default="data/gtld", help="Project-relative data root.")
    parser.add_argument("--data-prefix", default="diversity")
    parser.add_argument("--output-root", default="results/parser_runs/gtld/brain_eval")
    parser.add_argument(
        "--calibration-file",
        default="results/ground_truth_diversity/calibration.csv",
        help="Common Ground-truth LD calibration used only for reporting the x-axis.",
    )
    parser.add_argument("--standard-root", default=None, help="Path to corrected template CSV files, usually data/raw_2k.")
    parser.add_argument("--levels", nargs="*", default=LEVELS, help="Levels like 0_1 0_2 ... 0_9.")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    standard_root = resolve_standard_root(args.standard_root)
    print(f"Using standard templates: {standard_root}")

    summary_rows = []
    original_cwd = Path.cwd()
    try:
        for level in args.levels:
            summary_rows.append(evaluate_level(level, args, standard_root))
    finally:
        os.chdir(original_cwd)

    level_rows = [
        row
        for row in summary_rows
        if str(row.get("target_diversity", "")).upper() != "AVERAGE"
    ]
    summary_rows.append(
        {
            "target_diversity": "AVERAGE",
            "actual_ground_truth_ld": "",
            "actual_content_weighted_entropy_diversity": "",
            "PA": f"{sum(float(row['PA']) for row in level_rows) / len(level_rows):.4f}",
            "PTA": f"{sum(float(row['PTA']) for row in level_rows) / len(level_rows):.4f}",
            "RTA": f"{sum(float(row['RTA']) for row in level_rows) / len(level_rows):.4f}",
            "success_count": "",
            "eval_csv": "",
            "result_dir": "",
        }
    )

    summary_path = PROJECT_ROOT / args.output_root / "summary.csv"
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "target_diversity",
        "actual_ground_truth_ld",
        "actual_content_weighted_entropy_diversity",
        "PA",
        "PTA",
        "RTA",
        "success_count",
        "eval_csv",
        "result_dir",
    ]
    with summary_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in summary_rows:
            writer.writerow(row)

    print(f"Summary saved to: {summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
