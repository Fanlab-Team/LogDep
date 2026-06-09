# LogDep

LogGenius is an unsupervised log parsing experiment framework for evaluating
how parser performance changes under controlled log-diversity levels. It
constructs benchmark datasets at diversity levels from 0.1 to 0.9 and evaluates
multiple log parsers with the same PA, PTA, and RTA metrics.

The repository is organized for paper reproduction: the dataset construction
code, parser evaluation code, parser dependencies, constructed datasets, and
final result tables are all kept in one project directory.

---

## Introduction

Log parsing converts raw system logs into structured templates and variables.
Many parsers behave differently when the input logs have different diversity:
low-diversity logs provide limited variable evidence, while high-diversity logs
usually reveal more stable template-variable boundaries.

This project studies that behavior with a unified evaluation pipeline:

- construct datasets with target diversity scores from `0.1` to `0.9`;
- run multiple parsers on the same datasets;
- evaluate every parser with the same PA, PTA, and RTA metrics;
- collect the final results in CSV and Excel tables.

The current benchmark includes:

- Brain
- Drain
- Spell
- Logram
- LILAC
- LogDep

---

## Framework

The framework contains three main modules.

```text
raw benchmark logs
        |
        v
Ground-truth LD dataset builder
        |
        v
data/gtld/diversity_0_1 ... data/gtld/diversity_0_9
        |
        v
multi-parser evaluator
        |
        v
PA / PTA / RTA result tables
```

Main directories:

```text
Code/                  Main experiment scripts
data/raw_2k/           Original 2k benchmark logs and oracle templates
data/gtld/diversity_0_*/ Parser-visible raw logs for target GTLD levels
external_dependencies/ Third-party parser code used by the evaluator
results/ground_truth_diversity/ Offline GTLD calibration and build reports
results/parser_runs/gtld/       Per-parser evaluation outputs on GTLD data
results/final_metrics/ Final all-parser result tables
```

The archived folders under `Code/archive/` and `Code/legacy_loggenius/` are kept
only for development traceability. They are not required for reproducing the
final results.

---

## Quick Start

### Environment

The scripts are tested with Python 3. Install the common dependencies first:

```bash
pip install pandas jieba nltk openpyxl
```

Some parser backends may require their own dependencies:

```bash
pip install -r external_dependencies/logparser-main/requirements.txt
pip install -r external_dependencies/LILAC-main/requirements.txt
```

LLM API keys are not stored in this repository. Cached results can be inspected
without a key. If you need to re-run API-based LILAC or LogDepFull calls, set a
local environment variable such as:

```bash
export DEEPSEEK_API_KEY=your_local_key
```

On Windows PowerShell:

```powershell
$env:DEEPSEEK_API_KEY="your_local_key"
```

Do not commit real API keys.

### Code & Dataset

The original benchmark files are stored in:

```text
data/raw_2k/
```

The parser-independent diversity-controlled datasets are stored in:

```text
data/gtld/diversity_0_1/
data/gtld/diversity_0_2/
...
data/gtld/diversity_0_9/
```

Each level contains the same 16 benchmark datasets. For example:

```text
data/gtld/diversity_0_1/HDFS/HDFS.log
```

Only raw `.log` files are placed in these parser input directories. Corrected
templates and build reports are kept separately and are never exposed to a
parser during parsing.

### Common Ground-truth LD Axis

The public experiment x-axis is calculated offline from the true template
groups used by the controlled dataset builder. For a true group `G` and its
true variable positions `V_G`:

```text
D(G) = mean over p in V_G of H(X_G,p) / log(|G|)
GTLD = sum_G |G|^alpha * D(G) / sum_G |G|^alpha
```

The current benchmark uses `alpha = 0.5` and reports the macro-average GTLD
over the 16 datasets. Ground-truth information is used only to construct and
label the benchmark and to evaluate PA/PTA/RTA. Every parser independently
receives the same raw logs.

### Build Diversity-Controlled Datasets

To rebuild the Ground-truth LD datasets from `data/raw_2k/`, run:

```bash
python Code/build_datasets.py
python Code/ground_truth_diversity.py
python Code/validate_ground_truth_diversity.py
```

