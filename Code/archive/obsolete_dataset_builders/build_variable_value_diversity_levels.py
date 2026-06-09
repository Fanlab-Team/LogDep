#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Build variable-value diversity datasets from original logs.

For level k = 1..8:
  - parse original logs into template groups;
  - identify variable positions (<*>) in each parsed template;
  - make each variable position take k distinct values when possible;
  - keep fixed template tokens unchanged;
  - repeat the k representative lines to a stable per-template output size.

This differs from build_diversity_level_from_logs.py: that script keeps up to k
whole log lines per template, while this script controls distinct values at
each variable slot.
"""

from __future__ import annotations

import argparse
import csv
import datetime
import os
import re
import sys
from pathlib import Path
from typing import Dict, Iterable, List, Sequence


SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(SCRIPT_DIR))

import Brain as Ba
import EntropyCaculate as EC
import VariableDiversityCaculate as VDC


DATASETS = VDC.DATASETS
SETTINGS = VDC.BENCHMARK_SETTINGS
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


def choose_log_file(dataset: str) -> Path:
    for suffix in (".log", ".logs"):
        candidate = LOGS_DIR / f"{dataset}_2k{suffix}"
        if candidate.exists():
            return candidate
    raise FileNotFoundError(f"No logs/{dataset}_2k.log(s) found")


def split_sentence(value: str) -> List[str]:
    return [token for token in re.sub(r" +", " ", value).strip().split(" ") if token]


def parse_indices(value: str) -> List[int]:
    indices = []
    for part in str(value).strip().strip('"').split(","):
        part = part.strip()
        if part:
            indices.append(int(part))
    return indices


def read_template_groups(path: Path) -> List[dict]:
    for encoding in ("gbk", "utf-8-sig", "utf-8"):
        try:
            with path.open("r", encoding=encoding, newline="") as f:
                reader = csv.DictReader(f)
                rows = []
                for row in reader:
                    keys = list(row.keys())
                    template = row.get("妯℃澘") or row.get("模板") or row.get(keys[0]) or ""
                    index_value = row.get("鍙ュ瓙鏍囧彿") or row.get("句子标号") or row.get(keys[1]) or ""
                    rows.append(
                        {
                            "template": template,
                            "indices": parse_indices(index_value),
                        }
                    )
                return rows
        except UnicodeDecodeError:
            continue
    raise UnicodeDecodeError("unknown", b"", 0, 1, f"Cannot decode {path}")


def variable_positions(template: str) -> List[int]:
    return [idx for idx, token in enumerate(split_sentence(template)) if "<*>" in token or token == "*"]


def parse_original_templates(dataset: str, raw_lines: Sequence[str]) -> List[dict]:
    setting = SETTINGS[dataset]
    parse_sentences = EC.get_united_sentences(list(raw_lines), dataset, setting["regex"])
    old_cwd = Path.cwd()
    try:
        os.chdir(SCRIPT_DIR)
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
        return read_template_groups(PROJECT_ROOT / "log_after_group" / f"{dataset}_template.csv")
    finally:
        os.chdir(old_cwd)


def unique_in_order(values: Iterable[str]) -> List[str]:
    seen = set()
    result = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def synthesize_value(seed: str, ordinal: int, dataset: str, position: int) -> str:
    if re.fullmatch(r"-?\d+", seed):
        base = int(seed)
        return str(base + ordinal + 1)
    if re.fullmatch(r"0[xX][0-9a-fA-F]+", seed):
        base = int(seed, 16)
        return hex(base + ordinal + 1)
    if re.fullmatch(r"blk_-?\d+", seed):
        prefix = "blk_- " if seed.startswith("blk_-") else "blk_"
        number = abs(int(re.sub(r"^blk_-?", "", seed)))
        return f"{prefix.replace(' ', '')}{number + ordinal + 1}"
    if re.fullmatch(r"(\d+\.){3}\d+(:\d+)?", seed):
        port = ""
        ip = seed
        if ":" in seed:
            ip, port = seed.split(":", 1)
            port = f":{int(port) + ordinal + 1}" if port.isdigit() else f":{port}{ordinal + 1}"
        parts = [int(part) for part in ip.split(".")]
        parts[-1] = (parts[-1] + ordinal + 1) % 255 or 1
        return ".".join(str(part) for part in parts) + port
    if re.fullmatch(r"\d{2}:\d{2}:\d{2}", seed):
        h, m, s = [int(part) for part in seed.split(":")]
        s = (s + ordinal + 1) % 60
        return f"{h:02d}:{m:02d}:{s:02d}"
    if "/" in seed:
        return f"{seed.rstrip('/')}/v{ordinal + 1}"
    clean = re.sub(r"[^A-Za-z0-9_.$-]", "", seed)
    clean = clean or f"value{position}"
    return f"{clean}_v{ordinal + 1}"


def expand_pool(pool: List[str], target: int, dataset: str, position: int) -> List[str]:
    if not pool:
        pool = [f"value{position}"]
    result = list(pool)
    seed = pool[0]
    ordinal = 0
    while len(result) < target:
        candidate = synthesize_value(seed, ordinal, dataset, position)
        ordinal += 1
        if candidate not in result:
            result.append(candidate)
    return result[:target]


def detokenize(dataset: str, tokens: Sequence[str]) -> str:
    line = " ".join(tokens)
    if dataset == "HealthApp":
        line = re.sub(r"\s*\|\s*", "|", line)
        line = re.sub(r"(\d{2}):\s+(\d{2}):\s+(\d{2})", r"\1:\2:\3", line)
    if dataset in {"Hadoop"}:
        line = line.replace("_ ", "_")
    if dataset in {"Android", "BGL", "Proxifier"}:
        line = line.replace("( ", "(").replace(" )", ")")
    if dataset in {"BGL"}:
        line = line.replace(".. ", "..")
    if dataset in {"HealthApp", "Android", "HPC", "BGL", "Hadoop", "Linux", "Thunderbird", "Windows", "Zookeeper"}:
        line = line.replace("= ", "=")
    if dataset == "Windows":
        line = line.replace("[ ", "[").replace(" ]", "]")
    return line


def build_group_lines(
    dataset: str,
    value_tokens: Sequence[List[str]],
    group: dict,
    level: int,
    max_level: int,
) -> tuple[List[str], dict]:
    valid_indices = [idx for idx in group["indices"] if 0 <= idx < len(value_tokens)]
    if not valid_indices:
        return [], {
            "group_size": 0,
            "variable_positions": 0,
            "output_size": 0,
            "min_pool_size": 0,
            "synthetic_values_added": 0,
        }

    positions = variable_positions(group["template"])
    base_tokens = list(value_tokens[valid_indices[0]])
    if not positions:
        return [detokenize(dataset, base_tokens) for _ in range(len(valid_indices))], {
            "group_size": len(valid_indices),
            "variable_positions": 0,
            "output_size": len(valid_indices),
            "min_pool_size": 0,
            "synthetic_values_added": 0,
        }

    pools: Dict[int, List[str]] = {}
    min_pool_size = None
    synthetic_added = 0
    for position in positions:
        observed = [
            value_tokens[idx][position]
            for idx in valid_indices
            if position < len(value_tokens[idx])
        ]
        pool = unique_in_order(observed)
        min_pool_size = len(pool) if min_pool_size is None else min(min_pool_size, len(pool))
        expanded = expand_pool(pool, level, dataset, position)
        synthetic_added += max(0, len(expanded) - len(pool))
        pools[position] = expanded

    output_size = max(len(valid_indices), max_level)
    prototypes = []
    for variant_idx in range(level):
        tokens = list(base_tokens)
        for position, pool in pools.items():
            if position >= len(tokens):
                continue
            tokens[position] = pool[variant_idx % len(pool)]
        prototypes.append(detokenize(dataset, tokens))

    lines = [prototypes[i % len(prototypes)] for i in range(output_size)]
    return lines, {
        "group_size": len(valid_indices),
        "variable_positions": len(positions),
        "output_size": output_size,
        "min_pool_size": min_pool_size or 0,
        "synthetic_values_added": synthetic_added,
    }


def build_dataset(dataset: str, level: int, max_level: int, human_root: Path, eval_root: Path, report_dir: Path) -> dict:
    source_file = choose_log_file(dataset)
    raw_lines = read_lines(source_file)
    groups = parse_original_templates(dataset, raw_lines)
    value_sentences = EC.get_united_sentences(raw_lines, dataset, [])
    value_tokens = [split_sentence(sentence) for sentence in value_sentences]

    output_lines: List[str] = []
    group_rows = []
    variable_groups = 0
    synthetic_values_added = 0

    for group_id, group in enumerate(groups):
        group_lines, stats = build_group_lines(dataset, value_tokens, group, level, max_level)
        output_lines.extend(group_lines)
        if stats["variable_positions"] > 0:
            variable_groups += 1
        synthetic_values_added += stats["synthetic_values_added"]
        group_rows.append(
            {
                "dataset": dataset,
                "level": level,
                "group_id": group_id,
                "source_group_size": stats["group_size"],
                "variable_positions": stats["variable_positions"],
                "output_size": stats["output_size"],
                "min_real_value_pool_size": stats["min_pool_size"],
                "synthetic_values_added": stats["synthetic_values_added"],
                "template": group["template"],
            }
        )

    human_file = human_root / dataset / f"{dataset}_variable_diversity_{level}.log"
    eval_file = eval_root / dataset / f"{dataset}_variable_diverse_{level}.log"
    written = write_lines(human_file, output_lines)
    write_lines(eval_file, output_lines)

    detail_dir = report_dir / "template_groups"
    detail_dir.mkdir(parents=True, exist_ok=True)
    with (detail_dir / f"{dataset}_variable_diversity_{level}_groups.csv").open("w", encoding="utf-8-sig", newline="") as f:
        fieldnames = [
            "dataset",
            "level",
            "group_id",
            "source_group_size",
            "variable_positions",
            "output_size",
            "min_real_value_pool_size",
            "synthetic_values_added",
            "template",
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(group_rows)

    return {
        "dataset": dataset,
        "level": level,
        "source_file": str(source_file),
        "source_lines": len(raw_lines),
        "template_groups": len(groups),
        "variable_groups": variable_groups,
        "output_lines": written,
        "synthetic_values_added": synthetic_values_added,
        "human_output_file": str(human_file),
        "eval_output_file": str(eval_file),
    }


def write_manifest(report_dir: Path, level: int, rows: Sequence[dict]) -> Path:
    report_dir.mkdir(parents=True, exist_ok=True)
    path = report_dir / f"variable_diversity_{level}_manifest.csv"
    fieldnames = [
        "dataset",
        "level",
        "source_file",
        "source_lines",
        "template_groups",
        "variable_groups",
        "output_lines",
        "synthetic_values_added",
        "human_output_file",
        "eval_output_file",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return path


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build variable-value diversity levels from original logs.")
    parser.add_argument("--levels", nargs="*", type=int, default=list(range(1, 9)))
    parser.add_argument("--datasets", nargs="*", default=DATASETS)
    parser.add_argument("--max-level", type=int, default=8)
    args = parser.parse_args(argv)

    datasets = [dataset for dataset in args.datasets if dataset in DATASETS]
    for level in args.levels:
        if level < 1:
            raise ValueError("levels must be >= 1")
        human_root = PROJECT_ROOT / f"dir_variable_diversity_{level}"
        eval_root = PROJECT_ROOT / "data" / f"dir_variable_diverse_{level}"
        report_dir = PROJECT_ROOT / f"variable_diversity_{level}_build_report"
        rows = []
        print(f"Building variable-value diversity level {level}")
        for dataset in datasets:
            row = build_dataset(dataset, level, args.max_level, human_root, eval_root, report_dir)
            rows.append(row)
            print(
                f"  {dataset}: source={row['source_lines']} output={row['output_lines']} "
                f"groups={row['template_groups']} synthetic_values={row['synthetic_values_added']}"
            )
        manifest = write_manifest(report_dir, level, rows)
        print(f"manifest={manifest}")
        print(f"human_output_root={human_root}")
        print(f"eval_output_root={eval_root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
