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
import os

from sympy import false

sys.path.append("../../")
from logparser.Drain import LogParser
from logparser.utils import evaluator
import pandas as pd
import time
import gc

test_set = ['BGL','HDFS','Spark','Thunderbird']
def main(input_dir=None,is_time=None,data_scale=None):
    print("\n=== BENCHMARK ===")

    # 如果没有传参数，则使用默认的 2k 路径
    if data_scale is None or "loghub_2k_corrected" in input_dir or "dir_dedup" in input_dir or "genius" in data_scale:
        if input_dir is None or "loghub_2k_corrected" in input_dir:
            input_dir = "../../data/loghub_2k_corrected"
        benchmark_settings = {
            "HDFS": {
                "log_file": "HDFS/HDFS_2k.log",
                "log_format": "<Date> <Time> <Pid> <Level> <Component>: <Content>",
                "regex": [r"blk_-?\d+", r"(\d+\.){3}\d+(:\d+)?"],
                "st": 0.5,
                "depth": 4,
            },
            "Hadoop": {
                "log_file": "Hadoop/Hadoop_2k.log",
                "log_format": "<Date> <Time> <Level> \[<Process>\] <Component>: <Content>",
                "regex": [r"(\d+\.){3}\d+"],
                "st": 0.5,
                "depth": 4,
            },
            "Spark": {
                "log_file": "Spark/Spark_2k.log",
                "log_format": "<Date> <Time> <Level> <Component>: <Content>",
                "regex": [r"(\d+\.){3}\d+", r"\b[KGTM]?B\b", r"([\w-]+\.){2,}[\w-]+"],
                "st": 0.5,
                "depth": 4,
            },
            "Zookeeper": {
                "log_file": "Zookeeper/Zookeeper_2k.log",
                "log_format": "<Date> <Time> - <Level>  \[<Node>:<Component>@<Id>\] - <Content>",
                "regex": [r"(/|)(\d+\.){3}\d+(:\d+)?"],
                "st": 0.5,
                "depth": 4,
            },
            "BGL": {
                "log_file": "BGL/BGL_2k.log",
                "log_format": "<Label> <Timestamp> <Date> <Node> <Time> <NodeRepeat> <Type> <Component> <Level> <Content>",
                "regex": [r"core\.\d+"],
                "st": 0.5,
                "depth": 4,
            },
            "HPC": {
                "log_file": "HPC/HPC_2k.log",
                "log_format": "<LogId> <Node> <Component> <State> <Time> <Flag> <Content>",
                "regex": [r"=\d+"],
                "st": 0.5,
                "depth": 4,
            },
            "Thunderbird": {
                "log_file": "Thunderbird/Thunderbird_2k.log",
                "log_format": "<Label> <Timestamp> <Date> <User> <Month> <Day> <Time> <Location> <Component>(\[<PID>\])?: <Content>",
                "regex": [r"(\d+\.){3}\d+"],
                "st": 0.5,
                "depth": 4,
            },
            "Windows": {
                "log_file": "Windows/Windows_2k.log",
                "log_format": "<Date> <Time>, <Level>                  <Component>    <Content>",
                "regex": [r"0x.*?\s"],
                "st": 0.7,
                "depth": 5,
            },
            "Linux": {
                "log_file": "Linux/Linux_2k.log",
                "log_format": "<Month> <Date> <Time> <Level> <Component>(\[<PID>\])?: <Content>",
                "regex": [r"(\d+\.){3}\d+", r"\d{2}:\d{2}:\d{2}"],
                "st": 0.39,
                "depth": 6,
            },
            "Android": {
                "log_file": "Android/Android_2k.log",
                "log_format": "<Date> <Time>  <Pid>  <Tid> <Level> <Component>: <Content>",
                "regex": [
                    r"(/[\w-]+)+",
                    r"([\w-]+\.){2,}[\w-]+",
                    r"\b(\-?\+?\d+)\b|\b0[Xx][a-fA-F\d]+\b|\b[a-fA-F\d]{4,}\b",
                ],
                "st": 0.2,
                "depth": 6,
            },
            "HealthApp": {
                "log_file": "HealthApp/HealthApp_2k.log",
                "log_format": "<Time>\|<Component>\|<Pid>\|<Content>",
                "regex": [],
                "st": 0.2,
                "depth": 4,
            },
            "Apache": {
                "log_file": "Apache/Apache_2k.log",
                "log_format": "\[<Time>\] \[<Level>\] <Content>",
                "regex": [r"(\d+\.){3}\d+"],
                "st": 0.5,
                "depth": 4,
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
                "st": 0.6,
                "depth": 3,
            },
            "OpenSSH": {
                "log_file": "OpenSSH/OpenSSH_2k.log",
                "log_format": "<Date> <Day> <Time> <Component> sshd\[<Pid>\]: <Content>",
                "regex": [r"(\d+\.){3}\d+", r"([\w-]+\.){2,}[\w-]+"],
                "st": 0.6,
                "depth": 5,
            },
            "OpenStack": {
                "log_file": "OpenStack/OpenStack_2k.log",
                "log_format": "<Logrecord> <Date> <Time> <Pid> <Level> <Component> \[<ADDR>\] <Content>",
                "regex": [r"((\d+\.){3}\d+,?)+", r"/.+?\s", r"\d+"],
                "st": 0.5,
                "depth": 5,
            },
            "Mac": {
                "log_file": "Mac/Mac_2k.log",
                "log_format": "<Month>  <Date> <Time> <User> <Component>\[<PID>\]( \(<Address>\))?: <Content>",
                "regex": [r"([\w-]+\.){2,}[\w-]+"],
                "st": 0.7,
                "depth": 6,
            },
        }
    else:
        print(input_dir)
        benchmark_settings = {
            "HDFS": {
                "log_file": "HDFS/HDFS_full.log",
                "log_format": "<Date> <Time> <Pid> <Level> <Component>: <Content>",
                "regex": [r"blk_-?\d+", r"(\d+\.){3}\d+(:\d+)?"],
                "st": 0.5,
                "depth": 4,
            },
            "Hadoop": {
                "log_file": "Hadoop/Hadoop_full.log",
                "log_format": "<Date> <Time> <Level> \[<Process>\] <Component>: <Content>",
                "regex": [r"(\d+\.){3}\d+"],
                "st": 0.5,
                "depth": 4,
            },
            "Spark": {
                "log_file": "Spark/Spark_full.log",
                "log_format": "<Date> <Time> <Level> <Component>: <Content>",
                "regex": [r"(\d+\.){3}\d+", r"\b[KGTM]?B\b", r"([\w-]+\.){2,}[\w-]+"],
                "st": 0.5,
                "depth": 4,
            },
            "Zookeeper": {
                "log_file": "Zookeeper/Zookeeper_full.log",
                "log_format": "<Date> <Time> - <Level>  \[<Node>:<Component>@<Id>\] - <Content>",
                "regex": [r"(/|)(\d+\.){3}\d+(:\d+)?"],
                "st": 0.5,
                "depth": 4,
            },
            "BGL": {
                "log_file": "BGL/BGL_full.log",
                "log_format": "<Label> <Timestamp> <Date> <Node> <Time> <NodeRepeat> <Type> <Component> <Level> <Content>",
                "regex": [r"core\.\d+"],
                "st": 0.5,
                "depth": 4,
            },
            "HPC": {
                "log_file": "HPC/HPC_full.log",
                "log_format": "<LogId> <Node> <Component> <State> <Time> <Flag> <Content>",
                "regex": [r"=\d+"],
                "st": 0.5,
                "depth": 4,
            },
            "Thunderbird": {
                "log_file": "Thunderbird/Thunderbird_full.log",
                "log_format": "<Label> <Timestamp> <Date> <User> <Month> <Day> <Time> <Location> <Component>(\[<PID>\])?: <Content>",
                "regex": [r"(\d+\.){3}\d+"],
                "st": 0.5,
                "depth": 4,
            },
            "Linux": {
                "log_file": "Linux/Linux_full.log",
                "log_format": "<Month> <Date> <Time> <Level> <Component>(\[<PID>\])?: <Content>",
                "regex": [r"(\d+\.){3}\d+", r"\d{2}:\d{2}:\d{2}"],
                "st": 0.39,
                "depth": 6,
            },
            "HealthApp": {
                "log_file": "HealthApp/HealthApp_full.log",
                "log_format": "<Time>\|<Component>\|<Pid>\|<Content>",
                "regex": [],
                "st": 0.2,
                "depth": 4,
            },
            "Apache": {
                "log_file": "Apache/Apache_full.log",
                "log_format": "\[<Time>\] \[<Level>\] <Content>",
                "regex": [r"(\d+\.){3}\d+"],
                "st": 0.5,
                "depth": 4,
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
                "st": 0.6,
                "depth": 3,
            },
            "OpenSSH": {
                "log_file": "OpenSSH/OpenSSH_full.log",
                "log_format": "<Date> <Day> <Time> <Component> sshd\[<Pid>\]: <Content>",
                "regex": [r"(\d+\.){3}\d+", r"([\w-]+\.){2,}[\w-]+"],
                "st": 0.6,
                "depth": 5,
            },
            "OpenStack": {
                "log_file": "OpenStack/OpenStack_full.log",
                "log_format": "<Logrecord> <Date> <Time> <Pid> <Level> <Component> \[<ADDR>\] <Content>",
                "regex": [r"((\d+\.){3}\d+,?)+", r"/.+?\s", r"\d+"],
                "st": 0.5,
                "depth": 5,
            },
        }

    # 确保路径结尾有斜杠
    if not input_dir.endswith(os.sep):
        input_dir += os.sep

    output_dir = "Drain_result/"  # The output directory of parsing results

    bechmark_result = []
    # 用于记录：{ "数据集名称": 耗时秒数 }
    dataset_timing = {}

    for dataset, setting in benchmark_settings.items():
        # if dataset not in test_set:
        #     print(f"Dataset {dataset} not in test set, skipped")
        #     continue
        print("\n=== Evaluation on %s ===" % dataset)
        if "dir_dedup" in input_dir:
            tmp = setting["log_file"].replace("2k",f"dedup_{data_scale}")
        elif "genius" in data_scale:
            tmp = os.path.basename(setting["log_file"]).replace("2k", f"new_dataset")
            print("Using new dataset for evaluation")
        else:
            tmp = setting["log_file"]


        indir = os.path.join(input_dir, os.path.dirname(tmp))
        log_file = os.path.basename(tmp)

        parser = LogParser(
            log_format=setting["log_format"],
            indir=indir,
            outdir=output_dir,
            rex=setting["regex"],
            depth=setting["depth"],
            st=setting["st"],
        )

        # --- parsing time ---
        start_time = time.time()

        parser.parse(log_file)  #start parsing

        parse_time = time.time()-start_time
        dataset_timing[dataset] = parse_time
        # --- parsing time ---

        if is_time == false :
            F1_measure, accuracy = evaluator.evaluate(
                groundtruth=os.path.join(indir, log_file + "_structured.csv"),
                parsedresult=os.path.join(output_dir, log_file + "_structured.csv"),
            )
            bechmark_result.append([dataset, F1_measure, accuracy])
        # 3. 释放内存 (放在当前循环的最末尾)
        print(f"Clearing memory for {dataset}...")
        del parser
        gc.collect()

    if is_time == false :
        print("\n=== Overall evaluation results ===")
        df_result = pd.DataFrame(bechmark_result, columns=["Dataset", "F1_measure", "Accuracy"])
        df_result.set_index("Dataset", inplace=True)
        print(df_result)
        df_result.to_csv("Drain_bechmark_result.csv", float_format="%.6f")
    return dataset_timing


if __name__ == "__main__":
    main()