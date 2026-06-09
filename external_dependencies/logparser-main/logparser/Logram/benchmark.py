# =========================================================================
# Copyright (C) 2016-2023 LOGPAI (https://github.com/logpai).
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# =========================================================================


import sys

from sympy import false

sys.path.append("../../")
from logparser.Logram import LogParser
from logparser.utils import evaluator
import os
import pandas as pd
import time
import gc

test_set = ['BGL','HDFS','Spark','Thunderbird']

def main(input_dir=None,is_time=None,data_scale=None):
    # 如果没有传参数，则使用默认的 2k 路径
    if data_scale is None or "loghub_2k_corrected" in input_dir or "dir_dedup" in input_dir:

        if input_dir is None or "loghub_2k_corrected" in input_dir:
            input_dir = "../../data/loghub_2k_corrected"
        benchmark_settings = {
            "HDFS": {
                "log_file": "HDFS/HDFS_2k.log",
                "log_format": "<Date> <Time> <Pid> <Level> <Component>: <Content>",
                "regex": [
                    r"blk_(|-)[0-9]+",  # block id
                    r"(/|)([0-9]+\.){3}[0-9]+(:[0-9]+|)(:|)",  # IP
                    r"(?<=[^A-Za-z0-9])(\-?\+?\d+)(?=[^A-Za-z0-9])|[0-9]+$",
                ],
                "doubleThreshold": 15,
                "triThreshold": 10,
            },
            "Hadoop": {
                "log_file": "Hadoop/Hadoop_2k.log",
                "log_format": "<Date> <Time> <Level> \[<Process>\] <Component>: <Content>",
                "regex": [r"(\d+\.){3}\d+"],
                "doubleThreshold": 9,
                "triThreshold": 10,
            },
            "Spark": {
                "log_file": "Spark/Spark_2k.log",
                "log_format": "<Date> <Time> <Level> <Component>: <Content>",
                "regex": [r"(\d+\.){3}\d+", r"\b[KGTM]?B\b", r"([\w-]+\.){2,}[\w-]+"],
                "doubleThreshold": 15,
                "triThreshold": 10,
            },
            "Zookeeper": {
                "log_file": "Zookeeper/Zookeeper_2k.log",
                "log_format": "<Date> <Time> - <Level>  \[<Node>:<Component>@<Id>\] - <Content>",
                "regex": [r"(/|)(\d+\.){3}\d+(:\d+)?"],
                "doubleThreshold": 15,
                "triThreshold": 10,
            },
            "BGL": {
                "log_file": "BGL/BGL_2k.log",
                "log_format": "<Label> <Timestamp> <Date> <Node> <Time> <NodeRepeat> <Type> <Component> <Level> <Content>",
                "regex": [r"core\.\d+"],
                "doubleThreshold": 92,
                "triThreshold": 4,
            },
            "HPC": {
                "log_file": "HPC/HPC_2k.log",
                "log_format": "<LogId> <Node> <Component> <State> <Time> <Flag> <Content>",
                "regex": [r"=\d+"],
                "doubleThreshold": 15,
                "triThreshold": 10,
            },
            "Thunderbird": {
                "log_file": "Thunderbird/Thunderbird_2k.log",
                "log_format": "<Label> <Timestamp> <Date> <User> <Month> <Day> <Time> <Location> <Component>(\[<PID>\])?: <Content>",
                "regex": [r"(\d+\.){3}\d+"],
                "doubleThreshold": 35,
                "triThreshold": 32,
            },
            "Windows": {
                "log_file": "Windows/Windows_2k.log",
                "log_format": "<Date> <Time>, <Level>                  <Component>    <Content>",
                "regex": [r"0x.*?\s"],
                "doubleThreshold": 15,
                "triThreshold": 10,
            },
            "Linux": {
                "log_file": "Linux/Linux_2k.log",
                "log_format": "<Month> <Date> <Time> <Level> <Component>(\[<PID>\])?: <Content>",
                "regex": [r"(\d+\.){3}\d+", r"\d{2}:\d{2}:\d{2}"],
                "doubleThreshold": 120,
                "triThreshold": 100,
            },
            "Android": {
                "log_file": "Android/Android_2k.log",
                "log_format": "<Date> <Time>  <Pid>  <Tid> <Level> <Component>: <Content>",
                "regex": [
                    r"(/[\w-]+)+",
                    r"([\w-]+\.){2,}[\w-]+",
                    r"\b(\-?\+?\d+)\b|\b0[Xx][a-fA-F\d]+\b|\b[a-fA-F\d]{4,}\b",
                ],
                "doubleThreshold": 15,
                "triThreshold": 10,
            },
            "HealthApp": {
                "log_file": "HealthApp/HealthApp_2k.log",
                "log_format": "<Time>\|<Component>\|<Pid>\|<Content>",
                "regex": [],
                "doubleThreshold": 15,
                "triThreshold": 10,
            },
            "Apache": {
                "log_file": "Apache/Apache_2k.log",
                "log_format": "\[<Time>\] \[<Level>\] <Content>",
                "regex": [r"(\d+\.){3}\d+"],
                "doubleThreshold": 15,
                "triThreshold": 10,
            },
            "Proxifier": {
                "log_file": "Proxifier/Proxifier_2k.log",
                "log_format": "\[<Time>\] <Program> - <Content>",
                "regex": [
                    r"<\d+\ssec",
                    r"([\w-]+\.)+[\w-]+(:\d+)?",
                    r"\d{2}:\d{2}(:\d{2})*",
                    r"[KGTM]B",
                ],
                "doubleThreshold": 500,
                "triThreshold": 470,
            },
            "OpenSSH": {
                "log_file": "OpenSSH/OpenSSH_2k.log",
                "log_format": "<Date> <Day> <Time> <Component> sshd\[<Pid>\]: <Content>",
                "regex": [r"(\d+\.){3}\d+", r"([\w-]+\.){2,}[\w-]+"],
                "doubleThreshold": 88,
                "triThreshold": 81,
            },
            "OpenStack": {
                "log_file": "OpenStack/OpenStack_2k.log",
                "log_format": "<Logrecord> <Date> <Time> <Pid> <Level> <Component> \[<ADDR>\] <Content>",
                "regex": [r"((\d+\.){3}\d+,?)+", r"/.+?\s", r"\d+"],
                "doubleThreshold": 30,
                "triThreshold": 25,
            },
            "Mac": {
                "log_file": "Mac/Mac_2k.log",
                "log_format": "<Month>  <Date> <Time> <User> <Component>\[<PID>\]( \(<Address>\))?: <Content>",
                "regex": [r"([\w-]+\.){2,}[\w-]+"],
                "doubleThreshold": 2,
                "triThreshold": 2,
            },
        }
    else:
        benchmark_settings = {
            "HDFS": {
                "log_file": "HDFS/HDFS_full.log",
                "log_format": "<Date> <Time> <Pid> <Level> <Component>: <Content>",
                "regex": [
                    r"blk_(|-)[0-9]+",  # block id
                    r"(/|)([0-9]+\.){3}[0-9]+(:[0-9]+|)(:|)",  # IP
                    r"(?<=[^A-Za-z0-9])(\-?\+?\d+)(?=[^A-Za-z0-9])|[0-9]+$",
                ],
                "doubleThreshold": 15,
                "triThreshold": 10,
            },
            "Hadoop": {
                "log_file": "Hadoop/Hadoop_full.log",
                "log_format": "<Date> <Time> <Level> \[<Process>\] <Component>: <Content>",
                "regex": [r"(\d+\.){3}\d+"],
                "doubleThreshold": 9,
                "triThreshold": 10,
            },
            "Spark": {
                "log_file": "Spark/Spark_full.log",
                "log_format": "<Date> <Time> <Level> <Component>: <Content>",
                "regex": [r"(\d+\.){3}\d+", r"\b[KGTM]?B\b", r"([\w-]+\.){2,}[\w-]+"],
                "doubleThreshold": 15,
                "triThreshold": 10,
            },
            "Zookeeper": {
                "log_file": "Zookeeper/Zookeeper_full.log",
                "log_format": "<Date> <Time> - <Level>  \[<Node>:<Component>@<Id>\] - <Content>",
                "regex": [r"(/|)(\d+\.){3}\d+(:\d+)?"],
                "doubleThreshold": 15,
                "triThreshold": 10,
            },
            "BGL": {
                "log_file": "BGL/BGL_full.log",
                "log_format": "<Label> <Timestamp> <Date> <Node> <Time> <NodeRepeat> <Type> <Component> <Level> <Content>",
                "regex": [r"core\.\d+"],
                "doubleThreshold": 92,
                "triThreshold": 4,
            },
            "HPC": {
                "log_file": "HPC/HPC_full.log",
                "log_format": "<LogId> <Node> <Component> <State> <Time> <Flag> <Content>",
                "regex": [r"=\d+"],
                "doubleThreshold": 15,
                "triThreshold": 10,
            },
            "Thunderbird": {
                "log_file": "Thunderbird/Thunderbird_full.log",
                "log_format": "<Label> <Timestamp> <Date> <User> <Month> <Day> <Time> <Location> <Component>(\[<PID>\])?: <Content>",
                "regex": [r"(\d+\.){3}\d+"],
                "doubleThreshold": 35,
                "triThreshold": 32,
            },
            "Linux": {
                "log_file": "Linux/Linux_full.log",
                "log_format": "<Month> <Date> <Time> <Level> <Component>(\[<PID>\])?: <Content>",
                "regex": [r"(\d+\.){3}\d+", r"\d{2}:\d{2}:\d{2}"],
                "doubleThreshold": 120,
                "triThreshold": 100,
            },
            "HealthApp": {
                "log_file": "HealthApp/HealthApp_full.log",
                "log_format": "<Time>\|<Component>\|<Pid>\|<Content>",
                "regex": [],
                "doubleThreshold": 15,
                "triThreshold": 10,
            },
            "Apache": {
                "log_file": "Apache/Apache_full.log",
                "log_format": "\[<Time>\] \[<Level>\] <Content>",
                "regex": [r"(\d+\.){3}\d+"],
                "doubleThreshold": 15,
                "triThreshold": 10,
            },
            "Proxifier": {
                "log_file": "Proxifier/Proxifier_full.log",
                "log_format": "\[<Time>\] <Program> - <Content>",
                "regex": [
                    r"<\d+\ssec",
                    r"([\w-]+\.)+[\w-]+(:\d+)?",
                    r"\d{2}:\d{2}(:\d{2})*",
                    r"[KGTM]B",
                ],
                "doubleThreshold": 500,
                "triThreshold": 470,
            },
            "OpenSSH": {
                "log_file": "OpenSSH/OpenSSH_full.log",
                "log_format": "<Date> <Day> <Time> <Component> sshd\[<Pid>\]: <Content>",
                "regex": [r"(\d+\.){3}\d+", r"([\w-]+\.){2,}[\w-]+"],
                "doubleThreshold": 88,
                "triThreshold": 81,
            },
            "OpenStack": {
                "log_file": "OpenStack/OpenStack_full.log",
                "log_format": "<Logrecord> <Date> <Time> <Pid> <Level> <Component> \[<ADDR>\] <Content>",
                "regex": [r"((\d+\.){3}\d+,?)+", r"/.+?\s", r"\d+"],
                "doubleThreshold": 30,
                "triThreshold": 25,
            },
        }

    # 确保路径结尾有斜杠
    if not input_dir.endswith(os.sep):
        input_dir += os.sep

    output_dir = "Logram_result/"  # The output directory of parsing results

    bechmark_result = []
    dataset_timing = {}

    for dataset, setting in benchmark_settings.items():
        # 3/11添加
        if dataset not in test_set:
            print(f"Dataset {dataset} not in test set, skipped")
            continue

        print("\n=== Evaluation on %s ===" % dataset)
        if "dir_dedup" in input_dir:
            tmp = setting["log_file"].replace("2k",f"dedup_{data_scale}")
        else:
            tmp = setting["log_file"]
        indir = os.path.join(input_dir, os.path.dirname(tmp))
        log_file = os.path.basename(tmp)

        parser = LogParser(
            log_format=setting["log_format"],
            indir=indir,
            outdir=output_dir,
            rex=setting["regex"],
            doubleThreshold=setting["doubleThreshold"],
            triThreshold=setting["triThreshold"],
        )
        # --- parsing time ---
        start_time = time.time()

        parser.parse(log_file)  # start parsing

        parse_time = time.time() - start_time
        dataset_timing[dataset] = parse_time
        # --- parsing time ---

        if is_time == false:
            F1_measure, accuracy = evaluator.evaluate(
                groundtruth=os.path.join(indir, log_file + "_structured.csv"),
                parsedresult=os.path.join(output_dir, log_file + "_structured.csv"),
            )
            bechmark_result.append([dataset, F1_measure, accuracy])
        # 3. 释放内存 (放在当前循环的最末尾)
        print(f"Clearing memory for {dataset}...")
        del parser
        gc.collect()
    if is_time == false:
        print("\n=== Overall evaluation results ===")
        df_result = pd.DataFrame(bechmark_result, columns=["Dataset", "F1_measure", "Accuracy"])
        df_result.set_index("Dataset", inplace=True)
        print(df_result)
        df_result.to_csv("Logram_bechmark_result.csv", float_format="%.6f")
    return dataset_timing

if __name__ == "__main__":
    main()