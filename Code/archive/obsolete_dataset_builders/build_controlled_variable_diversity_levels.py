#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Build controlled variable-value diversity datasets.

This is a stricter follow-up to build_variable_value_diversity_levels.py.
It uses corrected structured labels from raw_2k, keeps the same template
coverage and line budget across levels, and increases only the number of real
observed values per EventId group.

For level k:
  - each selected template contributes a fixed number of log lines;
  - variable templates use up to k real log variants from the same EventId;
  - variants must share a stable token/shape signature to avoid changing the
    event structure while increasing variable values;
  - no synthetic variable values are generated.
"""

from __future__ import annotations

import argparse
import csv
import re
import shutil
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple


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


def template_has_variable(template: str) -> bool:
    return "<*>" in template


def normalized_shape(text: str) -> str:
    """Return a coarse structure signature that preserves separators."""
    text = re.sub(r"0[xX][0-9a-fA-F]+", "HEX", text)
    text = re.sub(r"\b\d+\.\d+\.\d+\.\d+(?::\d+)?\b", "IP", text)
    text = re.sub(r"\b-?\d+(?:\.\d+)?\b", "NUM", text)
    text = re.sub(r"\b[a-fA-F0-9]{6,}\b", "HEXID", text)
    text = re.sub(r"[A-Za-z_][A-Za-z0-9_.$-]*", "WORD", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def content_field(row: dict) -> str:
    return row.get("Content", "")


def stable_variant_rows(rows: Sequence[dict], raw_lines: Sequence[str], max_level: int) -> Tuple[List[dict], dict]:
    """Pick real rows from the largest stable shape cluster."""
    clusters: Dict[str, List[dict]] = defaultdict(list)
    for row in rows:
        try:
            line_id = int(row["LineId"])
        except (KeyError, ValueError):
            continue
        if not (1 <= line_id <= len(raw_lines)):
            continue
        signature = normalized_shape(content_field(row))
        clusters[signature].append(row)

    if not clusters:
        return [], {
            "shape_clusters": 0,
            "largest_shape_cluster_size": 0,
            "real_variants_available": 0,
        }

    best_signature, best_rows = max(clusters.items(), key=lambda item: len(item[1]))
    unique_rows = []
    seen_lines = set()
    for row in best_rows:
        line_id = int(row["LineId"])
        raw = raw_lines[line_id - 1]
        if raw in seen_lines:
            continue
        seen_lines.add(raw)
        unique_rows.append(row)

    return unique_rows[:max_level], {
        "shape_clusters": len(clusters),
        "selected_shape": best_signature,
        "largest_shape_cluster_size": len(best_rows),
        "real_variants_available": len(unique_rows),
    }


def cycle_to_budget(rows: Sequence[dict], level: int, line_budget: int, raw_lines: Sequence[str]) -> List[str]:
    if not rows:
        return []
    chosen = list(rows[: max(1, min(level, len(rows)))])
    return [raw_lines[int(chosen[i % len(chosen)]["LineId"]) - 1] for i in range(line_budget)]


def build_dataset(
    dataset: str,
    source_root: Path,
    level: int,
    max_level: int,
    line_budget: int,
    human_root: Path,
    eval_root: Path,
    report_dir: Path,
    require_full_level: bool,
) -> dict:
    ds_dir = source_root / dataset
    raw_file = ds_dir / f"{dataset}_2k.log"
    structured_file = ds_dir / f"{dataset}_2k.log_structured_corrected.csv"
    templates_file = ds_dir / f"{dataset}_2k.log_templates_corrected.csv"
    raw_lines = read_lines(raw_file)
    structured_rows = read_csv_rows(structured_file)
    template_rows = read_csv_rows(templates_file)

    template_by_event = {
        row.get("EventId", ""): row.get("EventTemplate", "")
        for row in template_rows
        if row.get("EventId")
    }
    rows_by_event: Dict[str, List[dict]] = defaultdict(list)
    for row in structured_rows:
        event_id = row.get("EventId", "")
        if event_id:
            rows_by_event[event_id].append(row)

    output_lines: List[str] = []
    group_rows = []
    selected_templates = 0
    variable_templates = 0
    skipped_templates = 0
    total_real_variants = 0

    for event_id in sorted(template_by_event, key=lambda value: int(value[1:]) if value[1:].isdigit() else value):
        template = template_by_event[event_id]
        group = rows_by_event.get(event_id, [])
        if not group:
            skipped_templates += 1
            continue
        variant_rows, stats = stable_variant_rows(group, raw_lines, max_level)
        if not variant_rows:
            skipped_templates += 1
            continue
        is_variable = template_has_variable(template)
        if require_full_level and is_variable and len(variant_rows) < max_level:
            skipped_templates += 1
            continue

        lines = cycle_to_budget(variant_rows, level if is_variable else 1, line_budget, raw_lines)
        output_lines.extend(lines)
        selected_templates += 1
        variable_templates += int(is_variable)
        total_real_variants += len(variant_rows)
        group_rows.append(
            {
                "dataset": dataset,
                "level": level,
                "event_id": event_id,
                "is_variable_template": int(is_variable),
                "source_group_size": len(group),
                "real_variants_available": stats["real_variants_available"],
                "shape_clusters": stats["shape_clusters"],
                "largest_shape_cluster_size": stats["largest_shape_cluster_size"],
                "line_budget": line_budget,
                "used_variants_this_level": min(level if is_variable else 1, len(variant_rows)),
                "template": template,
            }
        )

    human_file = human_root / dataset / f"{dataset}_variable_controlled_diversity_{level}.log"
    eval_file = eval_root / dataset / f"{dataset}_variable_controlled_diverse_{level}.log"
    write_lines(human_file, output_lines)
    write_lines(eval_file, output_lines)

    group_fieldnames = [
        "dataset",
        "level",
        "event_id",
        "is_variable_template",
        "source_group_size",
        "real_variants_available",
        "shape_clusters",
        "largest_shape_cluster_size",
        "line_budget",
        "used_variants_this_level",
        "template",
    ]
    write_csv(
        report_dir / "template_groups" / f"{dataset}_variable_controlled_diversity_{level}_groups.csv",
        group_rows,
        group_fieldnames,
    )

    return {
        "dataset": dataset,
        "level": level,
        "source_file": str(raw_file),
        "source_lines": len(raw_lines),
        "selected_templates": selected_templates,
        "selected_variable_templates": variable_templates,
        "skipped_templates": skipped_templates,
        "output_lines": len(output_lines),
        "avg_real_variants_per_selected_template": (
            round(total_real_variants / selected_templates, 4) if selected_templates else 0
        ),
        "human_output_file": str(human_file),
        "eval_output_file": str(eval_file),
    }


def build_level(args: argparse.Namespace, level: int) -> List[dict]:
    human_root = PROJECT_ROOT / f"dir_variable_controlled_diversity_{level}"
    eval_root = PROJECT_ROOT / "data" / f"dir_variable_controlled_diverse_{level}"
    report_dir = PROJECT_ROOT / f"variable_controlled_diversity_{level}_build_report"

    rows = []
    for dataset in args.datasets:
        row = build_dataset(
            dataset=dataset,
            source_root=args.source_root,
            level=level,
            max_level=args.max_level,
            line_budget=args.lines_per_template,
            human_root=human_root,
            eval_root=eval_root,
            report_dir=report_dir,
            require_full_level=args.require_full_level,
        )
        rows.append(row)
        print(
            f"  {dataset}: selected={row['selected_templates']} "
            f"variable={row['selected_variable_templates']} output={row['output_lines']}"
        )

    manifest_fields = [
        "dataset",
        "level",
        "source_file",
        "source_lines",
        "selected_templates",
        "selected_variable_templates",
        "skipped_templates",
        "output_lines",
        "avg_real_variants_per_selected_template",
        "human_output_file",
        "eval_output_file",
    ]
    write_csv(report_dir / f"variable_controlled_diversity_{level}_manifest.csv", rows, manifest_fields)

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
    parser = argparse.ArgumentParser(description="Build controlled variable-value diversity levels.")
    parser.add_argument("--levels", nargs="*", type=int, default=list(range(1, 9)))
    parser.add_argument("--datasets", nargs="*", default=DATASETS)
    parser.add_argument("--source-root", type=Path, default=DEFAULT_SOURCE_ROOT)
    parser.add_argument("--next-test-data", type=Path, default=DEFAULT_NEXT_TEST_DATA)
    parser.add_argument("--max-level", type=int, default=8)
    parser.add_argument("--lines-per-template", type=int, default=16)
    parser.add_argument(
        "--require-full-level",
        action="store_true",
        help="Keep only variable templates with at least max-level real variants.",
    )
    parser.add_argument("--copy-to-next-test", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    args.datasets = [dataset for dataset in args.datasets if dataset in DATASETS]
    if args.lines_per_template < 1:
        raise ValueError("--lines-per-template must be >= 1")
    for level in args.levels:
        print(f"Building controlled variable diversity level {level}")
        build_level(args, level)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
