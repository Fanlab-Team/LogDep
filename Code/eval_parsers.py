#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Evaluate multiple log parsers on the same entropy-target diversity datasets.

This script keeps all parser evaluations aligned with the same standard:
  - input: data/gtld/diversity_0_1 ... 0_9
  - ground truth: corrected templates in data/raw_2k
  - x-axis: offline parser-independent Ground-truth LD
  - metrics: PA, PTA, RTA with the same template-token matching rule

It runs parsers from the teacher-provided logparser-main repository and also
collects the already generated Brain summary into one folder.
"""

from __future__ import annotations

import argparse
import contextlib
import csv
import hashlib
import importlib.util
import json
import os
import re
import shutil
import sys
import time
import urllib.error
import urllib.request
from collections import Counter
from pathlib import Path
from typing import Any, Callable, Sequence

import pandas as pd


SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
DEFAULT_LOGPARSER_ROOT = PROJECT_ROOT / "external_dependencies" / "logparser-main"
DEFAULT_LOGDEP_TOOL = PROJECT_ROOT / "external_dependencies" / "LogDep" / "Code_LogIterSplit" / "logTool.py"
DEFAULT_LILAC_ROOT = PROJECT_ROOT / "external_dependencies" / "LILAC-main"

sys.path.insert(0, str(SCRIPT_DIR))

from diversity_metrics import (
    BENCHMARK_SETTINGS,
    DATASETS,
    LOG_FORMATS,
    extract_content_lines,
    find_log_file,
    normalized_entropy,
    read_lines,
    value_tokenize,
    variable_positions,
)
from eval_brain import (
    LEVELS,
    calculate_pa,
    calculate_pta,
    calculate_rta,
    message_split,
    read_actual_diversity,
    read_standard_templates,
    resolve_standard_root,
)


LOCAL_PARSER_NAMES = ["Drain", "Spell", "Logram", "LogDep", "LogDepFull"]
PARSER_NAMES = LOCAL_PARSER_NAMES + ["LILAC"]


DRAIN_SETTINGS: dict[str, dict[str, Any]] = {
    "HDFS": {"regex": [r"blk_-?\d+", r"(\d+\.){3}\d+(:\d+)?"], "st": 0.5, "depth": 4},
    "Hadoop": {"regex": [r"(\d+\.){3}\d+"], "st": 0.5, "depth": 4},
    "Spark": {"regex": [r"(\d+\.){3}\d+", r"\b[KGTM]?B\b", r"([\w-]+\.){2,}[\w-]+"], "st": 0.5, "depth": 4},
    "Zookeeper": {"regex": [r"(/|)(\d+\.){3}\d+(:\d+)?"], "st": 0.5, "depth": 4},
    "BGL": {"regex": [r"core\.\d+"], "st": 0.5, "depth": 4},
    "HPC": {"regex": [r"=\d+"], "st": 0.5, "depth": 4},
    "Thunderbird": {"regex": [r"(\d+\.){3}\d+"], "st": 0.5, "depth": 4},
    "Windows": {"regex": [r"0x.*?\s"], "st": 0.7, "depth": 5},
    "Linux": {"regex": [r"(\d+\.){3}\d+", r"\d{2}:\d{2}:\d{2}"], "st": 0.39, "depth": 6},
    "Android": {
        "regex": [r"(/[\w-]+)+", r"([\w-]+\.){2,}[\w-]+", r"\b(\-?\+?\d+)\b|\b0[Xx][a-fA-F\d]+\b|\b[a-fA-F\d]{4,}\b"],
        "st": 0.2,
        "depth": 6,
    },
    "HealthApp": {"regex": [], "st": 0.2, "depth": 4},
    "Apache": {"regex": [r"(\d+\.){3}\d+"], "st": 0.5, "depth": 4},
    "OpenSSH": {"regex": [r"(\d+\.){3}\d+", r"([\w-]+\.){2,}[\w-]+"], "st": 0.6, "depth": 5},
    "OpenStack": {"regex": [r"((\d+\.){3}\d+,?)+", r"/.+?\s", r"\d+"], "st": 0.5, "depth": 5},
    "Mac": {"regex": [r"([\w-]+\.){2,}[\w-]+"], "st": 0.7, "depth": 6},
    "Proxifier": {
        "regex": [r"<\d+\ssec", r"([\w-]+\.)+[\w-]+(:\d+)?", r"\d{2}:\d{2}(:\d{2})*", r"[KGTM]B"],
        "st": 0.6,
        "depth": 3,
    },
}


SPELL_SETTINGS: dict[str, dict[str, Any]] = {
    "HDFS": {"regex": [r"blk_-?\d+", r"(\d+\.){3}\d+(:\d+)?"], "tau": 0.7},
    "Hadoop": {"regex": [r"(\d+\.){3}\d+"], "tau": 0.7},
    "Spark": {"regex": [r"(\d+\.){3}\d+", r"\b[KGTM]?B\b", r"([\w-]+\.){2,}[\w-]+"], "tau": 0.55},
    "Zookeeper": {"regex": [r"(/|)(\d+\.){3}\d+(:\d+)?"], "tau": 0.7},
    "BGL": {"regex": [r"core\.\d+"], "tau": 0.75},
    "HPC": {"regex": [r"=\d+"], "tau": 0.65},
    "Thunderbird": {"regex": [r"(\d+\.){3}\d+"], "tau": 0.5},
    "Windows": {"regex": [r"0x.*?\s"], "tau": 0.7},
    "Linux": {"regex": [r"(\d+\.){3}\d+", r"\d{2}:\d{2}:\d{2}"], "tau": 0.55},
    "Android": {
        "regex": [r"(/[\w-]+)+", r"([\w-]+\.){2,}[\w-]+", r"\b(\-?\+?\d+)\b|\b0[Xx][a-fA-F\d]+\b|\b[a-fA-F\d]{4,}\b"],
        "tau": 0.95,
    },
    "HealthApp": {"regex": [], "tau": 0.5},
    "Apache": {"regex": [r"(\d+\.){3}\d+"], "tau": 0.6},
    "OpenSSH": {"regex": [r"(\d+\.){3}\d+", r"([\w-]+\.){2,}[\w-]+"], "tau": 0.8},
    "OpenStack": {"regex": [r"((\d+\.){3}\d+,?)+", r"/.+?\s", r"\d+"], "tau": 0.9},
    "Mac": {"regex": [r"([\w-]+\.){2,}[\w-]+"], "tau": 0.6},
    "Proxifier": {
        "regex": [r"<\d+\ssec", r"([\w-]+\.)+[\w-]+(:\d+)?", r"\d{2}:\d{2}(:\d{2})*", r"[KGTM]B"],
        "tau": 0.85,
    },
}


LOGRAM_SETTINGS: dict[str, dict[str, Any]] = {
    "HDFS": {
        "regex": [r"blk_(|-)[0-9]+", r"(/|)([0-9]+\.){3}[0-9]+(:[0-9]+|)(:|)", r"(?<=[^A-Za-z0-9])(\-?\+?\d+)(?=[^A-Za-z0-9])|[0-9]+$"],
        "doubleThreshold": 15,
        "triThreshold": 10,
    },
    "Hadoop": {"regex": [r"(\d+\.){3}\d+"], "doubleThreshold": 9, "triThreshold": 10},
    "Spark": {"regex": [r"(\d+\.){3}\d+", r"\b[KGTM]?B\b", r"([\w-]+\.){2,}[\w-]+"], "doubleThreshold": 15, "triThreshold": 10},
    "Zookeeper": {"regex": [r"(/|)(\d+\.){3}\d+(:\d+)?"], "doubleThreshold": 15, "triThreshold": 10},
    "BGL": {"regex": [r"core\.\d+"], "doubleThreshold": 92, "triThreshold": 4},
    "HPC": {"regex": [r"=\d+"], "doubleThreshold": 15, "triThreshold": 10},
    "Thunderbird": {"regex": [r"(\d+\.){3}\d+"], "doubleThreshold": 35, "triThreshold": 32},
    "Windows": {"regex": [r"0x.*?\s"], "doubleThreshold": 15, "triThreshold": 10},
    "Linux": {"regex": [r"(\d+\.){3}\d+", r"\d{2}:\d{2}:\d{2}"], "doubleThreshold": 120, "triThreshold": 100},
    "Android": {
        "regex": [r"(/[\w-]+)+", r"([\w-]+\.){2,}[\w-]+", r"\b(\-?\+?\d+)\b|\b0[Xx][a-fA-F\d]+\b|\b[a-fA-F\d]{4,}\b"],
        "doubleThreshold": 15,
        "triThreshold": 10,
    },
    "HealthApp": {"regex": [], "doubleThreshold": 15, "triThreshold": 10},
    "Apache": {"regex": [r"(\d+\.){3}\d+"], "doubleThreshold": 15, "triThreshold": 10},
    "OpenSSH": {"regex": [r"(\d+\.){3}\d+", r"([\w-]+\.){2,}[\w-]+"], "doubleThreshold": 88, "triThreshold": 81},
    "OpenStack": {"regex": [r"((\d+\.){3}\d+,?)+", r"/.+?\s", r"\d+"], "doubleThreshold": 30, "triThreshold": 25},
    "Mac": {"regex": [r"([\w-]+\.){2,}[\w-]+"], "doubleThreshold": 2, "triThreshold": 2},
    "Proxifier": {
        "regex": [r"<\d+\ssec", r"([\w-]+\.)+[\w-]+(:\d+)?", r"\d{2}:\d{2}(:\d{2})*", r"[KGTM]B"],
        "doubleThreshold": 500,
        "triThreshold": 470,
    },
}


LOGDEP_VAR_THRESHOLDS = {
    "Proxifier": 0.4,
    "HDFS": 0.4,
    "Hadoop": 0.45,
    "Spark": 0.86,
    "Zookeeper": 0.3,
    "BGL": 0.66,
    "HPC": 0.4,
    "Thunderbird": 0.74,
    "Windows": 0.3,
    "Linux": 0.3,
    "Android": 0.07,
    "HealthApp": 0.25,
    "Apache": 0.4,
    "OpenSSH": 0.4,
    "OpenStack": 0.01,
    "Mac": 0.01,
}


LOGDEP_FULL_LOW_DIVERSITY_THRESHOLD = 0.35
LOGDEP_FULL_LD_ALPHA = 0.5
LOGDEP_FULL_WILDCARD = "<*>"
GTLD_INACTIVE_VALUE_RE = re.compile(r"\b([a-z])\1alpha\b")


def import_logparser_classes(logparser_root: Path) -> dict[str, Any]:
    if not logparser_root.exists():
        raise FileNotFoundError(f"logparser-main root not found: {logparser_root}")
    sys.path.insert(0, str(logparser_root))
    from logparser.Drain import LogParser as DrainParser
    from logparser.Logram import LogParser as LogramParser
    from logparser.Spell import LogParser as SpellParser

    return {"Drain": DrainParser, "Spell": SpellParser, "Logram": LogramParser}


def load_logdep_logtool(path: Path) -> Any:
    if not path.exists():
        raise FileNotFoundError(f"LogDep logTool.py not found: {path}")
    spec = importlib.util.spec_from_file_location("logdep_logtool", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load LogDep logTool.py from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def read_generated_from_structured(path: Path) -> list[tuple[str, int]]:
    df = pd.read_csv(path)
    if "EventTemplate" not in df.columns:
        raise ValueError(f"Missing EventTemplate column in {path}")
    counts = Counter(df["EventTemplate"].fillna("").astype(str).tolist())
    return [(template, count) for template, count in counts.items() if template]


def write_template_with_idx(generated: list[tuple[str, int]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        for template, count in generated:
            f.write(f"{template} {count}\n")


def run_parser_for_dataset(
    parser_name: str,
    parser_class: Any,
    dataset: str,
    data_dir: Path,
    output_dir: Path,
) -> dict[str, Any]:
    log_file = find_log_file(dataset, data_dir, data_dir.name, flat=False)
    log_format = LOG_FORMATS[dataset]
    dataset_output_dir = output_dir / dataset
    dataset_output_dir.mkdir(parents=True, exist_ok=True)

    if parser_name == "Drain":
        setting = DRAIN_SETTINGS[dataset]
        parser = parser_class(
            log_format=log_format,
            indir=str(log_file.parent),
            outdir=str(dataset_output_dir),
            rex=setting["regex"],
            depth=setting["depth"],
            st=setting["st"],
        )
    elif parser_name == "Spell":
        setting = SPELL_SETTINGS[dataset]
        parser = parser_class(
            log_format=log_format,
            indir=str(log_file.parent),
            outdir=str(dataset_output_dir),
            rex=setting["regex"],
            tau=setting["tau"],
        )
    elif parser_name == "Logram":
        setting = LOGRAM_SETTINGS[dataset]
        parser = parser_class(
            log_format=log_format,
            indir=str(log_file.parent),
            outdir=str(dataset_output_dir),
            rex=setting["regex"],
            doubleThreshold=setting["doubleThreshold"],
            triThreshold=setting["triThreshold"],
        )
    else:
        raise ValueError(f"Unsupported parser: {parser_name}")

    run_log = dataset_output_dir / f"{dataset}_{parser_name.lower()}_run.log"
    start = time.perf_counter()
    with run_log.open("w", encoding="utf-8") as log, contextlib.redirect_stdout(log), contextlib.redirect_stderr(log):
        parser.parse(log_file.name)
    elapsed = time.perf_counter() - start

    structured_file = dataset_output_dir / f"{log_file.name}_structured.csv"
    template_file = dataset_output_dir / f"{log_file.name}_templates.csv"
    generated = read_generated_from_structured(structured_file)
    template_with_idx = dataset_output_dir / f"{dataset}_{parser_name.lower()}_new_template_with_idx.csv"
    write_template_with_idx(generated, template_with_idx)

    return {
        "dataset": dataset,
        "source_file": str(log_file),
        "structured_file": str(structured_file),
        "template_file": str(template_file),
        "template_with_idx": str(template_with_idx),
        "run_log": str(run_log),
        "parse_seconds": elapsed,
        "generated_templates": len(generated),
        "generated_template_line_count": sum(count for _, count in generated),
        "generated": generated,
    }


def run_logdep_for_dataset(dataset: str, data_dir: Path, output_dir: Path, logtool: Any) -> dict[str, Any]:
    setting = BENCHMARK_SETTINGS[dataset]
    log_file = find_log_file(dataset, data_dir, data_dir.name, flat=False)
    raw_lines = read_lines(log_file)
    content_lines, parse_failures = extract_content_lines(dataset, raw_lines)

    start = time.perf_counter()
    content = [([idx + 1], item) for idx, item in enumerate(content_lines)]
    sentences = logtool.deduplicate(content)
    sentences = logtool.dataClean(sentences, setting["regex"], setting["delimiter"], dataset)
    sentences = logtool.deduplicate(sentences)

    templates: list[str] = []
    templates_with_idx: list[tuple[list[int], str]] = []
    iterations = 0
    while sentences:
        iterations += 1
        sentences, templates, templates_with_idx = logtool.torun(
            sentences,
            templates,
            templates_with_idx,
            LOGDEP_VAR_THRESHOLDS[dataset],
        )
        sentences = logtool.deduplicate(sentences)
    elapsed = time.perf_counter() - start

    templates_with_idx = [(sorted(indexes), template) for indexes, template in templates_with_idx]
    generated = [(template, len(indexes)) for indexes, template in templates_with_idx]

    dataset_output_dir = output_dir / dataset
    dataset_output_dir.mkdir(parents=True, exist_ok=True)
    template_with_idx = dataset_output_dir / f"{dataset}_logdep_new_template_with_idx.csv"
    write_template_with_idx(generated, template_with_idx)

    iteration_file = dataset_output_dir / f"{dataset}_logdep_iterations.csv"
    with iteration_file.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["dataset", "iterations", "input_lines", "content_parse_failures"])
        writer.writerow([dataset, iterations, len(content_lines), parse_failures])

    return {
        "dataset": dataset,
        "source_file": str(log_file),
        "structured_file": "",
        "template_file": "",
        "template_with_idx": str(template_with_idx),
        "run_log": str(iteration_file),
        "parse_seconds": elapsed,
        "generated_templates": len(generated),
        "generated_template_line_count": sum(count for _, count in generated),
        "generated": generated,
    }


def normalize_logdep_full_content(content: str) -> str:
    """Normalize obvious variable forms before LogDep's frequency parser.

    The original LogDep core only masks digit-heavy/path-like variables.  The
    GTLD builder also fills inactive template slots with stable alphabetic
    placeholders such as ``aaalpha`` and ``bbalpha``; those represent synthetic
    variable values and should be treated like the active generated values.
    """
    text = str(content)
    wildcard = LOGDEP_FULL_WILDCARD
    text = GTLD_INACTIVE_VALUE_RE.sub(wildcard, text)
    text = re.sub(r"\bblk_-?\d+\b", wildcard, text)
    text = re.sub(r"\b(?:\d{1,3}\.){3}\d{1,3}(?::\d+)?\b", wildcard, text)
    text = re.sub(r"\b[\w-]+(?:\.[\w-]+){2,}(?::\d+)?\b", wildcard, text)
    text = re.sub(r"\b[\w-]+\.\d+(?:\.\d+)*\b", wildcard, text)
    text = re.sub(r"(?<!\w)0x[0-9a-fA-F]+\b", wildcard, text)
    text = re.sub(r"(/[\w.\-]+)+", wildcard, text)
    text = re.sub(r"(?<![A-Za-z])\b-?\d+(?:\.\d+)?\b", wildcard, text)
    return text


def logdep_group_key(dataset: str, content: str) -> str:
    normalized = normalize_logdep_full_content(content)
    tokens = value_tokenize([normalized], dataset)[0]
    return " ".join(tokens)


def group_diversity_from_contents(
    dataset: str,
    normalized_template: str,
    contents: Sequence[str],
) -> tuple[float, float, float]:
    """Apply the shared entropy formula to one LogDep-estimated group.

    Returns D(G), |G|^alpha * D(G), and |G|^alpha. Groups with no detected
    variable positions still contribute zero-valued weight to the global LD,
    matching the parser-independent Ground-truth LD definition.
    """
    group_size = len(contents)
    positions = variable_positions(normalized_template)
    group_weight = group_size**LOGDEP_FULL_LD_ALPHA if group_size > 0 else 0.0
    if group_size <= 1 or not positions:
        return 0.0, 0.0, group_weight

    tokenized = value_tokenize(contents, dataset)
    scores = []
    for position in positions:
        values = [tokens[position] for tokens in tokenized if position < len(tokens)]
        if values:
            scores.append(normalized_entropy(values, group_size))

    if not scores:
        return 0.0, 0.0, group_weight
    diversity = sum(scores) / len(scores)
    return diversity, diversity * group_weight, group_weight


def logdep_full_diversity_summary(
    dataset: str,
    content_lines: Sequence[str],
) -> tuple[float, int, int]:
    grouped: dict[str, list[str]] = {}
    for content in content_lines:
        key = logdep_group_key(dataset, content)
        grouped.setdefault(key, []).append(content)

    weighted_sum = 0.0
    weight_sum = 0.0
    low_diversity_groups = 0
    for key, contents in grouped.items():
        diversity, group_weighted_sum, group_weight_sum = group_diversity_from_contents(
            dataset,
            key,
            contents,
        )
        if diversity < LOGDEP_FULL_LOW_DIVERSITY_THRESHOLD:
            low_diversity_groups += 1
        weighted_sum += group_weighted_sum
        weight_sum += group_weight_sum
    global_ld = weighted_sum / weight_sum if weight_sum else 0.0
    return global_ld, low_diversity_groups, len(grouped)


def read_ground_truth_dataset_diversity(
    dataset: str,
    level: str,
    ground_truth_ld_root: str | Path,
) -> float:
    root = Path(ground_truth_ld_root)
    if not root.is_absolute():
        root = PROJECT_ROOT / root
    path = root / f"level_{level}.csv"
    if not path.is_file():
        raise FileNotFoundError(
            f"Missing Ground-truth LD file: {path}. "
            "Run Code/ground_truth_diversity.py first."
        )
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        for row in csv.DictReader(file):
            if row.get("dataset") == dataset:
                return float(row["ground_truth_ld"])
    raise ValueError(f"Missing Ground-truth LD for {dataset} at {level}: {path}")


def read_secret_text(path: Path) -> str:
    value = path.read_text(encoding="utf-8", errors="ignore").strip()
    for line in value.splitlines():
        line = line.strip()
        if line.startswith("sk-"):
            return line
        if "=" in line:
            maybe_key = line.split("=", 1)[1].strip().strip("\"'")
            if maybe_key.startswith("sk-"):
                return maybe_key
    return value


def resolve_deepseek_api_key(args: argparse.Namespace) -> str:
    if args.logdepfull_api_key_env:
        key = os.environ.get(args.logdepfull_api_key_env, "").strip()
        if key:
            return key
    if args.logdepfull_api_key_file:
        key_file = Path(args.logdepfull_api_key_file)
        if key_file.exists():
            key = read_secret_text(key_file)
            if key:
                return key
    raise RuntimeError(
        "LogDepFull API augmentation is enabled, but no API key was found. "
        "Set the configured environment variable or pass --logdepfull-api-key-file."
    )


def parse_deepseek_variant_text(text: str) -> list[str]:
    variants: list[str] = []
    for raw_line in str(text).splitlines():
        line = raw_line.strip()
        if not line:
            continue
        line = re.sub(r"^\s*(?:[-*]|\d+[\).:-])\s*", "", line).strip()
        if not line or line.startswith("```"):
            continue
        variants.append(line.strip("\"'"))
    return variants


def request_deepseek_variants(
    seed_content: str,
    api_key: str,
    model: str,
    base_url: str,
    count: int,
    temperature: float,
    max_tokens: int,
    thinking_mode: str,
    timeout: int,
) -> list[str]:
    prompt = (
        "You are augmenting log data for log parsing. Generate "
        f"{count} variants of the following log message content. "
        "Keep the same event semantics and constant words. Change only likely "
        "parameters such as ids, paths, IPs, ports, host names, block ids, "
        "numbers, sizes, sessions, or status values. Return one variant per "
        "line and no explanations.\n\n"
        f"LOG CONTENT:\n{seed_content}"
    )
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "You generate concise log content variants for data augmentation."},
            {"role": "user", "content": prompt},
        ],
        "temperature": temperature,
        "thinking": {"type": thinking_mode},
    }
    if max_tokens > 0:
        payload["max_tokens"] = max_tokens
    request = urllib.request.Request(
        base_url.rstrip("/") + "/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.URLError as exc:
        raise RuntimeError(f"DeepSeek augmentation request failed: {exc}") from exc

    content = data["choices"][0]["message"]["content"]
    variants = parse_deepseek_variant_text(content)
    return variants[:count]


def cached_deepseek_variants(
    seed_content: str,
    cache_dir: Path,
    args: argparse.Namespace,
) -> list[str]:
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_key = hashlib.sha256(
        "\n".join(
            [
                args.logdepfull_api_base_url,
                args.logdepfull_api_model,
                str(args.logdepfull_api_variants),
                str(args.logdepfull_api_temperature),
                str(args.logdepfull_api_max_tokens),
                args.logdepfull_api_thinking_mode,
                seed_content,
            ]
        ).encode("utf-8")
    ).hexdigest()
    cache_file = cache_dir / f"{cache_key}.json"
    if cache_file.exists():
        with cache_file.open("r", encoding="utf-8") as f:
            return list(json.load(f).get("variants", []))

    if args.logdepfull_api_cache_only:
        return []
    api_key = resolve_deepseek_api_key(args)
    variants = request_deepseek_variants(
        seed_content=seed_content,
        api_key=api_key,
        model=args.logdepfull_api_model,
        base_url=args.logdepfull_api_base_url,
        count=args.logdepfull_api_variants,
        temperature=args.logdepfull_api_temperature,
        max_tokens=args.logdepfull_api_max_tokens,
        thinking_mode=args.logdepfull_api_thinking_mode,
        timeout=args.logdepfull_api_timeout,
    )
    with cache_file.open("w", encoding="utf-8") as f:
        json.dump(
            {
                "seed": seed_content,
                "variants": variants,
                "model": args.logdepfull_api_model,
                "temperature": args.logdepfull_api_temperature,
                "max_tokens": args.logdepfull_api_max_tokens if args.logdepfull_api_max_tokens > 0 else None,
                "thinking_mode": args.logdepfull_api_thinking_mode,
            },
            f,
            ensure_ascii=False,
            indent=2,
        )
    return variants


def augment_logdep_full_contents(
    dataset: str,
    content_lines: Sequence[str],
    output_dir: Path,
    args: argparse.Namespace,
    enable_api: bool,
) -> tuple[list[tuple[int, str]], int]:
    real_items = [(idx + 1, content) for idx, content in enumerate(content_lines)]
    if not enable_api:
        return real_items, 0

    grouped: dict[str, list[tuple[int, str]]] = {}
    for idx, content in real_items:
        key = logdep_group_key(dataset, content)
        grouped.setdefault(key, []).append((idx, content))

    candidates: list[tuple[float, str, list[tuple[int, str]]]] = []
    for key, items in grouped.items():
        diversity, _weighted_sum, _weight_sum = group_diversity_from_contents(
            dataset,
            key,
            [content for _idx, content in items],
        )
        if diversity < LOGDEP_FULL_LOW_DIVERSITY_THRESHOLD:
            candidates.append((diversity, key, items))
    candidates.sort(key=lambda item: (item[0], len(item[2])))

    augmented_items = list(real_items)
    generated_count = 0
    cache_dir = output_dir / "_deepseek_cache" / dataset
    max_groups = max(args.logdepfull_api_max_groups, 0)
    for group_index, (_diversity, _key, items) in enumerate(candidates[:max_groups]):
        seed = items[0][1]
        variants = cached_deepseek_variants(seed, cache_dir, args)
        for variant_index, variant in enumerate(variants):
            if not variant.strip():
                continue
            synthetic_id = -((group_index + 1) * 100000 + variant_index + 1)
            augmented_items.append((synthetic_id, variant))
            generated_count += 1
    return augmented_items, generated_count


def build_logdep_full_template(contents: Sequence[str]) -> str:
    tokenized = [message_split(normalize_logdep_full_content(content)) for content in contents]
    if not tokenized:
        return ""

    wildcard = LOGDEP_FULL_WILDCARD
    max_len = max(len(tokens) for tokens in tokenized)
    template_tokens: list[str] = []
    for idx in range(max_len):
        values = [tokens[idx] if idx < len(tokens) else None for tokens in tokenized]
        if any(value is None for value in values):
            template_tokens.append(wildcard)
            continue
        unique_values = set(values)
        if len(unique_values) == 1 and values[0] not in {wildcard, "*"}:
            template_tokens.append(str(values[0]))
        else:
            template_tokens.append(wildcard)

    collapsed: list[str] = []
    for token in template_tokens:
        if token == wildcard and collapsed and collapsed[-1] == wildcard:
            continue
        collapsed.append(token)
    return " ".join(collapsed)


def run_logdep_full_for_dataset(
    dataset: str,
    level: str,
    data_dir: Path,
    output_dir: Path,
    logtool: Any,
    args: argparse.Namespace,
) -> dict[str, Any]:
    setting = BENCHMARK_SETTINGS[dataset]
    log_file = find_log_file(dataset, data_dir, data_dir.name, flat=False)
    raw_lines = read_lines(log_file)
    content_lines, parse_failures = extract_content_lines(dataset, raw_lines)
    start = time.perf_counter()
    estimated_ld, low_diversity_groups, coarse_groups = logdep_full_diversity_summary(
        dataset,
        content_lines,
    )
    global_ld = (
        read_ground_truth_dataset_diversity(dataset, level, args.ground_truth_ld_root)
        if args.logdepfull_ld_source in {"oracle", "benchmark"}
        else estimated_ld
    )
    enable_api = args.allow_logdepfull_api and global_ld <= args.logdepfull_api_trigger_ld
    augmented_items, api_generated_lines = augment_logdep_full_contents(
        dataset,
        content_lines,
        output_dir,
        args,
        enable_api=enable_api,
    )

    content = [
        ([idx], normalize_logdep_full_content(item))
        for idx, item in augmented_items
    ]
    sentences = logtool.deduplicate(content)
    sentences = logtool.dataClean(sentences, setting["regex"], setting["delimiter"], dataset)
    sentences = logtool.deduplicate(sentences)

    templates: list[str] = []
    templates_with_idx: list[tuple[list[int], str]] = []
    iterations = 0
    while sentences:
        iterations += 1
        sentences, templates, templates_with_idx = logtool.torun(
            sentences,
            templates,
            templates_with_idx,
            LOGDEP_VAR_THRESHOLDS[dataset],
        )
        sentences = logtool.deduplicate(sentences)
    elapsed = time.perf_counter() - start

    generated_counter: Counter[str] = Counter()
    for indexes, _template in templates_with_idx:
        real_indexes = sorted(index for index in indexes if index > 0)
        if not real_indexes:
            continue
        grouped_contents = [content_lines[index - 1] for index in real_indexes]
        template = build_logdep_full_template(grouped_contents)
        if template:
            generated_counter[template] += len(real_indexes)

    generated = list(generated_counter.items())

    dataset_output_dir = output_dir / dataset
    dataset_output_dir.mkdir(parents=True, exist_ok=True)
    template_with_idx = dataset_output_dir / f"{dataset}_logdepfull_new_template_with_idx.csv"
    write_template_with_idx(generated, template_with_idx)

    iteration_file = dataset_output_dir / f"{dataset}_logdepfull_iterations.csv"
    with iteration_file.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "dataset",
                "iterations",
                "input_lines",
                "content_parse_failures",
                "global_ld",
                "estimated_ld",
                "ld_source",
                "low_diversity_groups",
                "coarse_groups",
                "api_generated_lines",
                "api_enabled",
                "api_trigger_ld",
            ]
        )
        writer.writerow(
            [
                dataset,
                iterations,
                len(content_lines),
                parse_failures,
                f"{global_ld:.6f}",
                f"{estimated_ld:.6f}",
                args.logdepfull_ld_source,
                low_diversity_groups,
                coarse_groups,
                api_generated_lines,
                int(enable_api),
                args.logdepfull_api_trigger_ld,
            ]
        )

    return {
        "dataset": dataset,
        "source_file": str(log_file),
        "structured_file": "",
        "template_file": "",
        "template_with_idx": str(template_with_idx),
        "run_log": str(iteration_file),
        "parse_seconds": elapsed,
        "generated_templates": len(generated),
        "generated_template_line_count": sum(count for _, count in generated),
        "generated": generated,
    }


def run_lilac_for_dataset(dataset: str, level: str, data_dir: Path, output_dir: Path, args: argparse.Namespace) -> dict[str, Any]:
    lilac_root = Path(args.lilac_root)
    if not lilac_root.exists():
        raise FileNotFoundError(f"LILAC root not found: {lilac_root}")

    log_file = find_log_file(dataset, data_dir, data_dir.name, flat=False)
    log_format = LOG_FORMATS[dataset]
    data_type = f"{args.lilac_data_type_prefix}_{level}"
    lilac_result_dir = lilac_root / "result" / f"result_LILAC_{data_type}_{args.lilac_shot}_{args.lilac_example_size}_{args.lilac_model}"
    source_structured = lilac_result_dir / f"{dataset}_{data_type}.log_structured.csv"
    source_templates = lilac_result_dir / f"{dataset}_{data_type}.log_templates.csv"

    dataset_output_dir = output_dir / dataset
    dataset_output_dir.mkdir(parents=True, exist_ok=True)
    run_log = dataset_output_dir / f"{dataset}_lilac_run.log"

    elapsed = 0.0
    if not source_structured.exists():
        if not args.allow_lilac_api:
            raise RuntimeError(
                "LILAC result is missing and LILAC requires an LLM API call. "
                f"Missing: {source_structured}. Re-run with --allow-lilac-api after confirming the API key and cost."
            )

        eval_cwd = lilac_root / "benchmark" / "evaluation"
        if not eval_cwd.exists():
            raise FileNotFoundError(f"LILAC evaluation directory not found: {eval_cwd}")

        start = time.perf_counter()
        old_cwd = Path.cwd()
        try:
            os.chdir(eval_cwd)
            sys.path.insert(0, str(lilac_root))
            with run_log.open("w", encoding="utf-8") as log:
                # LILAC's gpt_query.py prints key material at import time; suppress
                # that import chatter so no credentials end up in result logs.
                with open(os.devnull, "w", encoding="utf-8") as devnull:
                    with contextlib.redirect_stdout(devnull), contextlib.redirect_stderr(devnull):
                        from benchmark.logparser.LILAC import LogParser as LilacParser

                parser = LilacParser(
                    log_format=log_format,
                    indir=str(log_file.parent),
                    outdir=str(dataset_output_dir),
                    rex=[],
                    data_type=data_type,
                    shot=args.lilac_shot,
                    example_size=args.lilac_example_size,
                    model=args.lilac_model,
                )
                with contextlib.redirect_stdout(log), contextlib.redirect_stderr(log):
                    parser.parse(log_file.name)
        finally:
            os.chdir(old_cwd)
        elapsed = time.perf_counter() - start

    if not source_structured.exists():
        raise FileNotFoundError(f"LILAC did not produce structured output: {source_structured}")

    structured_file = dataset_output_dir / source_structured.name
    shutil.copy2(source_structured, structured_file)
    template_file = ""
    if source_templates.exists():
        copied_templates = dataset_output_dir / source_templates.name
        shutil.copy2(source_templates, copied_templates)
        template_file = str(copied_templates)

    generated = read_generated_from_structured(structured_file)
    template_with_idx = dataset_output_dir / f"{dataset}_lilac_new_template_with_idx.csv"
    write_template_with_idx(generated, template_with_idx)

    return {
        "dataset": dataset,
        "source_file": str(log_file),
        "structured_file": str(structured_file),
        "template_file": template_file,
        "template_with_idx": str(template_with_idx),
        "run_log": str(run_log),
        "parse_seconds": elapsed,
        "generated_templates": len(generated),
        "generated_template_line_count": sum(count for _, count in generated),
        "generated": generated,
    }


def evaluate_parser_level(
    parser_name: str,
    parser_class: Any,
    level: str,
    args: argparse.Namespace,
    standard_root: Path,
    logdep_logtool: Any | None = None,
) -> dict[str, Any]:
    data_dir = PROJECT_ROOT / args.data_root / f"{args.data_prefix}_{level}"
    output_dir = PROJECT_ROOT / args.output_root / parser_name / f"diversity_{level}"
    output_dir.mkdir(parents=True, exist_ok=True)

    rows: list[dict[str, Any]] = []
    metrics_sum = {"PA": 0.0, "PTA": 0.0, "RTA": 0.0}
    success_count = 0
    total_parse_seconds = 0.0

    for dataset in DATASETS:
        print(f"[{parser_name} {level}] parsing {dataset} ...")
        try:
            if parser_name == "LogDep":
                if logdep_logtool is None:
                    raise ValueError("LogDep logtool module is not loaded.")
                parsed = run_logdep_for_dataset(dataset, data_dir, output_dir, logdep_logtool)
            elif parser_name == "LogDepFull":
                if logdep_logtool is None:
                    raise ValueError("LogDep logtool module is not loaded.")
                parsed = run_logdep_full_for_dataset(
                    dataset,
                    level,
                    data_dir,
                    output_dir,
                    logdep_logtool,
                    args,
                )
            elif parser_name == "LILAC":
                parsed = run_lilac_for_dataset(dataset, level, data_dir, output_dir, args)
            else:
                parsed = run_parser_for_dataset(parser_name, parser_class, dataset, data_dir, output_dir)
            standard = read_standard_templates(dataset, standard_root)
            generated = parsed.pop("generated")
            pa = calculate_pa(generated, standard)
            pta = calculate_pta(generated, standard)
            rta = calculate_rta(generated, standard)
            metrics_sum["PA"] += pa
            metrics_sum["PTA"] += pta
            metrics_sum["RTA"] += rta
            success_count += 1
            total_parse_seconds += float(parsed["parse_seconds"])
            rows.append(
                {
                    "dataset": dataset,
                    "PA": f"{pa:.4f}",
                    "PTA": f"{pta:.4f}",
                    "RTA": f"{rta:.4f}",
                    "parse_seconds": f"{parsed['parse_seconds']:.4f}",
                    "generated_templates": parsed["generated_templates"],
                    "generated_template_line_count": parsed["generated_template_line_count"],
                    "source_file": parsed["source_file"],
                    "structured_file": parsed["structured_file"],
                    "template_file": parsed["template_file"],
                    "template_with_idx": parsed["template_with_idx"],
                    "run_log": parsed["run_log"],
                    "error": "",
                }
            )
        except Exception as exc:
            rows.append(
                {
                    "dataset": dataset,
                    "PA": "ERROR",
                    "PTA": "ERROR",
                    "RTA": "ERROR",
                    "parse_seconds": "",
                    "generated_templates": "",
                    "generated_template_line_count": "",
                    "source_file": "",
                    "structured_file": "",
                    "template_file": "",
                    "template_with_idx": "",
                    "run_log": "",
                    "error": repr(exc),
                }
            )

    avg = {
        "dataset": "AVERAGE",
        "PA": f"{metrics_sum['PA'] / success_count:.4f}" if success_count else "ERROR",
        "PTA": f"{metrics_sum['PTA'] / success_count:.4f}" if success_count else "ERROR",
        "RTA": f"{metrics_sum['RTA'] / success_count:.4f}" if success_count else "ERROR",
        "parse_seconds": f"{total_parse_seconds:.4f}",
        "generated_templates": "",
        "generated_template_line_count": "",
        "source_file": "",
        "structured_file": "",
        "template_file": "",
        "template_with_idx": "",
        "run_log": "",
        "error": "",
    }
    rows.append(avg)

    eval_csv = output_dir / "metrics.csv"
    with eval_csv.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    actual_ground_truth_ld = read_actual_diversity(level, args.calibration_file)
    return {
        "parser": parser_name,
        "target_diversity": "0." + level.split("_")[1],
        "actual_ground_truth_ld": actual_ground_truth_ld,
        # Deprecated alias retained for compatibility with existing result tools.
        "actual_content_weighted_entropy_diversity": actual_ground_truth_ld,
        "PA": avg["PA"],
        "PTA": avg["PTA"],
        "RTA": avg["RTA"],
        "success_count": success_count,
        "parse_seconds": avg["parse_seconds"],
        "eval_csv": str(eval_csv),
        "result_dir": str(output_dir),
    }


def normalize_existing_summary(parser_name: str, source: Path, output_root: Path) -> list[dict[str, Any]]:
    if not source.exists():
        return []
    parser_dir = output_root / parser_name
    parser_dir.mkdir(parents=True, exist_ok=True)
    copied = parser_dir / "summary.csv"

    rows = []
    with source.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(
                {
                    "parser": parser_name,
                    "target_diversity": row.get("target_diversity", ""),
                    "actual_ground_truth_ld": row.get(
                        "actual_ground_truth_ld",
                        row.get("actual_content_weighted_entropy_diversity", ""),
                    ),
                    "actual_content_weighted_entropy_diversity": row.get(
                        "actual_content_weighted_entropy_diversity",
                        row.get("actual_ground_truth_ld", ""),
                    ),
                    "PA": row.get("PA", ""),
                    "PTA": row.get("PTA", ""),
                    "RTA": row.get("RTA", ""),
                    "success_count": row.get("success_count", "16"),
                    "parse_seconds": "",
                    "eval_csv": row.get("eval_csv", ""),
                    "result_dir": row.get("result_dir", ""),
                }
            )
    write_summary(rows, copied)
    return rows


def read_parser_summary(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def add_average_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Append one PA/PTA/RTA average row after each parser's level rows."""
    grouped: dict[str, list[dict[str, Any]]] = {}
    parser_order: list[str] = []
    for row in rows:
        parser_name = row.get("parser", "")
        if not parser_name or str(row.get("target_diversity", "")).upper() == "AVERAGE":
            continue
        if parser_name not in grouped:
            grouped[parser_name] = []
            parser_order.append(parser_name)
        grouped[parser_name].append(row)

    output: list[dict[str, Any]] = []
    for parser_name in parser_order:
        parser_rows = grouped[parser_name]
        parser_rows.sort(key=lambda row: float(row.get("target_diversity", "999")))
        output.extend(parser_rows)

        averages: dict[str, str] = {}
        for metric in ("PA", "PTA", "RTA"):
            values = []
            for row in parser_rows:
                try:
                    values.append(float(row.get(metric, "")))
                except (TypeError, ValueError):
                    pass
            averages[metric] = f"{sum(values) / len(values):.4f}" if values else "ERROR"

        output.append(
            {
                "parser": parser_name,
                "target_diversity": "AVERAGE",
                "actual_ground_truth_ld": "",
                "actual_content_weighted_entropy_diversity": "",
                **averages,
                "success_count": "",
                "parse_seconds": "",
                "eval_csv": "",
                "result_dir": "",
            }
        )
    return output


