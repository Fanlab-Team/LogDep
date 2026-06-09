#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Variable-value diversity calculator for log datasets.

This script is intentionally separate from `entropy_metrics.py`. The old metric
counts how many token positions vary inside a template group. This metric only
looks at variable positions in the parsed template and measures how many
different values each variable position takes.

Primary score:
  normalized entropy of values at each variable position, averaged over all
  variable positions. The score is in [0, 1].

Secondary score:
  normalized distinct ratio, (unique_values - 1) / (group_size - 1), also in
  [0, 1].
"""

from __future__ import annotations

import argparse
import csv
import datetime
import math
import os
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Iterable, List, Sequence

import pandas as pd


SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(SCRIPT_DIR))

import brain_parser as Ba
import entropy_metrics as EC


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


BENCHMARK_SETTINGS = {
    "Proxifier": {
        "regex": [r"<\d+\ssec", r"([\w-]+\.)+[\w-]+(:\d+)?", r"\d{2}:\d{2}(:\d{2})*", r"[KGTM]B"],
        "delimiter": [r"\(.*?\)"],
        "tag": 0,
        "theshold": 3,
    },
    "HDFS": {
        "regex": [r"blk_-?\d+", r"(\d+\.){3}\d+(:\d+)?"],
        "delimiter": [""],
        "tag": 0,
        "theshold": 2,
    },
    "Hadoop": {
        "regex": [r"(\d+\.){3}\d+"],
        "delimiter": [],
        "tag": 1,
        "theshold": 6,
    },
    "Spark": {
        "regex": [r"(\d+\.){3}\d+", r"\b[KGTM]?B\b", r"([\w-]+\.){2,}[\w-]+"],
        "delimiter": [],
        "tag": 0,
        "theshold": 4,
    },
    "Zookeeper": {
        "regex": [r"(/|)(\d+\.){3}\d+(:\d+)?"],
        "delimiter": [],
        "tag": 1,
        "theshold": 3,
    },
    "BGL": {
        "regex": [r"core\.\d+"],
        "delimiter": [],
        "tag": 0,
        "theshold": 6,
    },
    "HPC": {"regex": [], "delimiter": [], "tag": 0, "theshold": 5},
    "Thunderbird": {
        "regex": [r"(\d+\.){3}\d+"],
        "delimiter": [],
        "tag": 0,
        "theshold": 3,
    },
    "Windows": {
        "regex": [r"0x.*?\s"],
        "delimiter": [],
        "tag": 0,
        "theshold": 3,
    },
    "Linux": {
        "regex": [r"(\d+\.){3}\d+", r"\d{2}:\d{2}:\d{2}", r"J([a-z]{2})"],
        "delimiter": [r""],
        "tag": 0,
        "theshold": 4,
    },
    "Android": {
        "regex": [
            r"(/[\w-]+)+",
            r"([\w-]+\.){2,}[\w-]+",
            r"\b(\-?\+?\d+)\b|\b0[Xx][a-fA-F\d]+\b|\b[a-fA-F\d]{4,}\b",
        ],
        "delimiter": [r""],
        "tag": 0,
        "theshold": 5,
    },
    "HealthApp": {"regex": [], "delimiter": [r""], "tag": 0, "theshold": 4},
    "Apache": {
        "regex": [r"(\d+\.){3}\d+"],
        "delimiter": [],
        "tag": 0,
        "theshold": 4,
    },
    "OpenSSH": {
        "regex": [r"(\d+\.){3}\d+", r"([\w-]+\.){2,}[\w-]+"],
        "delimiter": [],
        "tag": 0,
        "theshold": 6,
    },
    "OpenStack": {
        "regex": [r"((\d+\.){3}\d+,?)+", r"/.+?\s ", r"\d+"],
        "delimiter": [],
        "tag": 0,
        "theshold": 6,
    },
    "Mac": {
        "regex": [r"([\w-]+\.){2,}[\w-]+"],
        "delimiter": [],
        "tag": 0,
        "theshold": 5,
    },
}


LOG_FORMATS = {
    "Proxifier": r"\[<Time>\] <Program> - <Content>",
    "HDFS": r"<Date> <Time> <Pid> <Level> <Component>: <Content>",
    "Hadoop": r"<Date> <Time> <Level> \[<Process>\] <Component>: <Content>",
    "Spark": r"<Date> <Time> <Level> <Component>: <Content>",
    "Zookeeper": r"<Date> <Time> - <Level>  \[<Node>:<Component>@<Id>\] - <Content>",
    "BGL": r"<Label> <Timestamp> <Date> <Node> <Time> <NodeRepeat> <Type> <Component> <Level> <Content>",
    "HPC": r"<LogId> <Node> <Component> <State> <Time> <Flag> <Content>",
    "Thunderbird": r"<Label> <Timestamp> <Date> <User> <Month> <Day> <Time> <Location> <Component>(\[<PID>\])?: <Content>",
    "Windows": r"<Date> <Time>, <Level>                  <Component>    <Content>",
    "Linux": r"<Month> <Date> <Time> <Level> <Component>(\[<PID>\])?: <Content>",
    "Android": r"<Date> <Time>  <Pid>  <Tid> <Level> <Component>: <Content>",
    "HealthApp": r"<Time>\|<Component>\|<Pid>\|<Content>",
    "Apache": r"\[<Time>\] \[<Level>\] <Content>",
    "OpenSSH": r"<Date> <Day> <Time> <Component> sshd\[<Pid>\]: <Content>",
    "OpenStack": r"<Logrecord> <Date> <Time> <Pid> <Level> <Component> \[<ADDR>\] <Content>",
    "Mac": r"<Month>  <Date> <Time> <User> <Component>\[<PID>\]( \(<Address>\))?: <Content>",
}


def read_lines(path: Path) -> List[str]:
    for encoding in ("utf-8", "utf-8-sig", "gbk", "latin-1"):
        try:
            with path.open("r", encoding=encoding) as f:
                return [line.rstrip("\r\n") for line in f if line.strip()]
        except UnicodeDecodeError:
            continue
    raise UnicodeDecodeError("unknown", b"", 0, 1, f"Cannot decode {path}")


def split_sentence(value: str) -> List[str]:
    return [token for token in re.sub(r" +", " ", value).strip().split(" ") if token]


def parse_indices(value: str) -> List[int]:
    indices = []
    for part in str(value).strip().strip('"').split(","):
        part = part.strip()
        if part:
            indices.append(int(part))
    return indices


def infer_suffix(data_dir: str) -> str:
    if data_dir == "logs":
        return "2k"
    if data_dir.startswith("dir_"):
        return data_dir[len("dir_") :]
    return data_dir


def find_log_file(dataset: str, root: Path, data_dir: str, flat: bool) -> Path:
    suffix = infer_suffix(data_dir)
    names = [
        f"{dataset}_{suffix}.log",
        f"{dataset}_{suffix}.logs",
        f"{dataset}_2k.log",
        f"{dataset}_2k.logs",
        f"{dataset}.log",
        f"{dataset}.logs",
    ]
    dirs = [root] if flat else [root / dataset, root]
    for directory in dirs:
        for name in names:
            candidate = directory / name
            if candidate.exists():
                return candidate
    raise FileNotFoundError(f"Cannot find log file for {dataset} under {root}")


def generate_logformat_regex(log_format: str) -> re.Pattern[str]:
    regex = ""
    splitters = re.split(r"(<[^<>]+>)", log_format)
    for idx, splitter in enumerate(splitters):
        if idx % 2 == 0:
            regex += re.sub(r" +", r"\\s+", splitter)
        else:
            header = splitter.strip("<").strip(">")
            regex += rf"(?P<{header}>.*?)"
    return re.compile("^" + regex + "$")


def extract_content_lines(dataset: str, raw_lines: Sequence[str]) -> tuple[List[str], int]:
    """Return Content-only lines while preserving row order for group indices."""
    log_format = LOG_FORMATS.get(dataset)
    if not log_format:
        return list(raw_lines), len(raw_lines)

    regex = generate_logformat_regex(log_format)
    content_lines = []
    failed = 0
    for line in raw_lines:
        match = regex.search(line.strip())
        if match is None:
            content_lines.append(line)
            failed += 1
        else:
            content_lines.append(match.group("Content"))
    return content_lines, failed


def read_template_groups(path: Path) -> List[tuple[str, List[int]]]:
    for encoding in ("gbk", "utf-8-sig", "utf-8"):
        try:
            with path.open("r", encoding=encoding, newline="") as f:
                reader = csv.DictReader(f)
                rows = []
                for row in reader:
                    keys = list(row.keys())
                    template = row.get("妯℃澘") or row.get("模板") or row.get(keys[0]) or ""
                    index_value = row.get("鍙ュ瓙鏍囧彿") or row.get("句子标号") or row.get(keys[1]) or ""
                    rows.append((template, parse_indices(index_value)))
                return rows
        except UnicodeDecodeError:
            continue
    raise UnicodeDecodeError("unknown", b"", 0, 1, f"Cannot decode {path}")


def value_tokenize(lines: Sequence[str], dataset: str) -> List[List[str]]:
    # Keep raw variable values. Passing an empty regex list preserves IPs,
    # block IDs, paths, numbers, and other values that entropy_metrics replaces.
    normalized = EC.get_united_sentences(list(lines), dataset, [])
    return [split_sentence(sentence) for sentence in normalized]


def normalized_entropy(values: Sequence[str], group_size: int) -> float:
    if group_size <= 1 or len(values) <= 1:
        return 0.0
    counts = Counter(values)
    if len(counts) <= 1:
        return 0.0
    total = sum(counts.values())
    entropy = 0.0
    for count in counts.values():
        probability = count / total
        entropy -= probability * math.log(probability)
    return entropy / math.log(group_size)


def normalized_distinct_ratio(values: Sequence[str], group_size: int) -> float:
    if group_size <= 1 or len(values) <= 1:
        return 0.0
    return (len(set(values)) - 1) / (group_size - 1)


def variable_positions(template: str) -> List[int]:
    tokens = split_sentence(template)
    return [idx for idx, token in enumerate(tokens) if "<*>" in token or token == "*"]


def calculate_from_groups(
    analysis_lines: Sequence[str],
    dataset: str,
    group_file: Path,
) -> tuple[dict, List[dict]]:
    value_tokens = value_tokenize(analysis_lines, dataset)
    groups = read_template_groups(group_file)

    details = []
    weighted_entropy_sum = 0.0
    weighted_distinct_sum = 0.0
    weight_sum = 0.0
    unweighted_entropy_sum = 0.0
    unweighted_distinct_sum = 0.0
    variable_position_count = 0
    variable_template_count = 0
    max_distinct_values = 0
    distinct_value_sum = 0.0

    for group_id, (template, indices) in enumerate(groups):
        valid_indices = [idx for idx in indices if 0 <= idx < len(value_tokens)]
        group_size = len(valid_indices)
        var_positions = variable_positions(template)
        if not var_positions:
            continue
        variable_template_count += 1

        template_entropy_scores = []
        template_distinct_scores = []
        template_distinct_counts = []

        for position in var_positions:
            values = [
                value_tokens[idx][position]
                for idx in valid_indices
                if position < len(value_tokens[idx])
            ]
            if not values:
                continue

            distinct_count = len(set(values))
            entropy_score = normalized_entropy(values, group_size)
            distinct_score = normalized_distinct_ratio(values, group_size)

            template_entropy_scores.append(entropy_score)
            template_distinct_scores.append(distinct_score)
            template_distinct_counts.append(distinct_count)

            weighted_entropy_sum += entropy_score * group_size
            weighted_distinct_sum += distinct_score * group_size
            weight_sum += group_size
            unweighted_entropy_sum += entropy_score
            unweighted_distinct_sum += distinct_score
            variable_position_count += 1
            distinct_value_sum += distinct_count
            max_distinct_values = max(max_distinct_values, distinct_count)

        if template_entropy_scores:
            details.append(
                {
                    "dataset": dataset,
                    "group_id": group_id,
                    "group_size": group_size,
                    "variable_positions": len(template_entropy_scores),
                    "template_entropy_diversity": sum(template_entropy_scores) / len(template_entropy_scores),
                    "template_distinct_ratio_diversity": sum(template_distinct_scores) / len(template_distinct_scores),
                    "avg_distinct_values": sum(template_distinct_counts) / len(template_distinct_counts),
                    "max_distinct_values": max(template_distinct_counts),
                    "template": template,
                }
            )

    summary = {
        "dataset": dataset,
        "line_count": len(analysis_lines),
        "template_groups": len(groups),
        "variable_templates": variable_template_count,
        "variable_positions": variable_position_count,
        "weighted_entropy_diversity": weighted_entropy_sum / weight_sum if weight_sum else 0.0,
        "unweighted_entropy_diversity": unweighted_entropy_sum / variable_position_count if variable_position_count else 0.0,
        "weighted_distinct_ratio_diversity": weighted_distinct_sum / weight_sum if weight_sum else 0.0,
        "unweighted_distinct_ratio_diversity": unweighted_distinct_sum / variable_position_count if variable_position_count else 0.0,
        "avg_distinct_values_per_variable": distinct_value_sum / variable_position_count if variable_position_count else 0.0,
        "max_distinct_values": max_distinct_values,
    }
    return summary, details


def calculate_dataset(
    dataset: str,
    log_file: Path,
    details_dir: Path | None = None,
    scope: str = "content",
) -> dict:
    setting = BENCHMARK_SETTINGS[dataset]
    raw_lines = read_lines(log_file)
    if scope == "content":
        analysis_lines, format_parse_failures = extract_content_lines(dataset, raw_lines)
    else:
        analysis_lines = raw_lines
        format_parse_failures = 0
    parse_sentences = EC.get_united_sentences(analysis_lines, dataset, setting["regex"])

    old_cwd = Path.cwd()
    try:
        os.chdir(SCRIPT_DIR)
        (PROJECT_ROOT / "log_after_group").mkdir(parents=True, exist_ok=True)
        start_time = datetime.datetime.now()
        Ba.parse_E(
            parse_sentences,
            setting["regex"],
            dataset,
            setting["theshold"],
            setting["delimiter"],
            setting["tag"],
            start_time,
            efficiency=False,
        )
        group_file = PROJECT_ROOT / "log_after_group" / f"{dataset}_template.csv"
        summary, details = calculate_from_groups(analysis_lines, dataset, group_file)
    finally:
        os.chdir(old_cwd)

    summary["source_file"] = str(log_file)
    summary["scope"] = scope
    summary["original_line_count"] = len(raw_lines)
    summary["format_parse_failures"] = format_parse_failures

    if details_dir is not None:
        details_dir.mkdir(parents=True, exist_ok=True)
        detail_path = details_dir / f"{dataset}_variable_diversity_details.csv"
        pd.DataFrame(details).to_csv(detail_path, index=False, encoding="utf-8-sig")
        summary["detail_file"] = str(detail_path)

    return summary


def write_summary(rows: Sequence[dict], output_file: Path) -> None:
    output_file.parent.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(rows)
    numeric_cols = [
        "original_line_count",
        "line_count",
        "format_parse_failures",
        "template_groups",
        "variable_templates",
        "variable_positions",
        "weighted_entropy_diversity",
        "unweighted_entropy_diversity",
        "weighted_distinct_ratio_diversity",
        "unweighted_distinct_ratio_diversity",
        "avg_distinct_values_per_variable",
        "max_distinct_values",
    ]
    avg = {"dataset": "AVERAGE", "source_file": ""}
    for col in numeric_cols:
        avg[col] = df[col].mean() if col in df else 0.0
    df = pd.concat([df, pd.DataFrame([avg])], ignore_index=True)
    df.to_csv(output_file, index=False, encoding="utf-8-sig")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Calculate variable-value diversity for log datasets.")
    parser.add_argument("--data-dir", default="dir_diverse_1", help="Directory name under data/, e.g. dir_diverse_1.")
    parser.add_argument("--input-root", default=None, help="Override input root. Defaults to data/<data-dir>.")
    parser.add_argument("--flat", action="store_true", help="Use when files are directly under input-root, e.g. logs/.")
    parser.add_argument("--datasets", nargs="*", default=DATASETS)
    parser.add_argument("--output", default=None, help="Output summary CSV path.")
    parser.add_argument("--details-dir", default=None, help="Optional directory for per-template details.")
    parser.add_argument(
        "--scope",
        choices=["content", "full"],
        default="content",
        help="Use Content-only text by default, or full raw lines for the old behavior.",
    )
    args = parser.parse_args(argv)

    input_root = Path(args.input_root) if args.input_root else PROJECT_ROOT / "data" / args.data_dir
    output = Path(args.output) if args.output else PROJECT_ROOT / f"variable_diversity_{args.data_dir}.csv"
    details_dir = Path(args.details_dir) if args.details_dir else None

    rows = []
    for dataset in args.datasets:
        if dataset not in DATASETS:
            print(f"Skip unknown dataset: {dataset}")
            continue
        log_file = find_log_file(dataset, input_root, args.data_dir, args.flat)
        print(f"Processing {dataset}: {log_file}")
        row = calculate_dataset(dataset, log_file, details_dir, scope=args.scope)
        rows.append(row)
        print(
            f"  weighted_entropy={row['weighted_entropy_diversity']:.4f}, "
            f"weighted_distinct={row['weighted_distinct_ratio_diversity']:.4f}, "
            f"avg_distinct={row['avg_distinct_values_per_variable']:.2f}"
        )

    write_summary(rows, output)
    print(f"[Done] summary={output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
