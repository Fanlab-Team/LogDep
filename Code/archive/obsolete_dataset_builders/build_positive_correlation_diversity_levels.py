#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Build a controlled positive-correlation diversity benchmark.

Goal:
  Construct datasets whose variable-value diversity increases from level 1 to
  level 8 and whose parser metrics are expected to improve because more
  templates receive evidence that their <*> fields are variables.

This script is intentionally a controlled stress test, not a natural sampling
benchmark:
  - fixed text comes from corrected templates in raw_2k;
  - log prefixes come from real 2k raw log lines;
  - variable values are controlled alphabetic tokens so regex pre-cleaning does
    not solve the task by itself;
  - the template set and line budget are fixed across all levels;
  - higher levels progressively activate more variable templates and more
    distinct values per active variable slot.
"""

from __future__ import annotations

import argparse
import csv
import math
import re
import shutil
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Sequence


SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
DEFAULT_SOURCE_ROOT = Path(r"C:\Users\86130\Desktop\Next_test\data\raw_2k")
DEFAULT_NEXT_TEST_DATA = Path(r"C:\Users\86130\Desktop\Next_test\data")

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

WORDS = [
    "alpha",
    "bravo",
    "charlie",
    "delta",
    "echo",
    "foxtrot",
    "golf",
    "hotel",
]


def read_lines(path: Path) -> List[str]:
    for encoding in ("utf-8", "utf-8-sig", "gbk", "latin-1"):
        try:
            with path.open("r", encoding=encoding) as f:
                return [line.rstrip("\r\n") for line in f]
        except UnicodeDecodeError:
            continue
    raise UnicodeDecodeError("unknown", b"", 0, 1, f"Cannot decode {path}")


def read_csv_rows(path: Path) -> List[dict]:
    for encoding in ("utf-8-sig", "utf-8", "gbk", "latin-1"):
        try:
            with path.open("r", encoding=encoding, newline="") as f:
                return list(csv.DictReader(f))
        except UnicodeDecodeError:
            continue
    raise UnicodeDecodeError("unknown", b"", 0, 1, f"Cannot decode {path}")


def write_lines(path: Path, lines: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as f:
        for line in lines:
            f.write(line.rstrip("\r\n") + "\n")


def write_csv(path: Path, rows: Sequence[dict], fieldnames: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def event_sort_key(event_id: str) -> tuple[int, str]:
    if event_id.startswith("E") and event_id[1:].isdigit():
        return int(event_id[1:]), event_id
    return 10**9, event_id


def placeholder_count(template: str) -> int:
    return len(re.findall(r"<\*>", template))


def placeholder_is_cleanly_separated(template: str) -> bool:
    for match in re.finditer(r"<\*>", template):
        before = template[match.start() - 1] if match.start() > 0 else " "
        after = template[match.end()] if match.end() < len(template) else " "
        if before.isalnum() or before == "_":
            return False
        if after.isalnum() or after == "_":
            return False
    return True


def is_selected_template(template: str, max_placeholders: int, max_length: int) -> bool:
    count = placeholder_count(template)
    return (
        1 <= count <= max_placeholders
        and len(template) <= max_length
        and placeholder_is_cleanly_separated(template)
    )


def value_for(slot_idx: int, variant_idx: int) -> str:
    slot_prefix = chr(ord("a") + (slot_idx % 26)) * 2
    word = WORDS[variant_idx % len(WORDS)]
    cycle = "" if variant_idx < len(WORDS) else chr(ord("a") + (variant_idx // len(WORDS)))
    return f"{slot_prefix}{word}{cycle}"


def fill_template(template: str, variant_idx: int) -> str:
    slot = 0

    def repl(_: re.Match[str]) -> str:
        nonlocal slot
        value = value_for(slot, variant_idx)
        slot += 1
        return value

    return re.sub(r"<\*>", repl, template)


def replace_content(raw_line: str, original_content: str, new_content: str) -> str | None:
    idx = raw_line.rfind(original_content)
    if idx < 0:
        return None
    return raw_line[:idx] + new_content + raw_line[idx + len(original_content) :]


def active_count(total: int, level: int, max_level: int) -> int:
    if level <= 1 or total <= 0:
        return 0
    return max(1, math.ceil(total * (level - 1) / (max_level - 1)))


def build_dataset(
    dataset: str,
    source_root: Path,
    level: int,
    max_level: int,
    lines_per_template: int,
    max_placeholders: int,
    max_template_length: int,
    human_root: Path,
    eval_root: Path,
    report_dir: Path,
) -> dict:
    ds_dir = source_root / dataset
    raw_lines = read_lines(ds_dir / f"{dataset}_2k.log")
    structured_rows = read_csv_rows(ds_dir / f"{dataset}_2k.log_structured_corrected.csv")
    template_rows = read_csv_rows(ds_dir / f"{dataset}_2k.log_templates_corrected.csv")

    rows_by_event: Dict[str, List[dict]] = defaultdict(list)
    for row in structured_rows:
        event_id = row.get("EventId", "")
        if event_id:
            rows_by_event[event_id].append(row)

    selected = []
    skipped = 0
    for template_row in sorted(template_rows, key=lambda row: event_sort_key(row.get("EventId", ""))):
        event_id = template_row.get("EventId", "")
        template = template_row.get("EventTemplate", "")
        group = rows_by_event.get(event_id, [])
        if not event_id or not group or not is_selected_template(template, max_placeholders, max_template_length):
            skipped += 1
            continue
        sample = group[0]
        try:
            line_id = int(sample["LineId"])
        except (KeyError, ValueError):
            skipped += 1
            continue
        if not (1 <= line_id <= len(raw_lines)):
            skipped += 1
            continue
        test_line = replace_content(raw_lines[line_id - 1], sample.get("Content", ""), fill_template(template, 0))
        if test_line is None:
            skipped += 1
            continue
        selected.append(
            {
                "event_id": event_id,
                "template": template,
                "line_id": line_id,
                "original_content": sample.get("Content", ""),
                "raw_line": raw_lines[line_id - 1],
                "placeholder_count": placeholder_count(template),
            }
        )

    activated = active_count(len(selected), level, max_level)
    output_lines: List[str] = []
    group_rows = []
    for idx, item in enumerate(selected):
        is_active = idx < activated
        distinct_values = level if is_active else 1
        for line_idx in range(lines_per_template):
            variant_idx = line_idx % distinct_values
            content = fill_template(item["template"], variant_idx)
            line = replace_content(item["raw_line"], item["original_content"], content)
            if line is not None:
                output_lines.append(line)
        group_rows.append(
            {
                "dataset": dataset,
                "level": level,
                "event_id": item["event_id"],
                "active": int(is_active),
                "distinct_values_per_slot": distinct_values,
                "line_budget": lines_per_template,
                "placeholder_count": item["placeholder_count"],
                "template": item["template"],
            }
        )

    human_file = human_root / dataset / f"{dataset}_variable_positive_diversity_{level}.log"
    eval_file = eval_root / dataset / f"{dataset}_variable_positive_diverse_{level}.log"
    write_lines(human_file, output_lines)
    write_lines(eval_file, output_lines)

    group_fields = [
        "dataset",
        "level",
        "event_id",
        "active",
        "distinct_values_per_slot",
        "line_budget",
        "placeholder_count",
        "template",
    ]
    write_csv(
        report_dir / "template_groups" / f"{dataset}_variable_positive_diversity_{level}_groups.csv",
        group_rows,
        group_fields,
    )

    return {
        "dataset": dataset,
        "level": level,
        "selected_templates": len(selected),
        "active_templates": activated,
        "skipped_templates": skipped,
        "output_lines": len(output_lines),
        "human_output_file": str(human_file),
        "eval_output_file": str(eval_file),
    }


def build_level(args: argparse.Namespace, level: int) -> List[dict]:
    human_root = PROJECT_ROOT / f"dir_variable_positive_diversity_{level}"
    eval_root = PROJECT_ROOT / "data" / f"dir_variable_positive_diverse_{level}"
    report_dir = PROJECT_ROOT / f"variable_positive_diversity_{level}_build_report"
    rows = []
    for dataset in args.datasets:
        row = build_dataset(
            dataset,
            args.source_root,
            level,
            args.max_level,
            args.lines_per_template,
            args.max_placeholders,
            args.max_template_length,
            human_root,
            eval_root,
            report_dir,
        )
        rows.append(row)
        print(
            f"  {dataset}: selected={row['selected_templates']} "
            f"active={row['active_templates']} output={row['output_lines']}"
        )

    fields = [
        "dataset",
        "level",
        "selected_templates",
        "active_templates",
        "skipped_templates",
        "output_lines",
        "human_output_file",
        "eval_output_file",
    ]
    write_csv(report_dir / f"variable_positive_diversity_{level}_manifest.csv", rows, fields)

    if args.copy_to_next_test:
        target = args.next_test_data / eval_root.name
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(eval_root, target)
        print(f"  copied_to={target}")

    print(f"  human_output_root={human_root}")
    print(f"  eval_output_root={eval_root}")
    print(f"  report_dir={report_dir}")
    return rows


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build positive-correlation variable diversity datasets.")
    parser.add_argument("--levels", nargs="*", type=int, default=list(range(1, 9)))
    parser.add_argument("--datasets", nargs="*", default=DATASETS)
    parser.add_argument("--source-root", type=Path, default=DEFAULT_SOURCE_ROOT)
    parser.add_argument("--next-test-data", type=Path, default=DEFAULT_NEXT_TEST_DATA)
    parser.add_argument("--max-level", type=int, default=8)
    parser.add_argument("--lines-per-template", type=int, default=16)
    parser.add_argument("--max-placeholders", type=int, default=8)
    parser.add_argument("--max-template-length", type=int, default=220)
    parser.add_argument("--copy-to-next-test", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    args.datasets = [dataset for dataset in args.datasets if dataset in DATASETS]
    for level in args.levels:
        print(f"Building positive-correlation diversity level {level}")
        build_level(args, level)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