def write_summary(rows: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "parser",
        "target_diversity",
        "actual_ground_truth_ld",
        "actual_content_weighted_entropy_diversity",
        "PA",
        "PTA",
        "RTA",
        "success_count",
        "parse_seconds",
        "eval_csv",
        "result_dir",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(add_average_rows(rows))


def write_per_parser(rows: list[dict[str, Any]], output_root: Path) -> None:
    metrics_dir = output_root / "per_parser"
    metrics_dir.mkdir(parents=True, exist_ok=True)
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in add_average_rows(rows):
        parser_name = row.get("parser", "")
        if parser_name:
            grouped.setdefault(parser_name, []).append(row)

    fieldnames = [
        "target_diversity",
        "actual_ground_truth_ld",
        "actual_content_weighted_entropy_diversity",
        "PA",
        "PTA",
        "RTA",
    ]
    for parser_name, parser_rows in grouped.items():
        output_file = metrics_dir / f"{parser_name.lower()}.csv"
        with output_file.open("w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for row in parser_rows:
                writer.writerow({field: row.get(field, "") for field in fieldnames})


def merge_parser_summary_rows(existing_rows: list[dict[str, Any]], new_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    for row in existing_rows + new_rows:
        key = row.get("target_diversity", "")
        if key and str(key).upper() != "AVERAGE":
            merged[key] = row

    def sort_key(row: dict[str, Any]) -> float:
        try:
            return float(row.get("target_diversity", "999"))
        except ValueError:
            return 999.0

    return sorted(merged.values(), key=sort_key)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate multiple parsers on 0.1-0.9 diversity datasets.")
    parser.add_argument("--logparser-root", default=str(DEFAULT_LOGPARSER_ROOT))
    parser.add_argument("--logdep-tool", default=str(DEFAULT_LOGDEP_TOOL))
    parser.add_argument("--lilac-root", default=str(DEFAULT_LILAC_ROOT))
    parser.add_argument("--lilac-model", default="deepseek-chat")
    parser.add_argument("--lilac-shot", type=int, default=0)
    parser.add_argument("--lilac-example-size", type=int, default=0)
    parser.add_argument(
        "--lilac-data-type-prefix",
        default="gtld",
        help="LILAC result namespace. Keep GTLD runs separate from legacy entropy-target caches.",
    )
    parser.add_argument("--allow-logdepfull-api", action="store_true")
    parser.add_argument(
        "--logdepfull-ld-source",
        choices=["estimated", "oracle", "benchmark"],
        default="estimated",
        help=(
            "Use LogDep's runtime estimate for the main fair experiment. "
            "The oracle/benchmark options expose Ground-truth LD and are only "
            "valid as an ablation upper bound."
        ),
    )
    parser.add_argument(
        "--ground-truth-ld-root",
        default="results/ground_truth_diversity",
        help="Per-dataset Ground-truth LD reports used only by oracle ablations.",
    )
    parser.add_argument("--logdepfull-api-base-url", default="https://api.deepseek.com")
    parser.add_argument("--logdepfull-api-model", default="deepseek-chat")
    parser.add_argument("--logdepfull-api-temperature", type=float, default=1.0)
    parser.add_argument("--logdepfull-api-max-tokens", type=int, default=0)
    parser.add_argument("--logdepfull-api-thinking-mode", choices=["disabled", "enabled"], default="disabled")
    parser.add_argument("--logdepfull-api-key-env", default="DEEPSEEK_API_KEY")
    parser.add_argument("--logdepfull-api-key-file", default="")
    parser.add_argument("--logdepfull-api-trigger-ld", type=float, default=0.35)
    parser.add_argument("--logdepfull-api-max-groups", type=int, default=8)
    parser.add_argument("--logdepfull-api-variants", type=int, default=4)
    parser.add_argument("--logdepfull-api-timeout", type=int, default=60)
    parser.add_argument(
        "--logdepfull-api-cache-only",
        action="store_true",
        help="Reuse cached LogDepFull LLM variants and skip uncached API requests.",
    )
    parser.add_argument(
        "--allow-lilac-api",
        action="store_true",
        help="Allow LILAC to call the configured LLM API when cached results are missing.",
    )
    parser.add_argument("--standard-root", default=None)
    parser.add_argument("--data-root", default="data/gtld")
    parser.add_argument("--data-prefix", default="diversity")
    parser.add_argument("--output-root", default="results/parser_runs/gtld/parser_eval")
    parser.add_argument(
        "--calibration-file",
        default="results/ground_truth_diversity/calibration.csv",
        help="Common Ground-truth LD calibration used only for reporting the x-axis.",
    )
    parser.add_argument(
        "--brain-summary",
        default="results/parser_runs/gtld/brain_eval/summary.csv",
        help="Brain summary to collect into the unified result table.",
    )
    parser.add_argument("--levels", nargs="*", default=LEVELS)
    parser.add_argument("--parsers", nargs="*", default=LOCAL_PARSER_NAMES, choices=PARSER_NAMES)
    parser.add_argument("--skip-existing", action="store_true", help="Do not collect the existing Brain summary.")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    output_root = PROJECT_ROOT / args.output_root
    standard_root = resolve_standard_root(args.standard_root)
    needs_logparser_main = any(name in {"Drain", "Spell", "Logram"} for name in args.parsers)
    parser_classes = import_logparser_classes(Path(args.logparser_root)) if needs_logparser_main else {}
    logdep_logtool = (
        load_logdep_logtool(Path(args.logdep_tool))
        if any(name in {"LogDep", "LogDepFull"} for name in args.parsers)
        else None
    )

    for parser_name in args.parsers:
        parser_rows = []
        for level in args.levels:
            parser_rows.append(
                evaluate_parser_level(
                    parser_name,
                    parser_classes.get(parser_name),
                    level,
                    args,
                    standard_root,
                    logdep_logtool=logdep_logtool,
                )
            )
        parser_summary = output_root / parser_name / "summary.csv"
        existing_rows = read_parser_summary(parser_summary)
        write_summary(merge_parser_summary_rows(existing_rows, parser_rows), parser_summary)

    all_rows: list[dict[str, Any]] = []
    if not args.skip_existing:
        brain_summary = Path(args.brain_summary)
        if not brain_summary.is_absolute():
            brain_summary = PROJECT_ROOT / brain_summary
        all_rows.extend(
            normalize_existing_summary(
                "Brain",
                brain_summary,
                output_root,
            )
        )
    for parser_name in PARSER_NAMES:
        parser_summary = output_root / parser_name / "summary.csv"
        parser_rows = read_parser_summary(parser_summary)
        if parser_rows:
            write_summary(parser_rows, parser_summary)
            all_rows.extend(read_parser_summary(parser_summary))

    write_summary(all_rows, output_root / "summary.csv")
    write_per_parser(all_rows, output_root)
    print(f"Saved unified results to: {output_root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
