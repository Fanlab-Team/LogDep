#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Build an aggressive before-template augmentation set for
dir_lowdiv_singleton_before_dedup.

The script keeps the original before files untouched and writes:

  dir_lowdiv_singleton_after_doubao_metric/<Dataset>/<Dataset>_lowdiv_singleton_after_doubao_metric.log

Generation order for every before line:
  1. existing cached DouBao/GPT rows with the exact same origin line
  2. existing cached/generated rows whose normalized skeleton matches the before line
  3. optional fresh DouBao calls when --use-doubao is set and env vars exist
  4. deterministic structure-preserving variable perturbations as a fallback

Fresh API credentials are read only from environment variables:
  DOUBAO_API_KEY or ARK_API_KEY
  DOUBAO_MODEL
"""

from __future__ import annotations

import argparse
import csv
import os
import random
import re
import sys
import time
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple


SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(SCRIPT_DIR))

import DouBao


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

INPUT_DIR = PROJECT_ROOT / "dir_lowdiv_singleton_before_dedup"
OUTPUT_DIR = PROJECT_ROOT / "dir_lowdiv_singleton_after_doubao_metric"
REPORT_DIR = PROJECT_ROOT / "doubao_metric_augmentation_report"


def read_lines(path: Path) -> List[str]:
    for encoding in ("utf-8", "utf-8-sig", "gbk", "latin-1"):
        try:
            with path.open("r", encoding=encoding) as f:
                return [line.rstrip("\r\n") for line in f if line.strip()]
        except UnicodeDecodeError:
            continue
    raise UnicodeDecodeError("unknown", b"", 0, 1, f"Cannot decode {path}")


def write_lines(path: Path, lines: Iterable[str]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with path.open("w", encoding="utf-8", newline="\n") as f:
        for line in lines:
            line = line.rstrip("\r\n")
            if not line.strip():
                continue
            f.write(line + "\n")
            count += 1
    return count


def clean_candidate(line: str) -> str:
    line = line.strip().strip("\ufeff")
    line = re.sub(r"^\s*\d+[\.\)、)]\s*", "", line)
    line = line.strip("` ")
    return line.strip()


def has_bad_markup_or_explanation(line: str) -> bool:
    if not line:
        return True
    if line.startswith(("```", "#", "**", ">", "|")):
        return True
    if re.search(r"[\u4e00-\u9fff]", line):
        return True
    lowered = line.lower()
    return any(word in lowered for word in ("markdown", "here are", "example", "output"))


def normalize_skeleton(line: str) -> str:
    s = line.strip()
    s = re.sub(r"\b\d{4}-\d{2}-\d{2}\b", "<DATE>", s)
    s = re.sub(r"\b\d{4}\.\d{2}\.\d{2}\b", "<DATE>", s)
    s = re.sub(r"\b\d{2}-\d{2}\b", "<MDATE>", s)
    s = re.sub(r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\b", "<MON>", s)
    s = re.sub(r"\b\d{2}:\d{2}:\d{2}(?:[,.]\d+)?\b", "<TIME>", s)
    s = re.sub(r"\b\d{6}\b", "<NUM>", s)
    s = re.sub(r"\b\d{10,}\b", "<NUM>", s)
    s = re.sub(r"\bblk_-?\d+\b", "blk_<NUM>", s)
    s = re.sub(r"\b(application|appattempt|job|attempt|container)_\d+(?:_\d+)*\b", r"\1_<NUM>", s)
    s = re.sub(r"\bR\d{2}-M\d-N[0-9A-F]-[CI]:J\d{2}-U\d{2}\b", "<BGLNODE>", s)
    s = re.sub(r"\bcalvisitor-\d+-\d+-\d+-\d+\b", "<HOST>", s)
    s = re.sub(r"\bairbears2-\d+-\d+-\d+-\d+\b", "<HOST>", s)
    s = re.sub(r"\b[\w-]+\.fareast\.corp\.microsoft\.com\b", "<HOST>", s)
    s = re.sub(r"(\d+\.){3}\d+(?::\d+)?", "<IP>", s)
    s = re.sub(r"0x[0-9a-fA-F]+", "<HEX>", s)
    s = re.sub(r"@[0-9a-fA-F]{4,}", "@<HEX>", s)
    s = re.sub(r"\b[0-9a-fA-F]{8,}\b", "<HEX>", s)
    s = re.sub(r"(?<=[=\[: ,])-?\d+(?:\.\d+)?", "<NUM>", s)
    s = re.sub(r"\b-?\d+(?:\.\d+)?\b", "<NUM>", s)
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def format_ok(dataset: str, line: str) -> bool:
    if has_bad_markup_or_explanation(line):
        return False
    patterns = {
        "Android": r"^\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}\.\d+\s+\d+\s+\d+\s+[A-Z]\s+[^:]+:\s+.+",
        "Apache": r"^\[[A-Z][a-z]{2}\s+[A-Z][a-z]{2}\s+\d{2}\s+\d{2}:\d{2}:\d{2}\s+\d{4}\]\s+\[[a-z]+\]\s+.+",
        "BGL": r"^\S+\s+\d+\s+\d{4}\.\d{2}\.\d{2}\s+\S+\s+\d{4}-\d{2}-\d{2}-\d{2}\.\d{2}\.\d{2}\.\d+\s+\S+\s+\S+\s+\S+\s+\S+\s+.+",
        "HDFS": r"^\d{6}\s+\d{6}\s+\d+\s+[A-Z]+\s+[^:]+:\s+.+",
        "Hadoop": r"^\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2},\d+\s+[A-Z]+\s+\[[^\]]+\]\s+[^:]+:\s+.+",
        "Spark": r"^\d{2}/\d{2}/\d{2}\s+\d{2}:\d{2}:\d{2}\s+[A-Z]+\s+[^:]+:\s+.+",
        "Zookeeper": r"^\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2},\d+\s+-\s+[A-Z]+\s+\s+\[[^\]]+\]\s+-\s+.+",
        "HealthApp": r"^\d{8}-\d{1,2}:\d{1,2}:\d{1,2}:\d+\|[^|]+\|\d+\|.+",
        "OpenSSH": r"^[A-Z][a-z]{2}\s+\d+\s+\d{2}:\d{2}:\d{2}\s+\S+\s+sshd\[\d+\]:\s+.+",
        "OpenStack": r"^\S+\s+\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}\.\d+\s+\d+\s+[A-Z]+\s+\S+\s+\[[^\]]+\]\s+.+",
        "Mac": r"^[A-Z][a-z]{2}\s+\d+\s+\d{2}:\d{2}:\d{2}\s+\S+\s+[\w. ]+\[\d+\](?:\s+\([^)]+\))?:\s+.+",
        "Proxifier": r"^\[\d{2}\.\d{2}\s+\d{2}:\d{2}:\d{2}\]\s+.+\s+-\s+.+",
    }
    pattern = patterns.get(dataset)
    return True if pattern is None else bool(re.match(pattern, line))


def same_template(dataset: str, origin: str, candidate: str) -> bool:
    if candidate == origin:
        return False
    if not format_ok(dataset, candidate):
        return False
    return normalize_skeleton(origin) == normalize_skeleton(candidate)


def rand_time(rng: random.Random, millis: bool = False, comma: bool = False) -> str:
    base = f"{rng.randrange(0, 24):02d}:{rng.randrange(0, 60):02d}:{rng.randrange(0, 60):02d}"
    if millis:
        sep = "," if comma else "."
        base += f"{sep}{rng.randrange(0, 1000):03d}"
    return base


def rand_ip(rng: random.Random, with_port: bool) -> str:
    ip = f"10.{rng.randrange(1, 255)}.{rng.randrange(1, 255)}.{rng.randrange(1, 255)}"
    return f"{ip}:{rng.randrange(1024, 65535)}" if with_port else ip


def rand_hex(rng: random.Random, length: int) -> str:
    length = max(4, min(16, length))
    return "".join(rng.choice("0123456789abcdef") for _ in range(length))


def rand_ymd_dash(rng: random.Random) -> str:
    return f"2005-{rng.randrange(1,13):02d}-{rng.randrange(1,29):02d}"


def rand_ymd_dot(rng: random.Random) -> str:
    return f"2005.{rng.randrange(1,13):02d}.{rng.randrange(1,29):02d}"


def rand_bgl_datetime(rng: random.Random) -> str:
    return (
        f"{rand_ymd_dash(rng)}-"
        f"{rng.randrange(0,24):02d}.{rng.randrange(0,60):02d}.{rng.randrange(0,60):02d}."
        f"{rng.randrange(0,1000000):06d}"
    )


def rand_proxifier_header(rng: random.Random) -> str:
    return f"[{rng.randrange(1,13):02d}.{rng.randrange(1,29):02d} {rand_time(rng)}]"


def preserve_width_number(rng: random.Random, token: str) -> str:
    neg = token.startswith("-")
    body = token[1:] if neg else token
    if "." in body:
        left, right = body.split(".", 1)
        value = f"{rng.randrange(0, 10 ** max(1, len(left))):0{len(left)}d}.{rng.randrange(0, 10 ** len(right)):0{len(right)}d}"
    else:
        width = len(body)
        value = f"{rng.randrange(0, 10 ** min(width, 8)):0{width}d}"
    return "-" + value if neg else value


def mutate_line(dataset: str, line: str, rng: random.Random) -> str:
    s = line
    protected: List[str] = []

    def protect(pattern: str, repl) -> None:
        nonlocal s

        def _replace(match: re.Match) -> str:
            protected.append(repl(match))
            return f"__PROTECTED_{len(protected) - 1}__"

        s = re.sub(pattern, _replace, s)

    protect(r"\[\d{2}\.\d{2}\s+\d{2}:\d{2}:\d{2}\]", lambda _: rand_proxifier_header(rng))
    protect(r"\b\d{4}-\d{2}-\d{2}-\d{2}\.\d{2}\.\d{2}\.\d+\b", lambda _: rand_bgl_datetime(rng))
    protect(r"\b\d{4}-\d{2}-\d{2}\b", lambda _: rand_ymd_dash(rng))
    protect(r"\b\d{4}\.\d{2}\.\d{2}\b", lambda _: rand_ymd_dot(rng))
    protect(r"\b\d{2}-\d{2}\b", lambda _: f"{rng.randrange(1,13):02d}-{rng.randrange(1,29):02d}")
    protect(r"\b\d{2}:\d{2}:\d{2}\.\d+\b", lambda _: rand_time(rng, millis=True))
    protect(r"\b\d{2}:\d{2}:\d{2},\d+\b", lambda _: rand_time(rng, millis=True, comma=True))
    protect(r"\b\d{2}:\d{2}:\d{2}\b", lambda _: rand_time(rng))

    s = re.sub(r"(\d+\.){3}\d+(:\d+)?", lambda m: rand_ip(rng, bool(m.group(2))), s)
    s = re.sub(r"\bblk_-?\d+\b", lambda _: f"blk_{rng.choice(['', '-'])}{rng.randrange(10**17, 10**18)}", s)
    s = re.sub(r"\bapplication_\d+_\d+\b", lambda _: f"application_{rng.randrange(10**12,10**13)}_{rng.randrange(1,9999):04d}", s)
    s = re.sub(r"\bappattempt_\d+_\d+_\d+\b", lambda _: f"appattempt_{rng.randrange(10**12,10**13)}_{rng.randrange(1,9999):04d}_{rng.randrange(1,5):06d}", s)
    s = re.sub(r"\bjob_\d+_\d+\b", lambda _: f"job_{rng.randrange(10**12,10**13)}_{rng.randrange(1,9999):04d}", s)
    s = re.sub(r"\bcontainer_\d+_\d+_\d+_\d+\b", lambda _: f"container_{rng.randrange(10**12,10**13)}_{rng.randrange(1,9999):04d}_{rng.randrange(1,9):02d}_{rng.randrange(1,999999):06d}", s)
    s = re.sub(r"0x[0-9a-fA-F]+", lambda m: "0x" + rand_hex(rng, len(m.group(0)) - 2), s)
    s = re.sub(r"@[0-9a-fA-F]{4,}", lambda m: "@" + rand_hex(rng, len(m.group(0)) - 1), s)
    s = re.sub(r"\b(?=[0-9a-fA-F]*[a-fA-F])[0-9a-fA-F]{8,}\b", lambda m: rand_hex(rng, len(m.group(0))), s)
    s = re.sub(r"\bcore\.\d+\b", lambda _: f"core.{rng.randrange(0, 16)}", s)
    s = re.sub(r"\bcalvisitor-\d+-\d+-\d+-\d+\b", lambda _: f"calvisitor-{rng.randrange(1,255)}-{rng.randrange(1,255)}-{rng.randrange(1,255)}-{rng.randrange(1,255)}", s)
    s = re.sub(r"\bairbears2-\d+-\d+-\d+-\d+\b", lambda _: f"airbears2-{rng.randrange(1,255)}-{rng.randrange(1,255)}-{rng.randrange(1,255)}-{rng.randrange(1,255)}", s)
    s = re.sub(r"\b\d+(?:\.\d+)?\b", lambda m: preserve_width_number(rng, m.group(0)), s)

    for idx, value in enumerate(protected):
        s = s.replace(f"__PROTECTED_{idx}__", value)

    if dataset == "Apache":
        s = DouBao.ensure_apache_header(s)
    return s


def structural_variants(dataset: str, origin: str, count: int, rng: random.Random) -> List[str]:
    out: List[str] = []
    seen = {origin}
    attempts = count * 20
    for _ in range(attempts):
        candidate = clean_candidate(mutate_line(dataset, origin, rng))
        if candidate in seen:
            continue
        if same_template(dataset, origin, candidate):
            seen.add(candidate)
            out.append(candidate)
            if len(out) >= count:
                break
    return out


def load_original_full_lines(dataset: str) -> set:
    original = set()
    for suffix in (".log", ".logs"):
        path = PROJECT_ROOT / "logs" / f"{dataset}_2k{suffix}"
        if path.exists():
            original.update(read_lines(path))
    return original


def load_cached_candidates(dataset: str) -> Tuple[Dict[str, List[str]], List[str]]:
    exact: Dict[str, List[str]] = {}
    pool: List[str] = []

    gpt_path = PROJECT_ROOT / "log_after_gpt" / f"{dataset}_gpt_data.csv"
    if gpt_path.exists():
        with gpt_path.open("r", encoding="gbk", errors="ignore", newline="") as f:
            for row in csv.reader(f):
                if not row or row[0] == "index" or len(row) < 3:
                    continue
                origin = row[1].strip()
                candidates = [clean_candidate(cell) for cell in row[2:] if clean_candidate(cell)]
                exact.setdefault(origin, []).extend(candidates)
                pool.extend(candidates)

    select_dir = PROJECT_ROOT / "log_after_select"
    for select_path in select_dir.glob(f"{dataset}_select_top_*.csv"):
        with select_path.open("r", encoding="gbk", errors="ignore", newline="") as f:
            for row in csv.reader(f):
                if row:
                    pool.append(clean_candidate(row[0]))

    original_full = load_original_full_lines(dataset)
    for new_path in (PROJECT_ROOT / "new_dataset").glob(f"{dataset}_new_dataset*.txt"):
        for line in read_lines(new_path):
            if line not in original_full:
                pool.append(clean_candidate(line))

    dedup_pool: List[str] = []
    seen = set()
    for line in pool:
        if line and line not in seen:
            seen.add(line)
            dedup_pool.append(line)
    return exact, dedup_pool


def build_prompt(dataset: str, origin: str, n: int) -> str:
    return (
        "You are a log data augmenter. Generate new log lines with exactly the "
        "same event template as the source log. Keep fixed words, component, "
        "level, action phrase, error type, and reason phrase unchanged. Only "
        "change obvious variable values such as time, pid, tid, node, IP, port, "
        "block id, hex id, byte/ms counters, uid, coordinates, and numeric "
        "measurements. Do not create a new event type. Output plain log lines "
        "only, no numbering, no markdown, no explanation.\n\n"
        f"Dataset: {dataset}\n"
        f"Source log:\n{origin}\n\n"
        f"Output {n} complete log lines:"
    )


def call_doubao_candidates(dataset: str, origin: str, n: int, api_key: str, model: str) -> List[str]:
    prompt = build_prompt(dataset, origin, n)
    response = DouBao.use_DouBao_api(prompt, api_key, model)
    answer = response.choices[0].message.content
    return [clean_candidate(line) for line in DouBao.clean_llm_response(answer, dataset)]


def augment_dataset(
    dataset: str,
    per_origin: int,
    use_doubao: bool,
    api_key: str,
    model: str,
    api_limit: int,
    seed: int,
) -> dict:
    input_file = INPUT_DIR / dataset / f"{dataset}_lowdiv_singleton_before_dedup.log"
    before_lines = read_lines(input_file)
    exact_cache, pool = load_cached_candidates(dataset)
    rng = random.Random(seed + sum(ord(c) for c in dataset))

    accepted: List[str] = []
    accepted_rows: List[dict] = []
    rejected_rows: List[dict] = []
    api_called = 0

    for idx, origin in enumerate(before_lines):
        per_line: List[str] = []
        seen = {origin}

        def try_add(candidate: str, source: str) -> None:
            candidate = clean_candidate(candidate)
            if not candidate or candidate in seen:
                return
            if same_template(dataset, origin, candidate):
                seen.add(candidate)
                per_line.append(candidate)
                accepted_rows.append({
                    "dataset": dataset,
                    "origin_index": idx,
                    "source": source,
                    "origin": origin,
                    "generated": candidate,
                })
            else:
                if len(rejected_rows) < 300:
                    rejected_rows.append({
                        "dataset": dataset,
                        "origin_index": idx,
                        "source": source,
                        "origin": origin,
                        "generated": candidate,
                        "reason": "format_or_skeleton_mismatch",
                    })

        for candidate in exact_cache.get(origin, []):
            if len(per_line) >= per_origin:
                break
            try_add(candidate, "cached_exact_origin")

        for candidate in pool:
            if len(per_line) >= per_origin:
                break
            try_add(candidate, "cached_template_pool")

        if use_doubao and api_key and model and api_called < api_limit and len(per_line) < per_origin:
            try:
                api_called += 1
                for candidate in call_doubao_candidates(dataset, origin, per_origin - len(per_line), api_key, model):
                    if len(per_line) >= per_origin:
                        break
                    try_add(candidate, "doubao_api")
                time.sleep(1.5)
            except Exception as exc:
                rejected_rows.append({
                    "dataset": dataset,
                    "origin_index": idx,
                    "source": "doubao_api",
                    "origin": origin,
                    "generated": "",
                    "reason": f"{type(exc).__name__}: {exc}",
                })

        if len(per_line) < per_origin:
            for candidate in structural_variants(dataset, origin, per_origin - len(per_line), rng):
                try_add(candidate, "structural_metric_fallback")

        accepted.extend(per_line[:per_origin])

    after_lines = before_lines + [line for line in accepted if line not in before_lines]
    output_file = OUTPUT_DIR / dataset / f"{dataset}_lowdiv_singleton_after_doubao_metric.log"
    after_count = write_lines(output_file, after_lines)

    write_csv(REPORT_DIR / dataset / "accepted_samples.csv", accepted_rows[:500], [
        "dataset", "origin_index", "source", "origin", "generated",
    ])
    write_csv(REPORT_DIR / dataset / "rejected_samples.csv", rejected_rows[:500], [
        "dataset", "origin_index", "source", "origin", "generated", "reason",
    ])
    write_lines(REPORT_DIR / dataset / "prompt_samples.txt", [
        build_prompt(dataset, line, min(5, per_origin)) for line in before_lines[:3]
    ])

    by_source: Dict[str, int] = {}
    for row in accepted_rows:
        by_source[row["source"]] = by_source.get(row["source"], 0) + 1

    return {
        "dataset": dataset,
        "source_file": str(input_file),
        "output_file": str(output_file),
        "before_lines": len(before_lines),
        "target_per_origin": per_origin,
        "cached_exact_accepted": by_source.get("cached_exact_origin", 0),
        "cached_pool_accepted": by_source.get("cached_template_pool", 0),
        "doubao_api_accepted": by_source.get("doubao_api", 0),
        "structural_fallback_accepted": by_source.get("structural_metric_fallback", 0),
        "api_called_count": api_called,
        "accepted_lines": len(accepted),
        "rejected_sampled": len(rejected_rows),
        "final_total_lines": after_count,
    }


def write_csv(path: Path, rows: Sequence[dict], fields: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Aggressively augment low-diversity logs for metric improvement.")
    parser.add_argument("--per-origin", type=int, default=12, help="Accepted generated lines per original before line.")
    parser.add_argument("--seed", type=int, default=20260529)
    parser.add_argument("--use-doubao", action="store_true", help="Call DouBao API if env vars are configured.")
    parser.add_argument("--api-limit-per-dataset", type=int, default=20)
    parser.add_argument("--datasets", nargs="*", default=DATASETS)
    args = parser.parse_args(argv)

    api_key = os.environ.get("DOUBAO_API_KEY") or os.environ.get("ARK_API_KEY") or ""
    model = os.environ.get("DOUBAO_MODEL") or ""
    use_doubao = args.use_doubao and bool(api_key and model)

    if args.use_doubao and not use_doubao:
        print("DouBao API requested but DOUBAO_API_KEY/ARK_API_KEY or DOUBAO_MODEL is missing; using caches and structural fallback.")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    summary = []
    for dataset in args.datasets:
        if dataset not in DATASETS:
            print(f"Skip unknown dataset: {dataset}")
            continue
        print(f"Augmenting {dataset} ...")
        row = augment_dataset(
            dataset=dataset,
            per_origin=args.per_origin,
            use_doubao=use_doubao,
            api_key=api_key,
            model=model,
            api_limit=args.api_limit_per_dataset,
            seed=args.seed,
        )
        summary.append(row)
        print(f"  before={row['before_lines']} accepted={row['accepted_lines']} final={row['final_total_lines']} api_calls={row['api_called_count']}")

    fields = [
        "dataset",
        "source_file",
        "output_file",
        "before_lines",
        "target_per_origin",
        "cached_exact_accepted",
        "cached_pool_accepted",
        "doubao_api_accepted",
        "structural_fallback_accepted",
        "api_called_count",
        "accepted_lines",
        "rejected_sampled",
        "final_total_lines",
    ]
    write_csv(REPORT_DIR / "doubao_metric_augmentation_summary.csv", summary, fields)
    print(f"summary={REPORT_DIR / 'doubao_metric_augmentation_summary.csv'}")
    print(f"output_dir={OUTPUT_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
