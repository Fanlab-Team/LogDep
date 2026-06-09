#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Build diversity-controlled datasets from corrected ground-truth templates.

The recommended ``ground-truth`` construction mode targets a parser-independent
LD value. It balances:
1. the fraction of true template groups whose variables are activated; and
2. the normalized entropy of variable values inside activated groups.

The legacy mode is retained only for reproducing earlier development results.
"""

from __future__ import annotations

import argparse
import csv
import math
import random
import re
import shutil
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Sequence


SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
DEFAULT_SOURCE_ROOT = PROJECT_ROOT / "data" / "raw_2k"
DEFAULT_NEXT_TEST_DATA = PROJECT_ROOT / "data"
DEFAULT_DATA_OUTPUT_ROOT = PROJECT_ROOT / "data" / "gtld"
DEFAULT_RESULTS_OUTPUT_ROOT = PROJECT_ROOT / "results" / "ground_truth_diversity"
DEFAULT_CALIBRATION_FILE = DEFAULT_RESULTS_OUTPUT_ROOT / "calibration.csv"

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


def slug(score: float) -> str:
    return f"{score:.1f}".replace(".", "_")


def read_calibration(path: Path | None) -> Dict[str, dict]:
    if path is None or not path.is_file():
        return {}
    rows = read_csv_rows(path)
    return {
        f"{float(row['target_score']):.1f}": row
        for row in rows
        if row.get("target_score")
    }


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


def normalized_entropy_from_counts(counts: Sequence[int]) -> float:
    total = sum(counts)
    if total <= 1:
        return 0.0
    entropy = 0.0
    for count in counts:
        if count <= 0:
            continue
        probability = count / total
        entropy -= probability * math.log(probability)
    return entropy / math.log(total)


def balanced_counts(total: int, buckets: int) -> List[int]:
    base = total // buckets
    remainder = total % buckets
    return [base + (1 if idx < remainder else 0) for idx in range(buckets)]


def target_entropy_sequence(total: int, target: float) -> tuple[List[int], float, List[int]]:
    """Return a variant-id sequence whose normalized entropy is close to target."""
    best_counts = [total]
    best_score = 0.0
    best_error = abs(target)

    for buckets in range(1, total + 1):
        # Balanced distribution over k values covers the high-entropy region.
        candidates = [balanced_counts(total, buckets)]

        # Skewed distributions cover low and middle entropy more finely.
        for dominant in range(max(1, math.ceil(total / buckets)), total - buckets + 2):
            remaining = total - dominant
            if buckets == 1:
                counts = [total]
            else:
                counts = [dominant] + balanced_counts(remaining, buckets - 1)
            candidates.append(counts)

        for counts in candidates:
            score = normalized_entropy_from_counts(counts)
            error = abs(score - target)
            if error < best_error:
                best_error = error
                best_score = score
                best_counts = counts

    sequence = []
    for variant_id, count in enumerate(best_counts):
        sequence.extend([variant_id] * count)
    return sequence[:total], best_score, best_counts


def inactive_value_for(slot_idx: int) -> str:
    slot_prefix = chr(ord("a") + (slot_idx % 26)) * 2
    return f"{slot_prefix}alpha"


def active_value_for(dataset: str, slot_idx: int, variant_idx: int) -> str:
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


def fill_template(dataset: str, template: str, variant_idx: int | None) -> str:
    slot = 0

    def repl(_: re.Match[str]) -> str:
        nonlocal slot
        if variant_idx is None:
            value = inactive_value_for(slot)
        else:
            value = active_value_for(dataset, slot, variant_idx)
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
        raw_line = raw_lines[line_id - 1]
        if replace_content(raw_line, sample.get("Content", ""), fill_template(dataset, template, None)) is None:
            continue
        selected.append(
            {
                "event_id": event_id,
                "template": template,
                "line_id": line_id,
                "original_content": sample.get("Content", ""),
                "raw_line": raw_line,
                "placeholder_count": placeholder_count(template),
            }
        )
    return selected


def ground_truth_parameters(group_count: int, target_score: float) -> tuple[int, float, float]:
    """Choose breadth and depth so their product targets the requested GTLD."""
    if group_count <= 0:
        return 0, 0.0, 0.0
    target_score = min(1.0, max(0.0, target_score))
    active_count = min(
        group_count,
        max(1, round(group_count * math.sqrt(target_score))),
    )
    activation_ratio = active_count / group_count
    slot_entropy_target = min(1.0, target_score / activation_ratio)
    return active_count, activation_ratio, slot_entropy_target


def build_dataset(
    dataset: str,
    source_root: Path,
    target_score: float,
    activation_ratio: float,
    active_slot_entropy_target: float,
    lines_per_template: int,
    max_placeholders: int,
    max_template_length: int,
    human_root: Path,
    eval_root: Path,
    report_dir: Path,
    construction_mode: str,
    template_order_seed: int,
) -> dict:
    selected = selected_templates(dataset, source_root, max_placeholders, max_template_length)
    requested_activation_ratio = activation_ratio
    requested_slot_entropy = active_slot_entropy_target
    if construction_mode == "ground-truth":
        random.Random(f"{template_order_seed}:{dataset}").shuffle(selected)
        requested_activation_ratio = math.sqrt(min(1.0, max(0.0, target_score)))
        active_count, activation_ratio, active_slot_entropy_target = ground_truth_parameters(
            len(selected),
            target_score,
        )
        requested_slot_entropy = active_slot_entropy_target
    else:
        active_count = min(len(selected), math.ceil(len(selected) * activation_ratio))
        activation_ratio = active_count / len(selected) if selected else 0.0

    variant_sequence, achieved_entropy, counts = target_entropy_sequence(
        lines_per_template,
        active_slot_entropy_target,
    )
    output_lines: List[str] = []
    group_rows = []

    for idx, item in enumerate(selected):
        is_active = idx < active_count
        start_line_id = len(output_lines) + 1
        for line_idx in range(lines_per_template):
            variant_idx = variant_sequence[line_idx] if is_active else None
            content = fill_template(dataset, item["template"], variant_idx)
            line = replace_content(item["raw_line"], item["original_content"], content)
            if line is not None:
                output_lines.append(line)
        end_line_id = len(output_lines)
        group_ground_truth_ld = achieved_entropy if is_active else 0.0
        group_rows.append(
            {
                "dataset": dataset,
                "target_score": target_score,
                "construction_mode": construction_mode,
                "selection_rank": idx + 1,
                "requested_activation_ratio": requested_activation_ratio,
                "activation_ratio": activation_ratio,
                "event_id": item["event_id"],
                "active": int(is_active),
                "line_budget": lines_per_template,
                "start_line_id": start_line_id,
                "end_line_id": end_line_id,
                "requested_entropy_per_active_slot": requested_slot_entropy,
                "target_entropy_per_active_slot": active_slot_entropy_target,
                "achieved_entropy_per_active_slot": achieved_entropy,
                "ground_truth_group_ld": group_ground_truth_ld,
                "value_counts": " ".join(str(count) for count in counts),
                "placeholder_count": item["placeholder_count"],
                "template": item["template"],
            }
        )

    score_slug = slug(target_score)
    human_file = human_root / dataset / f"{dataset}.log"
    eval_file = eval_root / dataset / f"{dataset}.log"
    write_lines(human_file, output_lines)
    write_lines(eval_file, output_lines)

    group_fields = [
        "dataset",
        "target_score",
        "construction_mode",
        "selection_rank",
        "requested_activation_ratio",
        "activation_ratio",
        "event_id",
        "active",
        "line_budget",
        "start_line_id",
        "end_line_id",
        "requested_entropy_per_active_slot",
        "target_entropy_per_active_slot",
        "achieved_entropy_per_active_slot",
        "ground_truth_group_ld",
        "value_counts",
        "placeholder_count",
        "template",
    ]
    write_csv(
        report_dir / "template_groups" / f"{dataset}_groups.csv",
        group_rows,
        group_fields,
    )

    return {
        "dataset": dataset,
        "target_score": target_score,
        "construction_mode": construction_mode,
        "selected_templates": len(selected),
        "active_templates": active_count,
        "requested_activation_ratio": requested_activation_ratio,
        "activation_ratio": activation_ratio,
        "requested_entropy_per_active_slot": requested_slot_entropy,
        "target_entropy_per_active_slot": active_slot_entropy_target,
        "achieved_entropy_per_active_slot": achieved_entropy,
        "ground_truth_ld": (
            sum(float(row["ground_truth_group_ld"]) for row in group_rows) / len(group_rows)
            if group_rows
            else 0.0
        ),
        "output_lines": len(output_lines),
        "human_output_file": str(human_file),
        "eval_output_file": str(eval_file),
    }


def build_target(args: argparse.Namespace, target_score: float) -> List[dict]:
    score_slug = slug(target_score)
    human_root = args.results_output_root / "generated_logs" / f"level_{score_slug}"
    eval_root = args.data_output_root / f"{args.data_prefix}_{score_slug}"
    report_dir = args.results_output_root / "build_reports" / f"level_{score_slug}"
    calibrated = args.calibration.get(f"{target_score:.1f}", {})
    activation_ratio = (
        args.activation_ratio
        if args.activation_ratio is not None
        else float(calibrated.get("activation_ratio", target_score))
    )
    active_slot_entropy = (
        args.slot_entropy
        if args.slot_entropy is not None
        else float(calibrated.get("calibrated_slot_entropy", target_score))
    )

    rows = []
    for dataset in args.datasets:
        row = build_dataset(
            dataset,
            args.source_root,
            target_score,
            activation_ratio,
            active_slot_entropy,
            args.lines_per_template,
            args.max_placeholders,
            args.max_template_length,
            human_root,
            eval_root,
            report_dir,
            args.construction_mode,
            args.template_order_seed,
        )
        rows.append(row)
        print(
            f"  {dataset}: selected={row['selected_templates']} "
            f"active={row['active_templates']} output={row['output_lines']} "
            f"activation={row['activation_ratio']:.4f} "
            f"slot_entropy={row['achieved_entropy_per_active_slot']:.4f} "
            f"GTLD={row['ground_truth_ld']:.4f}"
        )

    fields = [
        "dataset",
        "target_score",
        "construction_mode",
        "selected_templates",
        "active_templates",
        "requested_activation_ratio",
        "activation_ratio",
        "requested_entropy_per_active_slot",
        "target_entropy_per_active_slot",
        "achieved_entropy_per_active_slot",
        "ground_truth_ld",
        "output_lines",
        "human_output_file",
        "eval_output_file",
    ]
    write_csv(report_dir / "manifest.csv", rows, fields)

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
    parser = argparse.ArgumentParser(description="Build parser-independent diversity datasets.")
    parser.add_argument("--targets", nargs="*", type=float, default=[i / 10 for i in range(1, 10)])
    parser.add_argument("--datasets", nargs="*", default=DATASETS)
    parser.add_argument("--source-root", type=Path, default=DEFAULT_SOURCE_ROOT)
    parser.add_argument("--next-test-data", type=Path, default=DEFAULT_NEXT_TEST_DATA)
    parser.add_argument("--data-output-root", type=Path, default=DEFAULT_DATA_OUTPUT_ROOT)
    parser.add_argument("--data-prefix", default="diversity")
    parser.add_argument("--results-output-root", type=Path, default=DEFAULT_RESULTS_OUTPUT_ROOT)
    parser.add_argument("--calibration-file", type=Path, default=DEFAULT_CALIBRATION_FILE)
    parser.add_argument("--ignore-calibration", action="store_true")
    parser.add_argument("--lines-per-template", type=int, default=64)
    parser.add_argument("--max-placeholders", type=int, default=8)
    parser.add_argument("--max-template-length", type=int, default=220)
    parser.add_argument("--activation-ratio", type=float, default=None)
    parser.add_argument("--slot-entropy", type=float, default=None)
    parser.add_argument(
        "--construction-mode",
        choices=["ground-truth", "legacy"],
        default="ground-truth",
        help="Use true template groups to target GTLD, or reproduce the legacy builder.",
    )
    parser.add_argument(
        "--template-order-seed",
        type=int,
        default=20260604,
        help="Fixed seed used to select a nested, unbiased set of active true templates.",
    )
    parser.add_argument("--copy-to-next-test", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    args.datasets = [dataset for dataset in args.datasets if dataset in DATASETS]
    args.calibration = (
        {} if args.ignore_calibration else read_calibration(args.calibration_file)
    )
    for target_score in args.targets:
        print(f"Building entropy target {target_score:.1f}")
        build_target(args, target_score)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
