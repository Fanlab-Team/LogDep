"""
This file is part of TA-Eval-Rep.
Copyright (C) 2022 University of Luxembourg
    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, version 3 of the License.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.
    You should have received a copy of the GNU General Public License
    along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""

import sys
import os
import csv
from benchmark.evaluation.newUtils import caculate

sys.path.append('../')

from benchmark.logparser.LILAC import LogParser
from benchmark.evaluation.settings import benchmark_settings
from benchmark.evaluation.utils.common import common_args
from benchmark.evaluation.utils.evaluator_main import evaluator, prepare_results
from benchmark.evaluation.utils.postprocess import post_average


datasets_full = [
    "Proxifier",
    "Linux",
    "Apache",
    "Zookeeper",
    "Hadoop",
    "HealthApp",
    "OpenStack",
    "HPC",
    "Mac",
    "OpenSSH",
    "Spark",
    "Thunderbird",
    "BGL",
    "HDFS",
    "Windows",
    "Android"
]

datasets_2k = [
    'HDFS', 'Hadoop', 'Spark', 'Zookeeper', 'BGL', 'HPC', 'Thunderbird', 'Windows', 'Linux', 'Android',
    'HealthApp', 'Apache', 'OpenSSH', 'OpenStack', 'Mac','Proxifier'
]
# datasets_full = ['Thunderbird','BGL','Spark','HDFS']
# datasets_2k = ['Thunderbird','BGL','Spark','HDFS']
# 按零样本数
# datasets_2k = ['HDFS','Spark', 'Zookeeper', 'HPC',
#             'Windows', 'Apache', 'OpenSSH',
#             'OpenStack', 'Proxifier']


# # 按零样本数
# datasets_full = ['HDFS','Spark', 'Zookeeper', 'HPC',
#             'Windows', 'Apache', 'OpenSSH',
#             'OpenStack', 'Proxifier']
# 按零样本过半
# datasets_2k = ['HDFS', 'Hadoop', 'Spark', 'Zookeeper', 'Thunderbird',
#             'Windows', 'Apache', 'OpenSSH',
#             'OpenStack', 'Proxifier']
# datasets_full = ['HDFS', 'Hadoop', 'Spark', 'Zookeeper', 'Thunderbird',
#             'Windows', 'Apache', 'OpenSSH',
#             'OpenStack', 'Proxifier']

def test_time(data_type="2k"):
    # 获取原始参数
    args = common_args()

    # 显式指定这三个参数
    args.shot = 0 # 可以根据需要修改为 0, 1, 3, 5 等值
    args.example_size = 0  # 可以根据需要修改
    args.model = "deepseek-chat"  # 可以根据需要修改为其他模型名称
    args.oracle_template_correction = True


    input_dir = f"../../{data_type}_dataset/"
    output_dir = f"../../result/result_LILAC_{data_type}_{args.shot}_{args.example_size}_{args.model}"
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    result_file = prepare_results(
        output_dir=output_dir,
        otc=args.oracle_template_correction,
        complex=args.complex,
        frequent=args.frequent
    )

    if args.full_data:
        datasets = datasets_full
    else:
        datasets = datasets_2k

    # --- 修改点 1: 初始化用于存储耗时的列表 ---
    parsing_stats = []

    for dataset in datasets:
        setting = benchmark_settings[dataset]
        if data_type != "2k":
            log_file = setting['log_file'].replace("_2k", "_full")
        else:
            log_file = setting['log_file'].replace("_2k", f"_{data_type}")
        indir = os.path.join(input_dir, os.path.dirname(log_file))
        if os.path.exists(os.path.join(output_dir, f"{dataset}_{data_type}.log_structured.csv")):
            parser = None
            print("parseing result exist.")
        else:
            parser = LogParser
        # run evaluator for a dataset
        parse_time = evaluator(
            dataset=dataset,
            input_dir=input_dir,
            output_dir=output_dir,
            log_file=log_file,
            LogParser=parser,
            param_dict={
                # 'log_format': setting['log_format'], 'indir': indir, 'outdir': output_dir, 'rex': setting['regex'],
                'log_format': setting['log_format'], 'indir': indir, 'outdir': output_dir, 'rex': [],
                'data_type': data_type, 'shot': args.shot, 'example_size': args.example_size,
                'model': args.model, 'selection_method': args.selection_method,
            },
            otc=args.oracle_template_correction,
            complex=args.complex,
            frequent=args.frequent,
            result_file=result_file,
        )  # it internally saves the results into a summary file

        # --- 修改点 2: 记录当前数据集的解析时间 ---
        # 假设 evaluator 在跳过解析时可能返回 None 或 0，这里记录实际值
        parsing_stats.append({
            "dataset": dataset,
            "parse_time": parse_time if parse_time is not None else "skipped/0"
        })

    # --- 修改点 3: 将统计结果写入 CSV 文件 ---
    stats_file_path = os.path.join(output_dir, "parsing_time_stats.csv")
    with open(stats_file_path, mode='w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=["dataset", "parse_time"])
        writer.writeheader()
        writer.writerows(parsing_stats)
    print(f"Parsing times saved to: {stats_file_path}")

    metric_file = os.path.join(output_dir, result_file)
    post_average(metric_file,
                 f"LILAC_{data_type}_complex={args.complex}_frequent={args.frequent}_{args.shot}_{args.example_size}_{args.model}",
                 args.complex, args.frequent)

#要是出错了就把run_evaluation方法中的代码所有都复制到主函数里
def run_evaluation():
    # 获取原始参数
    args = common_args()

    # 显式指定这三个参数
    args.shot = 8
    args.example_size = 32
    args.model = "deepseek-chat"  # 可以根据需要修改为其他模型名称
    args.oracle_template_correction = True

    data_type = "2k"

    input_dir = f"../../{data_type}_dataset/"
    output_dir = f"../../result/result_LILAC_{data_type}_{args.shot}_{args.example_size}_{args.model}"
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    result_file = prepare_results(
        output_dir=output_dir,
        otc=args.oracle_template_correction,
        complex=args.complex,
        frequent=args.frequent
    )

    if args.full_data:
        datasets = datasets_full
    else:
        datasets = datasets_2k

    # --- 修改点 1: 初始化用于存储耗时的列表 ---
    parsing_stats = []

    for dataset in datasets:
        setting = benchmark_settings[dataset]
        if data_type == "deduplicated":
            log_file = setting['log_file'].replace("_2k", "_deduplicated")
        elif data_type != "2k":
            log_file = setting['log_file'].replace("_2k", "_full")
        else:
            log_file = setting['log_file'].replace("_2k", f"_{data_type}")
        indir = os.path.join(input_dir, os.path.dirname(log_file))
        if os.path.exists(os.path.join(output_dir, f"{dataset}_{data_type}.log_structured.csv")):
            parser = None
            print("parseing result exist.")
        else:
            parser = LogParser
        # run evaluator for a dataset
        parse_time = evaluator(
            dataset=dataset,
            input_dir=input_dir,
            output_dir=output_dir,
            log_file=log_file,
            LogParser=parser,
            param_dict={
                # 'log_format': setting['log_format'], 'indir': indir, 'outdir': output_dir, 'rex': setting['regex'],
                'log_format': setting['log_format'], 'indir': indir, 'outdir': output_dir, 'rex': [],
                'data_type': data_type, 'shot': args.shot, 'example_size': args.example_size,
                'model': args.model, 'selection_method': args.selection_method,
            },
            otc=args.oracle_template_correction,
            complex=args.complex,
            frequent=args.frequent,
            result_file=result_file,
        )  # it internally saves the results into a summary file

        # --- 修改点 2: 记录当前数据集的解析时间 ---
        # 假设 evaluator 在跳过解析时可能返回 None 或 0，这里记录实际值
        parsing_stats.append({
            "dataset": dataset,
            "parse_time": parse_time if parse_time is not None else "skipped/0"
        })

    # --- 修改点 3: 将统计结果写入 CSV 文件 ---
    stats_file_path = os.path.join(output_dir, "parsing_time_stats.csv")
    with open(stats_file_path, mode='w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=["dataset", "parse_time"])
        writer.writeheader()
        writer.writerows(parsing_stats)
    print(f"Parsing times saved to: {stats_file_path}")

    metric_file = os.path.join(output_dir, result_file)
    post_average(metric_file,
                 f"LILAC_{data_type}_complex={args.complex}_frequent={args.frequent}_{args.shot}_{args.example_size}_{args.model}",
                 args.complex, args.frequent)


def time_evaluation(data_type="2k"):
    # 获取原始参数
    args = common_args()

    # 显式指定这三个参数
    args.shot = 0  # 可以根据需要修改为 0, 1, 3, 5 等值
    args.example_size = 0  # 可以根据需要修改
    args.model = "deepseek-chat"  # 可以根据需要修改为其他模型名称
    args.oracle_template_correction = True

    input_dir = f"../../{data_type}_dataset/"
    output_dir = f"../../result/result_LILAC_{data_type}_{args.shot}_{args.example_size}_{args.model}"
    time_output_dir = f"../../result/time/{data_type}"

    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    result_file = prepare_results(
        output_dir=output_dir,
        otc=args.oracle_template_correction,
        complex=args.complex,
        frequent=args.frequent
    )

    if args.full_data:
        datasets = datasets_full
    else:
        datasets = datasets_2k

    # --- 修改点 1: 初始化用于存储耗时的列表 ---
    parsing_stats = []

    for dataset in datasets:
        setting = benchmark_settings[dataset]
        log_file = setting['log_file'].replace("_2k", f"_{data_type}")
        indir = os.path.join(input_dir, os.path.dirname(log_file))
        if os.path.exists(os.path.join(output_dir, f"{dataset}_{data_type}.log_structured.csv")):
            parser = None
            print("parseing result exist.")
        else:
            parser = LogParser
        # run evaluator for a dataset
        parse_time = evaluator(
            dataset=dataset,
            input_dir=input_dir,
            output_dir=output_dir,
            log_file=log_file,
            LogParser=parser,
            param_dict={
                # 'log_format': setting['log_format'], 'indir': indir, 'outdir': output_dir, 'rex': setting['regex'],
                'log_format': setting['log_format'], 'indir': indir, 'outdir': output_dir, 'rex': [],
                'data_type': data_type, 'shot': args.shot, 'example_size': args.example_size,
                'model': args.model, 'selection_method': args.selection_method,
            },
            otc=args.oracle_template_correction,
            complex=args.complex,
            frequent=args.frequent,
            result_file=result_file,
        )  # it internally saves the results into a summary file

        # --- 修改点 2: 记录当前数据集的解析时间 ---
        # 假设 evaluator 在跳过解析时可能返回 None 或 0，这里记录实际值
        parsing_stats.append({
            "dataset": dataset,
            "parse_time": parse_time if parse_time is not None else "skipped/0"
        })

    # --- 修改点 3: 将统计结果写入 CSV 文件 ---
    stats_file_path = os.path.join(time_output_dir, "parsing_time_stats.csv")
    with open(stats_file_path, mode='w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=["dataset", "parse_time"])
        writer.writeheader()
        writer.writerows(parsing_stats)
    print(f"Parsing times saved to: {stats_file_path}")

    metric_file = os.path.join(output_dir, result_file)
    post_average(metric_file,
                 f"LILAC_{data_type}_complex={args.complex}_frequent={args.frequent}_{args.shot}_{args.example_size}_{args.model}",
                 args.complex, args.frequent)


def test_diversity():

    dedup_scale= [1,2,3,4,5,6,7,8]
    # --- 初始化汇总结果列表和总累加器 ---
    diversity_results_summary = []
    end_sum = {'PA': 0.0, 'PTA': 0.0, 'RTA': 0.0}
    end_count = 0

    # 结果汇总输出目录
    summary_dir = '../../result/deduplicated_summary'
    if not os.path.exists(summary_dir):
        os.makedirs(summary_dir)
    summary_file = os.path.join(summary_dir, 'diversity_result.csv')

    for scale in dedup_scale:

        # 获取原始参数
        args = common_args()

        # 显式指定这三个参数
        args.shot = 0  # 可以根据需要修改为 0, 1, 3, 5 等值
        args.example_size = 0  # 可以根据需要修改
        args.model = "deepseek-chat"  # 可以根据需要修改为其他模型名称
        args.oracle_template_correction = True

        data_type = f"dedup_{scale}"

        input_dir = f"../../deduplicated_data/dir_{data_type}/"
        output_dir = f"../../result/deuplicated/result_LILAC_{data_type}_{args.shot}_{args.example_size}_{args.model}"
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

        result_file = prepare_results(
            output_dir=output_dir,
            otc=args.oracle_template_correction,
            complex=args.complex,
            frequent=args.frequent
        )

        if args.full_data:
            datasets = datasets_full
        else:
            datasets = datasets_2k

        # --- 修改点 1: 初始化用于存储耗时的列表 ---
        parsing_stats = []

        for dataset in datasets:
            setting = benchmark_settings[dataset]

            log_file = setting['log_file'].replace("_2k", f"_{data_type}")

            indir = os.path.join(input_dir, os.path.dirname(log_file))
            if os.path.exists(os.path.join(output_dir, f"{dataset}_{data_type}.log_structured.csv")):
                parser = None
                print("parseing result exist.")
            else:
                parser = LogParser
            # run evaluator for a dataset
            parse_time = evaluator(
                dataset=dataset,
                input_dir=input_dir,
                output_dir=output_dir,
                log_file=log_file,
                LogParser=parser,
                param_dict={
                    # 'log_format': setting['log_format'], 'indir': indir, 'outdir': output_dir, 'rex': setting['regex'],
                    'log_format': setting['log_format'], 'indir': indir, 'outdir': output_dir, 'rex': [],
                    'data_type': data_type, 'shot': args.shot, 'example_size': args.example_size,
                    'model': args.model, 'selection_method': args.selection_method,
                },
                otc=args.oracle_template_correction,
                complex=args.complex,
                frequent=args.frequent,
                result_file=result_file,
            )  # it internally saves the results into a summary file

            # --- 修改点 2: 记录当前数据集的解析时间 ---
            # 假设 evaluator 在跳过解析时可能返回 None 或 0，这里记录实际值
            parsing_stats.append({
                "dataset": dataset,
                "parse_time": parse_time if parse_time is not None else "skipped/0"
            })

        # --- 修改点 3: 将统计结果写入 CSV 文件 ---
        stats_file_path = os.path.join(output_dir, "parsing_time_stats.csv")
        with open(stats_file_path, mode='w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=["dataset", "parse_time"])
            writer.writeheader()
            writer.writerows(parsing_stats)
        print(f"Parsing times saved to: {stats_file_path}")

        metric_file = os.path.join(output_dir, result_file)
        post_average(metric_file,
                     f"LILAC_{data_type}_complex={args.complex}_frequent={args.frequent}_{args.shot}_{args.example_size}_{args.model}",
                     args.complex, args.frequent)
        avg_pa, avg_pta, avg_rta = caculate.go_caculate_single(data_type)
        # 记录到汇总列表（用于写入 CSV）
        current_row = {
            'dedup_scale': scale,
            'PA': f"{avg_pa:.4f}",
            'PTA': f"{avg_pta:.4f}",
            'RTA': f"{avg_rta:.4f}"
        }
        diversity_results_summary.append(current_row)

        # 累加用于计算最后的 AVERAGE 行
        end_sum['PA'] += avg_pa
        end_sum['PTA'] += avg_pta
        end_sum['RTA'] += avg_rta
        end_count += 1

        # --- 关键修改 3: 在循环结束后，将所有结果写入汇总 CSV ---
    with open(summary_file, 'w', newline='', encoding='utf-8') as csvfile:
        fieldnames = ['dedup_scale', 'PA', 'PTA', 'RTA']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()

        # 写入各梯度的结果
        writer.writerows(diversity_results_summary)

        # 写入总平均值行
        if end_count > 0:
            avg_row = {
                'dedup_scale': 'AVERAGE',
                'PA': f"{(end_sum['PA'] / end_count):.4f}",
                'PTA': f"{(end_sum['PTA'] / end_count):.4f}",
                'RTA': f"{(end_sum['RTA'] / end_count):.4f}"
            }
            writer.writerow(avg_row)

    print(f"\n所有梯度测试完毕！汇总结果已保存至: {summary_file}")



if __name__ == "__main__":
    # data_scale=['10k']
    # for data_type in data_scale:
    #     test_time(data_type)

    run_evaluation()
    # test_diversity()