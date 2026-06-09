#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Strict DouBao augmentation for dir_lowdiv_singleton_before_dedup.

This script does not use historical new_dataset/log_after_gpt caches and does
not generate deterministic fallback rows. Every appended row must come from a
fresh DouBao API response for one source line in the before dataset.

Credentials are read from environment variables only:
  DOUBAO_API_KEY or ARK_API_KEY
  DOUBAO_MODEL

Outputs:
  dir_lowdiv_singleton_after_doubao_api_strict/
  doubao_api_strict_report/
"""

from __future__ import annotations

import argparse
import csv
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence


SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(SCRIPT_DIR))

import DouBao
import run_lowdiv_doubao_metric_augment as metric


INPUT_DIR = PROJECT_ROOT / "dir_lowdiv_singleton_before_dedup"
OUTPUT_DIR = PROJECT_ROOT / "dir_lowdiv_singleton_after_doubao_api_strict"
REPORT_DIR = PROJECT_ROOT / "doubao_api_strict_report"
AFTER_SIZE = "lowdiv_singleton_after_doubao_api_strict_dedup"
BEFORE_SIZE = "lowdiv_singleton_before_dedup"


def get_env(name: str) -> str:
    value = os.environ.get(name, "")
    if value:
        return value
    if os.name == "nt":
        try:
            import winreg

            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as key:
                user_value, _ = winreg.QueryValueEx(key, name)
                return str(user_value)
        except OSError:
            return ""
    return ""


def write_csv(path: Path, rows: Sequence[dict], fields: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def append_csv(path: Path, row: dict, fields: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    exists = path.exists() and path.stat().st_size > 0
    with path.open("a", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        if not exists:
            writer.writeheader()
        writer.writerow({field: row.get(field, "") for field in fields})


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


def read_previous_accepted(dataset: str) -> Dict[str, List[str]]:
    path = REPORT_DIR / dataset / "accepted_samples.csv"
    accepted: Dict[str, List[str]] = {}
    if not path.exists():
        return accepted
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            origin = row.get("origin", "")
            generated = row.get("generated", "")
            if origin and generated:
                accepted.setdefault(origin, []).append(generated)
    return accepted


def build_prompt(dataset: str, origin: str, count: int) -> str:
    skeleton = metric.normalize_skeleton(origin)
    return (
        "浣犳槸鏃ュ織鏁版嵁澧炲己鍣ㄣ€傝鍩轰簬缁欏畾鍘熷鏃ュ織锛岀敓鎴愯嫢骞叉潯鍚屾ā鏉跨殑鏂版棩蹇椼€俓n"
        "涓ユ牸瑙勫垯锛歕n"
        "1. 鍙兘鐢熸垚涓庡師濮嬫棩蹇楃浉鍚屼簨浠舵ā鏉跨殑瀹屾暣鏃ュ織琛屻€俓n"
        "2. 鍥哄畾瀛楁銆丆omponent銆丩evel銆乤ction銆侀敊璇被鍨嬨€佸浐瀹?reason銆佸浐瀹氫簨浠剁煭璇繀椤讳繚鎸佷笉鍙樸€俓n"
        "3. 鍙兘鏇挎崲鏄庢樉鍙橀噺瀛楁锛屼緥濡傛椂闂淬€佽妭鐐广€丳ID銆乀ID銆佹暟瀛椼€両P銆佺鍙ｃ€乥lock id銆乭ex id銆乵s銆乥ytes銆乽id銆佸潗鏍囩瓑銆俓n"
        "4. 涓嶈鐢熸垚鍏ㄦ柊鐨勪簨浠剁被鍨嬶紝涓嶈鏀瑰啓璇箟锛屼笉瑕佽ˉ鍏呰В閲娿€俓n"
        "5. 鍙緭鍑虹函鏃ュ織琛岋紝涓嶈 Markdown锛屼笉瑕佺紪鍙凤紝涓嶈绌鸿銆俓n"
        "6. 濡傛灉涓嶇‘瀹氭煇涓瓧娈垫槸涓嶆槸鍙橀噺锛屽氨淇濇寔鍘熷€笺€俓n\n"
        f"Dataset: {dataset}\n"
        f"缁撴瀯楠ㄦ灦鍙傝€? {skeleton}\n"
        f"鍘熷鏃ュ織:\n{origin}\n\n"
        f"璇疯緭鍑?{count} 鏉″畬鏁存棩蹇楄锛?
    )


def parse_response(answer: str, dataset: str) -> List[str]:
    raw_lines = DouBao.clean_llm_response(answer, dataset)
    cleaned: List[str] = []
    for line in raw_lines:
        line = metric.clean_candidate(line)
        if line:
            cleaned.append(line)
    return cleaned


def call_doubao(prompt: str, api_key: str, model: str, retries: int) -> str:
    last_error: Optional[BaseException] = None
    for attempt in range(retries):
        try:
            response = DouBao.use_DouBao_api(prompt, api_key, model)
            return response.choices[0].message.content
        except Exception as exc:
            last_error = exc
            wait = 3 + attempt * 2
            print(f"    retry {attempt + 1}/{retries}: {type(exc).__name__}: {exc}; wait {wait}s")
            time.sleep(wait)
    raise RuntimeError(f"DouBao failed after {retries} retries: {last_error}")


def augment_dataset(
    dataset: str,
    api_key: str,
    model: str,
    per_origin: int,
    lines_per_call: int,
    rounds: int,
    retries: int,
    sleep_seconds: float,
    max_calls: Optional[int],
    resume: bool,
) -> dict:
    input_file = INPUT_DIR / dataset / f"{dataset}_{BEFORE_SIZE}.log"
    before_lines = metric.read_lines(input_file)
    previous = read_previous_accepted(dataset) if resume else {}

    accepted_rows: List[dict] = []
    rejected_rows: List[dict] = []
    accepted_by_origin: Dict[str, List[str]] = {origin: list(previous.get(origin, [])) for origin in before_lines}
    raw_response_path = REPORT_DIR / dataset / "raw_responses.txt"
    prompt_path = REPORT_DIR / dataset / "prompt_samples.txt"
    accepted_path = REPORT_DIR / dataset / "accepted_samples.csv"
    rejected_path = REPORT_DIR / dataset / "rejected_samples.csv"
    (REPORT_DIR / dataset).mkdir(parents=True, exist_ok=True)

    if not resume:
        for path in (raw_response_path, prompt_path, accepted_path, rejected_path):
            if path.exists():
                path.unlink()

    accepted_fields = ["dataset", "origin_index", "round", "origin", "generated"]
    rejected_fields = ["dataset", "origin_index", "round", "origin", "generated", "reason"]

    api_calls = 0
    for idx, origin in enumerate(before_lines):
        origin_seen = {origin, *accepted_by_origin.get(origin, [])}
        if len(accepted_by_origin.get(origin, [])) >= per_origin:
            continue

        for round_idx in range(rounds):
            if len(accepted_by_origin[origin]) >= per_origin:
                break
            if max_calls is not None and api_calls >= max_calls:
                break

            need = max(lines_per_call, per_origin - len(accepted_by_origin[origin]))
            prompt = build_prompt(dataset, origin, need)
            if idx < 3 and round_idx == 0:
                with prompt_path.open("a", encoding="utf-8", newline="\n") as f:
                    f.write(prompt + "\n\n---\n\n")

            api_calls += 1
            print(f"  {dataset} origin={idx + 1}/{len(before_lines)} round={round_idx + 1}, accepted={len(accepted_by_origin[origin])}/{per_origin}")
            answer = call_doubao(prompt, api_key, model, retries)
            with raw_response_path.open("a", encoding="utf-8", newline="\n") as f:
                f.write(f"### origin={idx} round={round_idx}\n{answer}\n\n")

            for candidate in parse_response(answer, dataset):
                if len(accepted_by_origin[origin]) >= per_origin:
                    break
                if candidate in origin_seen:
                    continue
                if metric.same_template(dataset, origin, candidate):
                    origin_seen.add(candidate)
                    accepted_by_origin[origin].append(candidate)
                    row = {
                        "dataset": dataset,
                        "origin_index": idx,
                        "round": round_idx,
                        "origin": origin,
                        "generated": candidate,
                    }
                    accepted_rows.append(row)
                    append_csv(accepted_path, row, accepted_fields)
                else:
                    row = {
                        "dataset": dataset,
                        "origin_index": idx,
                        "round": round_idx,
                        "origin": origin,
                        "generated": candidate,
                        "reason": "format_or_skeleton_mismatch",
                    }
                    rejected_rows.append(row)
                    append_csv(rejected_path, row, rejected_fields)
            time.sleep(sleep_seconds)

        if max_calls is not None and api_calls >= max_calls:
            break

    added: List[str] = []
    seen_added = set(before_lines)
    for origin in before_lines:
        for line in accepted_by_origin.get(origin, [])[:per_origin]:
            if line not in seen_added:
                seen_added.add(line)
                added.append(line)

    output_file = OUTPUT_DIR / dataset / f"{dataset}_lowdiv_singleton_after_doubao_api_strict.log"
    final_total = write_lines(output_file, before_lines + added)

    return {
        "dataset": dataset,
        "source_file": str(input_file),
        "output_file": str(output_file),
        "before_lines": len(before_lines),
        "target_per_origin": per_origin,
        "api_called_count": api_calls,
        "accepted_lines": len(added),
        "rejected_lines": len(rejected_rows),
        "final_total_lines": final_total,
    }


def copy_for_eval(temp_root: Path, after_dir: Path, eval_root: Path) -> None:
    shutil.copytree(eval_root / "Code_LogIterSplit", temp_root / "Code_LogIterSplit")
    shutil.copytree(eval_root / "data" / "raw_2k", temp_root / "data" / "raw_2k")
    for dataset in metric.DATASETS:
        before_src = INPUT_DIR / dataset / f"{dataset}_{BEFORE_SIZE}.log"
        after_src = after_dir / dataset / f"{dataset}_lowdiv_singleton_after_doubao_api_strict.log"
        before_dst = temp_root / "data" / f"dir_{BEFORE_SIZE}" / dataset / f"{dataset}_{BEFORE_SIZE}.log"
        after_dst = temp_root / "data" / f"dir_{AFTER_SIZE}" / dataset / f"{dataset}_{AFTER_SIZE}.log"
        before_dst.parent.mkdir(parents=True, exist_ok=True)
        after_dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(before_src, before_dst)
        shutil.copy2(after_src, after_dst)


def run_eval(data_size: str, temp_root: Path, out_path: Path) -> None:
    code_dir = temp_root / "Code_LogIterSplit"
    cmd = [sys.executable, "-c", f"import runLogIterSplit; runLogIterSplit.save_evaluation_results_to_csv(data_size='{data_size}')"]
    subprocess.run(cmd, cwd=str(code_dir), check=True)
    shutil.copy2(temp_root / "result" / "evaluation_results.csv", out_path)


def read_metric_rows(path: Path) -> Dict[str, dict]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return {row["dataset"]: row for row in csv.DictReader(f)}


def write_compare(before_csv: Path, after_csv: Path, out_path: Path) -> dict:
    before = read_metric_rows(before_csv)
    after = read_metric_rows(after_csv)
    fields = ["dataset", "before_PA", "after_PA", "delta_PA", "before_PTA", "after_PTA", "delta_PTA", "before_RTA", "after_RTA", "delta_RTA"]
    rows: List[dict] = []
    average = {}
    for dataset in metric.DATASETS + ["AVERAGE"]:
        if dataset not in before or dataset not in after:
            continue
        row = {"dataset": dataset}
        for metric_name in ("PA", "PTA", "RTA"):
            bv = float(before[dataset][metric_name])
            av = float(after[dataset][metric_name])
            row[f"before_{metric_name}"] = f"{bv:.4f}"
            row[f"after_{metric_name}"] = f"{av:.4f}"
            row[f"delta_{metric_name}"] = f"{av - bv:+.4f}"
            if dataset == "AVERAGE":
                average[f"delta_{metric_name}"] = av - bv
        rows.append(row)
    write_csv(out_path, rows, fields)
    return average


def maybe_run_eval(eval_root: Path, require_improvement: bool) -> None:
    if not eval_root.exists():
        print(f"Skip eval: evaluator root not found: {eval_root}")
        return
    temp_root = PROJECT_ROOT / f"temp_doubao_api_strict_eval_{int(time.time())}"
    if temp_root.exists():
        shutil.rmtree(temp_root)
    (temp_root / "data").mkdir(parents=True)
    copy_for_eval(temp_root, OUTPUT_DIR, eval_root)
    before_csv = REPORT_DIR / "evaluation_before.csv"
    after_csv = REPORT_DIR / "evaluation_after_doubao_api_strict.csv"
    run_eval(BEFORE_SIZE, temp_root, before_csv)
    run_eval(AFTER_SIZE, temp_root, after_csv)
    avg = write_compare(before_csv, after_csv, REPORT_DIR / "evaluation_compare_doubao_api_strict.csv")
    if require_improvement and not all(avg.get(f"delta_{m}", -1) > 0 for m in ("PA", "PTA", "RTA")):
        print("WARNING: average PA/PTA/RTA did not all improve. Keep generated files for inspection, but do not treat this as final.")
    shutil.rmtree(temp_root, ignore_errors=True)


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Fresh DouBao API-only augmentation for low-diversity before logs.")
    parser.add_argument("--datasets", nargs="*", default=metric.DATASETS)
    parser.add_argument("--per-origin", type=int, default=8)
    parser.add_argument("--lines-per-call", type=int, default=12)
    parser.add_argument("--rounds", type=int, default=2)
    parser.add_argument("--retries", type=int, default=3)
    parser.add_argument("--sleep", type=float, default=1.5)
    parser.add_argument("--max-calls-per-dataset", type=int, default=None)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--eval", action="store_true")
    parser.add_argument("--eval-root", default=r"C:\Users\86130\Desktop\Next_test")
    parser.add_argument("--require-improvement", action="store_true")
    args = parser.parse_args(argv)

    api_key = get_env("DOUBAO_API_KEY") or get_env("ARK_API_KEY")
    model = get_env("DOUBAO_MODEL")
    if not api_key or not model:
        print("Missing DouBao credentials.")
        print("Set DOUBAO_API_KEY (or ARK_API_KEY) and DOUBAO_MODEL, then rerun.")
        return 2

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    summary: List[dict] = []
    for dataset in args.datasets:
        if dataset not in metric.DATASETS:
            print(f"Skip unknown dataset: {dataset}")
            continue
        print(f"Strict DouBao augment: {dataset}")
        row = augment_dataset(
            dataset=dataset,
            api_key=api_key,
            model=model,
            per_origin=args.per_origin,
            lines_per_call=args.lines_per_call,
            rounds=args.rounds,
            retries=args.retries,
            sleep_seconds=args.sleep,
            max_calls=args.max_calls_per_dataset,
            resume=args.resume,
        )
        summary.append(row)
        print(f"  before={row['before_lines']} accepted={row['accepted_lines']} final={row['final_total_lines']} api_calls={row['api_called_count']}")

    write_csv(
        REPORT_DIR / "doubao_api_strict_summary.csv",
        summary,
        [
            "dataset",
            "source_file",
            "output_file",
            "before_lines",
            "target_per_origin",
            "api_called_count",
            "accepted_lines",
            "rejected_lines",
            "final_total_lines",
        ],
    )

    if args.eval:
        maybe_run_eval(Path(args.eval_root), args.require_improvement)

    print(f"output_dir={OUTPUT_DIR}")
    print(f"report_dir={REPORT_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