The default `ground-truth` construction mode jointly controls the fraction of
activated true template groups and the normalized entropy of their true
variable positions. A fixed seed gives nested but unbiased active-template
sets across levels. The validation command checks target error, line counts,
nested groups, and that parser input folders contain raw logs only.

For an isolated test build that does not overwrite the main datasets:

```bash
python Code/build_datasets.py --targets 0.1 --datasets HDFS \
  --data-output-root tmp/data --results-output-root tmp/gtld_results
python Code/ground_truth_diversity.py --levels 0_1 --datasets HDFS \
  --data-root tmp/data --build-reports-root tmp/gtld_results/build_reports \
  --output-root tmp/gtld_results
```

The build reports are written to:

```text
results/ground_truth_diversity/build_reports/
results/ground_truth_diversity/level_0_1.csv
results/ground_truth_diversity/calibration.csv
```

The earlier Brain-grouped diversity pipeline remains under `results/diversity/`
only for development traceability. It is not the common x-axis of the current
experiment.

### Evaluate Parsers

To run the default parser set on all diversity levels:

```bash
python Code/eval_parsers.py
```

By default, this evaluates the local parser set:

```text
Drain, Spell, Logram, LogDep, LogDepFull
```

and also collects the cached Brain summary when available.

To evaluate selected parsers:

```bash
python Code/eval_parsers.py --parsers Drain Spell Logram
```

For the main fair LogDepFull experiment, LogDep estimates LD from raw logs and
uses that estimate to decide whether low-diversity LLM augmentation is needed:

```bash
python Code/eval_parsers.py --parsers LogDepFull \
  --skip-existing --allow-logdepfull-api \
  --logdepfull-ld-source estimated
```

`--logdepfull-ld-source oracle` exposes per-dataset Ground-truth LD to LogDep
and must be reported only as an ablation upper bound, never as the main result.
To quantify runtime estimation error after a LogDepFull run:

```bash
python Code/analyze_estimated_ld.py
```

To evaluate Brain only:

```bash
python Code/eval_brain.py
```

To regenerate the final all-parser CSV and Excel tables from the parser
summaries:

```bash
python Code/build_final_metrics.py
```

Run this only after Brain, Drain, Spell, Logram, LILAC, and the final
LLM-enhanced LogDepFull configuration all contain nine GTLD-level rows.

---

## Examples

Final all-parser results:

```text
results/final_metrics/all_metrics.csv
results/final_metrics/all_metrics.xlsx
```

Per-parser result tables:

```text
results/parser_runs/gtld/parser_eval/per_parser/
```

LogDep detailed outputs:

```text
results/parser_runs/gtld/parser_eval/LogDepFull/
```

Each parser has 10 rows in the final result table:

- 9 rows for diversity levels `0.1` to `0.9`;
- 1 row for the average score.

The final metrics are:

- `PA`: parsing accuracy;
- `PTA`: template precision accuracy;
- `RTA`: recovered template accuracy.

---

## Reproducibility Notes

- The project uses project-relative paths by default.
- `external_dependencies/` contains the parser code required by the final
  evaluation pipeline. It is a compact experiment dependency copy, not a full
  mirror of every original upstream repository.
- Real API key files are intentionally excluded.
- LILAC and LLM-enhanced LogDepFull runs on newly constructed logs require
  fresh API outputs unless matching caches already exist.
- Brain, Drain, Spell, Logram, base LogDep, LILAC, and LogDepFull can be
  re-evaluated on all nine diversity levels with the current scripts.

Current migration status: the GTLD datasets and the Brain, Drain, Spell,
Logram, and grammar-only LogDepFull reruns are complete. LILAC and the
LLM-enabled LogDepFull rerun are still required before replacing the
paper-facing tables under `results/final_metrics/`.

---

## Contributes

Contributions are welcome. Useful improvements include:

- adding a clean `requirements.txt`;
- adding Linux shell scripts equivalent to the current PowerShell helper;
- adding plotting scripts for PA/PTA/RTA over diversity;
- adding support for more log parsers or benchmark datasets;
- improving documentation for reproducing API-based experiments.

---

## License

This repository currently does not include a top-level license file. Please add
one before public release. Third-party parser dependencies under
`external_dependencies/` keep their original licenses and notices.
