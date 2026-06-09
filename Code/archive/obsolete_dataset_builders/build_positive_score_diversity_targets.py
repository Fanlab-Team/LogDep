#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Build positive-correlation datasets for target diversity scores 0.1..0.9.

Compared with build_positive_correlation_diversity_levels.py, this script uses
more rows per template and a target active-template ratio. Active templates get
one distinct value per generated line, making their entropy close to 1; inactive
templates keep a single value and contribute near-zero diversity. This makes the
overall diversity score tunable while preserving the same positive-correlation
mechanism: higher target score => more templates contain variable evidence.
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

BASE_WORDS = [
    "alpha",
    "bravo",
    "charlie",
    "delta",
    "echo",
    "foxtrot",
    "golf",
    "hotel",
    "india",
    "juliet",
    "kilo",
    "lima",
    "mike",
    "november",
    "oscar",
    "papa",
    "quebec",
    "romeo",
    "sierra",
    "tango",
    "uniform",
    "victor",
    "whiskey",
    "xray",
    "yankee",
    "zulu",
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


def slug(score: float) -> str:
    return f"{score:.1f}".replace(".", "_")


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


def inactive_value_for(slot_idx: int) -> str:
    slot_prefix = chr(ord("a") + (slot_idx % 26)) * 2
    return f"{slot_prefix}alpha"


def active_value_for(dataset: str, slot_idx: int, variant_idx: int) -> str:
    # Standalone numeric values are intentionally used for active slots:
    # runLogIterSplit.dataClean() treats digit-heavy tokens as variables, while
    # VariableDiversityCaculate still counts the raw numeric values.
    number = 100000 + slot_idx * 10000 + variant_idx
    if dataset == "HDFS":
        return f"blk_{number}"
    if dataset in {"Hadoop", "Spark", "Zookeeper", "Thunderbird", "Linux", "Apache", "OpenSSH"}:
        a = 10 + (slot_idx % 100)
        b = (variant_idx // 250) % 250
        c = (variant_idx // 250) % 250
        d = (variant_idx % 250) + 1
        return f"{a}.{b}.{c}.{d}"
    if dataset == "BGL":
        return f"core.{number}"
    if dataset in {"Mac", "Proxifier"}:
        return f"node{slot_idx}-{variant_idx}.example.local"
    return str(number)


def fill_template(dataset: str, template: str, variant_idx: int, active: bool) -> str:
    slot = 0

    def repl(_: re.Match[str]) -> str:
        nonlocal slot
        value = active_value_for(dataset, slot, variant_idx) if active else inactive_value_for(slot)
        slot += 1
        return value

    return re.sub(r"<\*>", repl, template)


def replace_content(raw_line: str, original_content: str, new_content: str) -> str | None:
    idx = raw_line.rfind(original_content)
    if idx < 0:
        return None
    return raw_line[:idx] + new_content + raw_line[idx + len(original_content) :]


def selected_templates(dataset: str, source_root: Path, max_placeholders: int, max_template_length: int) -> List[dict]:
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
    for template_row in sorted(template_rows, key=lambda row: event_sort_key(row.get("EventId", ""))):
        event_id = template_row.get("EventId", "")
        template = template_row.get("EventTemplate", "")
        group = rows_by_event.get(event_id, [])
        if not event_id or not group or not is_selected_template(template, max_placeholders, max_template_length):
            continue
        sample = group[0]
        try:
            line_id = int(sample["LineId"])
        except (KeyError, ValueError):
            continue
        if not (1 <= line_id <= len(raw_lines)):
            continue
        if replace_content(raw_lines[line_id - 1], sample.get("Content", ""), fill_template(dataset, template, 0, False)) is None:
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
    return selected


def build_dataset(
    dataset: str,
    source_root: Path,
    target_score: float,
    lines_per_template: int,
    max_placeholders: int,
    max_template_length: int,
    human_root: Path,
    eval_root: Path,
    report_dir: Path,
) -> dict:
    selected = selected_templates(dataset, source_root, max_placeholders, max_template_length)
    active = min(len(selected), math.ceil(len(selected) * target_score))
    output_lines: List[str] = []
    group_rows = []

    for idx, item in enumerate(selected):
        is_active = idx < active
        distinct_values = lines_per_template if is_active else 1
        for line_idx in range(lines_per_template):
            variant_idx = line_idx % distinct_values
            content = fill_template(dataset, item["template"], variant_idx, is_active)
            line = replace_content(item["raw_line"], item["original_content"], content)
            if line is not None:
                output_lines.append(line)
        group_rows.append(
            {
                "dataset": dataset,
                "target_score": target_score,
                "event_id": item["event_id"],
                "active": int(is_active),
                "distinct_values_per_slot": distinct_values,
                "line_budget": lines_per_template,
                "placeholder_count": item["placeholder_count"],
                "template": item["template"],
            }
        )

    score_slug = slug(target_score)
    human_file = human_root / dataset / f"{dataset}_variable_positive_score_{score_slug}.log"
    eval_file = eval_root / dataset / f"{dataset}_variable_positive_diverse_score_{score_slug}.log"
    write_lines(human_file, output_lines)
    write_lines(eval_file, output_lines)

    group_fields = [
        "dataset",
        "target_score",
        "event_id",
        "active",
        "distinct_values_per_slot",
        "line_budget",
        "placeholder_count",
        "template",
    ]
    write_csv(
        report_dir / "template_groups" / f"{dataset}_variable_positive_score_{score_slug}_groups.csv",
        group_rows,
        group_fields,
    )

    return {
        "dataset": dataset,
        "target_score": target_score,
        "selected_templates": len(selected),
        "active_templates": active,
        "output_lines": len(output_lines),
        "human_output_file": str(human_file),
        "eval_output_file": str(eval_file),
    }


def build_target(args: argparse.Namespace, target_score: float) -> List[dict]:
    score_slug = slug(target_score)
    human_root = PROJECT_ROOT / f"dir_variable_positive_score_{score_slug}"
    eval_root = PROJECT_ROOT / "data" / f"dir_variable_positive_diverse_score_{score_slug}"
    report_dir = PROJECT_ROOT / f"variable_positive_score_{score_slug}_build_report"

    rows = []
    for dataset in args.datasets:
        row = build_dataset(
            dataset,
            args.source_root,
            target_score,
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
        "target_score",
        "selected_templates",
        "active_templates",
        "output_lines",
        "human_output_file",
        "eval_output_file",
    ]
    write_csv(report_dir / f"variable_positive_score_{score_slug}_manifest.csv", rows, fields)

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
    parser = argparse.ArgumentParser(description="Build target-score positive diversity datasets.")
    parser.add_argument("--targets", nargs="*", type=float, default=[i / 10 for i in range(1, 10)])
    parser.add_argument("--datasets", nargs="*", default=DATASETS)
    parser.add_argument("--source-root", type=Path, default=DEFAULT_SOURCE_ROOT)
    parser.add_argument("--next-test-data", type=Path, default=DEFAULT_NEXT_TEST_DATA)
    parser.add_argument("--lines-per-template", type=int, default=64)
    parser.add_argument("--max-placeholders", type=int, default=8)
    parser.add_argument("--max-template-length", type=int, default=220)
    parser.add_argument("--copy-to-next-test", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    args.datasets = [dataset for dataset in args.datasets if dataset in DATASETS]
    for target_score in args.targets:
        print(f"Building positive target score {target_score:.1f}")
        build_target(args, target_score)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
