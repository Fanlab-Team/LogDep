#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Construct controlled-diversity datasets from the original logs/ directory.

For diversity level d:
  For each parsed template group, keep up to d representative raw log lines as
  the only variable assignments for that template. Repeat those representatives
  round-robin to preserve the original template group size.

This keeps total line count and template frequency close to the original logs,
while controlling the number of variable values available per template.

Outputs for --level 2:
  ../dir_diversity_2/<Dataset>/<Dataset>_diversity_2.log
  ../data/dir_diverse_2/<Dataset>/<Dataset>_diverse_2.log
  ../diversity_2_report/
"""

from __future__ import annotations

import argparse
import csv
import os
import shutil
import sys
from pathlib import Path
from typing import List, Sequence


SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(SCRIPT_DIR))

import EntropyCaculate as EC


DATASETS = [
    "HDFS",
    "Hadoop",
    "Spark",
    "Zookeeper",
    "BGL",
    "HPC",
    "Thunderbird",
    "Windows",
    "Linux",
    "Android",
    "HealthApp",
    "Apache",
    "OpenSSH",
    "OpenStack",
    "Mac",
    "Proxifier",
]

LOGS_DIR = PROJECT_ROOT / "logs"


def read_lines(path: Path) -> List[str]:
    for encoding in ("utf-8", "utf-8-sig", "gbk", "latin-1"):
        try:
            with path.open("r", encoding=encoding) as f:
                return [line.rstrip("\r\n") for line in f if line.strip()]
        except UnicodeDecodeError:
            continue
    raise UnicodeDecodeError("unknown", b"", 0, 1, f"Cannot decode {path}")


def write_lines(path: Path, lines: Sequence[str]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as f:
        for line in lines:
            f.write(line.rstrip("\r\n") + "\n")
    return len(lines)


def read_template_groups(path: Path) -> List[dict]:
    for encoding in ("gbk", "utf-8-sig", "utf-8"):
        try:
            with path.open("r", encoding=encoding, newline="") as f:
                return list(csv.DictReader(f))
        except UnicodeDecodeError:
            continue
    raise UnicodeDecodeError("unknown", b"", 0, 1, f"Cannot decode {path}")


def parse_indices(value: str) -> List[int]:
    indices = []
    for part in value.strip().strip('"').split(","):
        part = part.strip()
        if part:
            indices.append(int(part))
    return indices


def choose_log_file(dataset: str) -> Path:
    for suffix in (".log", ".logs"):
        candidate = LOGS_DIR / f"{dataset}_2k{suffix}"
        if candidate.exists():
            return candidate
    raise FileNotFoundError(f"No logs/{dataset}_2k.log(s) found")


def unique_representatives(raw_lines: Sequence[str], indices: Sequence[int], level: int) -> List[int]:
    reps: List[int] = []
    seen = set()
    for idx in indices:
        line = raw_lines[idx]
        if line in seen:
            continue
        seen.add(line)
        reps.append(idx)
        if len(reps) >= level:
            break
    if reps:
        return reps
    return list(indices[:1])


def round_robin_fill(raw_lines: Sequence[str], representatives: Sequence[int], output_size: int) -> List[str]:
    return [raw_lines[representatives[i % len(representatives)]] for i in range(output_size)]


def run_entropy_parser(dataset: str, source_file: Path) -> float:
    old_cwd = Path.cwd()
    try:
        os.chdir(SCRIPT_DIR)
        return EC.E_dataset("../logs/", source_file.name, dataset)
    finally:
        os.chdir(old_cwd)


def build_one_dataset(dataset: str, level: int, human_root: Path, eval_root: Path, report_dir: Path) -> dict:
    source_file = choose_log_file(dataset)
    raw_lines = read_lines(source_file)
    original_diversity = run_entropy_parser(dataset, source_file)

    group_file = PROJECT_ROOT / "log_after_group" / f"{dataset}_template.csv"
    rows = read_template_groups(group_file)

    output_lines: List[str] = []
    group_rows: List[dict] = []
    skipped_groups = 0
    groups_with_fewer_than_level = 0

    for group_id, row in enumerate(rows):
        template = row.get("模板") or row.get("妯℃澘") or ""
        index_value = row.get("句子标号") or row.get("鍙ュ瓙鏍囧彿") or ""
        try:
            indices = parse_indices(index_value)
        except ValueError:
            skipped_groups += 1
            continue
        valid_indices = [idx for idx in indices if 0 <= idx < len(raw_lines)]
        if not valid_indices:
            skipped_groups += 1
            continue

        reps = unique_representatives(raw_lines, valid_indices, level)
        if len(reps) < level:
            groups_with_fewer_than_level += 1
        group_output = round_robin_fill(raw_lines, reps, len(valid_indices))
        output_lines.extend(group_output)

        group_rows.append(
            {
                "dataset": dataset,
                "group_id": group_id,
                "template": template,
                "source_group_size": len(valid_indices),
                "representative_count": len(reps),
                "representative_indices": ",".join(str(idx) for idx in reps),
                "representative_lines": " ||| ".join(raw_lines[idx] for idx in reps),
            }
        )

    human_output = human_root / dataset / f"{dataset}_diversity_{level}.log"
    eval_output = eval_root / dataset / f"{dataset}_diverse_{level}.log"
    output_count = write_lines(human_output, output_lines)
    write_lines(eval_output, output_lines)

    group_report_dir = report_dir / "template_groups"
    group_report_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(group_file, group_report_dir / f"{dataset}_template.csv")
    with (group_report_dir / f"{dataset}_diversity_{level}_groups.csv").open("w", encoding="utf-8", newline="") as f:
        fieldnames = [
            "dataset",
            "group_id",
            "template",
            "source_group_size",
            "representative_count",
            "representative_indices",
            "representative_lines",
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(group_rows)

    return {
        "dataset": dataset,
        "source_file": str(source_file),
        "original_lines": len(raw_lines),
        "template_groups": len(group_rows),
        "skipped_groups": skipped_groups,
        "groups_with_fewer_than_level": groups_with_fewer_than_level,
        "output_lines": output_count,
        "unique_output_lines": len(set(output_lines)),
        "original_diversity_score": original_diversity,
        "target_diversity_level": level,
        "preserve_template_frequency": True,
        "human_output_file": str(human_output),
        "eval_output_file": str(eval_output),
    }


def write_manifest(report_dir: Path, level: int, rows: Sequence[dict]) -> None:
    report_dir.mkdir(parents=True, exist_ok=True)
    path = report_dir / f"diversity_{level}_manifest.csv"
    fieldnames = [
        "dataset",
        "source_file",
        "original_lines",
        "template_groups",
        "skipped_groups",
        "groups_with_fewer_than_level",
        "output_lines",
        "unique_output_lines",
        "original_diversity_score",
        "target_diversity_level",
        "preserve_template_frequency",
        "human_output_file",
        "eval_output_file",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build controlled-diversity log datasets from logs/.")
    parser.add_argument("--level", type=int, required=True, help="Target diversity level d. Use 2 for diversity=2.")
    parser.add_argument("--datasets", nargs="*", default=DATASETS)
    args = parser.parse_args(argv)

    if args.level < 1:
        raise ValueError("--level must be >= 1")

    human_root = PROJECT_ROOT / f"dir_diversity_{args.level}"
    eval_root = PROJECT_ROOT / "data" / f"dir_diverse_{args.level}"
    report_dir = PROJECT_ROOT / f"diversity_{args.level}_report"
    (PROJECT_ROOT / "log_after_group").mkdir(parents=True, exist_ok=True)

    manifest = []
    for dataset in args.datasets:
        if dataset not in DATASETS:
            print(f"Skip unknown dataset: {dataset}")
            continue
        print(f"Building diversity={args.level} dataset: {dataset}")
        row = build_one_dataset(dataset, args.level, human_root, eval_root, report_dir)
        manifest.append(row)
        print(
            f"  original={row['original_lines']} output={row['output_lines']} "
            f"groups={row['template_groups']} unique={row['unique_output_lines']} "
            f"under_level_groups={row['groups_with_fewer_than_level']}"
        )

    write_manifest(report_dir, args.level, manifest)
    print(f"manifest={report_dir / f'diversity_{args.level}_manifest.csv'}")
    print(f"human_output_root={human_root}")
    print(f"eval_output_root={eval_root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
