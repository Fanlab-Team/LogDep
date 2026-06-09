#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Build datasets targeted at EntropyCaculate diversity scores 0.1 ... 0.9.

The original logs have a low average diversity ceiling under the current
metric, so the default calibrated mode keeps each dataset's log-format shell
and line count, then generates one controlled template whose token-position
variation targets the requested score. Use --mode template_tail to instead
append a controlled tail to dir_diversity_1 lines, preserving more of the
previously constructed low-diversity source.

Outputs:
  dir_diversity_score_0_1/<Dataset>/<Dataset>_diversity_score_0_1.log
  data/dir_diverse_score_0_1/<Dataset>/<Dataset>_diverse_score_0_1.log
  diversity_score_targets_report/
"""

from __future__ import annotations

import argparse
import csv
import math
import os
import sys
from pathlib import Path
from typing import Iterable, List, Sequence


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


def letters(number: int) -> str:
    alphabet = "abcdefghijklmnopqrstuvwxyz"
    result = ""
    number = int(number)
    while True:
        result = alphabet[number % 26] + result
        number //= 26
        if number == 0:
            return result


def target_slug(target: float) -> str:
    return f"{target:.1f}".replace(".", "_")


def parse_targets(values: Iterable[str]) -> List[float]:
    targets = []
    for value in values:
        target = float(value)
        if target <= 0.0 or target >= 1.0:
            raise ValueError("target diversity scores must be between 0 and 1")
        targets.append(round(target, 1))
    return targets


def base_file(dataset: str, base_root: Path) -> Path:
    candidate = base_root / dataset / f"{dataset}_diversity_1.log"
    if candidate.exists():
        return candidate
    raise FileNotFoundError(f"Missing base file: {candidate}")


def tail_plan(lines: Sequence[str], target: float) -> tuple[int, int, int, float]:
    avg_len = sum(len(line.split()) for line in lines) / max(len(lines), 1)

    # Choose enough tail positions so the requested ratio is reachable even
    # when the original log prefix is long. The +80 is a stability margin.
    min_tail = math.ceil(target * (avg_len + 1) / max(1.0 - target, 1e-9))
    total_tail = max(60, min_tail + 80)

    variable_tail = round(target * (avg_len + 1 + total_tail))
    variable_tail = max(1, min(total_tail, variable_tail))
    fixed_tail = total_tail - variable_tail
    return total_tail, variable_tail, fixed_tail, avg_len


def tail_plan_from_length(avg_len: float, target: float) -> tuple[int, int, int]:
    min_tail = math.ceil(target * (avg_len + 1) / max(1.0 - target, 1e-9))
    total_tail = max(60, min_tail + 80)
    variable_tail = round(target * (avg_len + 1 + total_tail))
    variable_tail = max(1, min(total_tail, variable_tail))
    fixed_tail = total_tail - variable_tail
    return total_tail, variable_tail, fixed_tail


def variable_suffix(line_index: int, token_index: int) -> str:
    value = (line_index * 1103515245 + token_index * 12345) >> 8
    return "a" if (value & 1) == 0 else "b"


def controlled_tail(line_index: int, variable_tail: int, fixed_tail: int) -> str:
    # Two values are enough: the diversity metric only checks whether a token
    # position has at least two distinct values. The per-position hash avoids a
    # single global A/B split that some parsers separate into two groups.
    tokens = ["dganchor"]
    tokens.extend(
        f"zv{letters(i)}<*>{variable_suffix(line_index, i)}"
        for i in range(variable_tail)
    )
    tokens.extend(f"zf{letters(i)}" for i in range(fixed_tail))
    return " ".join(tokens)


def format_shell(dataset: str, content: str) -> str:
    shells = {
        "HDFS": "081109 203518 143 INFO dfs.DataNode: {content}",
        "Hadoop": "2015-10-18 18:01:47 INFO [main] org.apache.hadoop.Service: {content}",
        "Spark": "17/06/09 20:10:40 INFO executor.CoarseGrainedExecutorBackend: {content}",
        "Zookeeper": "2015-07-29 17:41:47 - INFO  [main:ZooKeeperServer@123] - {content}",
        "BGL": "- 1117838570 2005.06.03 R02-M1-N0-C:J12-U11 2005-06-03-15.42.50.363779 R02-M1-N0-C:J12-U11 RAS KERNEL INFO {content}",
        "HPC": "1 node-1 component state 10 flag {content}",
        "Thunderbird": "- 1131566461 2005.11.09 user Nov 9 12:00:00 location component[123]: {content}",
        "Windows": "2016-09-28 04:30:30, INFO                  Service    {content}",
        "Linux": "Jun 14 15:16:01 INFO kernel[123]: {content}",
        "Android": "03-17 16:13:38.811  1702  2395 I ActivityManager: {content}",
        "HealthApp": "00:00:00|HealthComponent|100|{content}",
        "Apache": "[Sun Dec 04 04:47:44 2005] [notice] {content}",
        "OpenSSH": "Dec 10 06:55:46 LabSZ sshd[123]: {content}",
        "OpenStack": "1 2017-05-14 19:39:01.445 25746 INFO nova.compute.manager [req-abc] {content}",
        "Mac": "Jul  1 09:00:00 user kernel[0]: {content}",
        "Proxifier": "[10:00] proxy.exe - {content}",
    }
    return shells[dataset].format(content=content)


def build_calibrated_dataset(
    dataset: str,
    target: float,
    base_root: Path,
    human_root: Path,
    eval_root: Path,
) -> dict:
    source = base_file(dataset, base_root)
    line_count = len(read_lines(source))
    avg_len = len(format_shell(dataset, "dganchor").split())
    total_tail, variable_tail, fixed_tail = tail_plan_from_length(avg_len, target)

    generated = [
        format_shell(dataset, controlled_tail(i, variable_tail, fixed_tail))
        for i in range(line_count)
    ]

    slug = target_slug(target)
    human_file = human_root / dataset / f"{dataset}_diversity_score_{slug}.log"
    eval_file = eval_root / dataset / f"{dataset}_diverse_score_{slug}.log"
    written_count = write_lines(human_file, generated)
    write_lines(eval_file, generated)

    return {
        "target_score": f"{target:.1f}",
        "dataset": dataset,
        "source_file": str(source),
        "generation_mode": "calibrated",
        "output_lines": written_count,
        "average_source_token_length": f"{avg_len:.4f}",
        "tail_tokens": total_tail,
        "variable_tail_tokens": variable_tail,
        "fixed_tail_tokens": fixed_tail,
        "human_output_file": str(human_file),
        "eval_output_file": str(eval_file),
    }


def build_dataset(
    dataset: str,
    target: float,
    base_root: Path,
    human_root: Path,
    eval_root: Path,
) -> dict:
    source = base_file(dataset, base_root)
    lines = read_lines(source)
    total_tail, variable_tail, fixed_tail, avg_len = tail_plan(lines, target)

    generated = [
        f"{line} {controlled_tail(i, variable_tail, fixed_tail)}"
        for i, line in enumerate(lines)
    ]

    slug = target_slug(target)
    human_file = human_root / dataset / f"{dataset}_diversity_score_{slug}.log"
    eval_file = eval_root / dataset / f"{dataset}_diverse_score_{slug}.log"
    line_count = write_lines(human_file, generated)
    write_lines(eval_file, generated)

    return {
        "target_score": f"{target:.1f}",
        "dataset": dataset,
        "source_file": str(source),
        "generation_mode": "template_tail",
        "output_lines": line_count,
        "average_source_token_length": f"{avg_len:.4f}",
        "tail_tokens": total_tail,
        "variable_tail_tokens": variable_tail,
        "fixed_tail_tokens": fixed_tail,
        "human_output_file": str(human_file),
        "eval_output_file": str(eval_file),
    }


def verify_dataset(dataset: str, target: float, eval_root: Path) -> float:
    old_cwd = Path.cwd()
    slug = target_slug(target)
    try:
        os.chdir(SCRIPT_DIR)
        return EC.E_dataset(
            f"../data/dir_diverse_score_{slug}/{dataset}/",
            f"{dataset}_diverse_score_{slug}.log",
            dataset,
        )
    finally:
        os.chdir(old_cwd)


def write_csv(path: Path, rows: Sequence[dict], fieldnames: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build datasets targeted at EntropyCaculate diversity scores."
    )
    parser.add_argument(
        "--targets",
        nargs="*",
        default=[f"0.{i}" for i in range(1, 10)],
        help="Target scores, default: 0.1 ... 0.9",
    )
    parser.add_argument("--datasets", nargs="*", default=DATASETS)
    parser.add_argument(
        "--base-root",
        default=str(PROJECT_ROOT / "dir_diversity_1"),
        help="Base directory derived from original logs.",
    )
    parser.add_argument(
        "--mode",
        choices=("calibrated", "template_tail"),
        default="calibrated",
        help="calibrated targets the metric score closely; template_tail preserves more dir_diversity_1 content.",
    )
    parser.add_argument(
        "--no-verify",
        action="store_true",
        help="Only build files, skip EntropyCaculate verification.",
    )
    args = parser.parse_args(argv)

    targets = parse_targets(args.targets)
    datasets = [dataset for dataset in args.datasets if dataset in DATASETS]
    base_root = Path(args.base_root)
    report_dir = PROJECT_ROOT / "diversity_score_targets_report"

    manifest_rows = []
    verify_rows = []

    for target in targets:
        slug = target_slug(target)
        human_root = PROJECT_ROOT / f"dir_diversity_score_{slug}"
        eval_root = PROJECT_ROOT / "data" / f"dir_diverse_score_{slug}"
        print(f"Building target diversity score {target:.1f}")

        for dataset in datasets:
            if args.mode == "calibrated":
                row = build_calibrated_dataset(dataset, target, base_root, human_root, eval_root)
            else:
                row = build_dataset(dataset, target, base_root, human_root, eval_root)
            manifest_rows.append(row)

            actual_score = None
            if not args.no_verify:
                actual_score = verify_dataset(dataset, target, eval_root)
                verify_rows.append(
                    {
                        "target_score": f"{target:.1f}",
                        "dataset": dataset,
                        "actual_diversity_score": actual_score,
                        "absolute_error": abs(actual_score - target),
                    }
                )

            score_text = "not_verified" if actual_score is None else f"{actual_score:.4f}"
            print(
                f"  {dataset}: lines={row['output_lines']} "
                f"tail={row['tail_tokens']} variable={row['variable_tail_tokens']} "
                f"actual={score_text}"
            )

    manifest_fields = [
        "target_score",
        "dataset",
        "source_file",
        "generation_mode",
        "output_lines",
        "average_source_token_length",
        "tail_tokens",
        "variable_tail_tokens",
        "fixed_tail_tokens",
        "human_output_file",
        "eval_output_file",
    ]
    write_csv(
        report_dir / "diversity_score_targets_manifest.csv",
        manifest_rows,
        manifest_fields,
    )

    if verify_rows:
        summary_rows = []
        for target in targets:
            rows = [r for r in verify_rows if r["target_score"] == f"{target:.1f}"]
            avg_score = sum(float(r["actual_diversity_score"]) for r in rows) / len(rows)
            avg_error = sum(float(r["absolute_error"]) for r in rows) / len(rows)
            summary_rows.append(
                {
                    "target_score": f"{target:.1f}",
                    "dataset": "AVERAGE",
                    "actual_diversity_score": avg_score,
                    "absolute_error": avg_error,
                }
            )

        verify_fields = [
            "target_score",
            "dataset",
            "actual_diversity_score",
            "absolute_error",
        ]
        write_csv(
            report_dir / "diversity_score_targets_verify.csv",
            verify_rows + summary_rows,
            verify_fields,
        )

    print(f"manifest={report_dir / 'diversity_score_targets_manifest.csv'}")
    if verify_rows:
        print(f"verify={report_dir / 'diversity_score_targets_verify.csv'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
