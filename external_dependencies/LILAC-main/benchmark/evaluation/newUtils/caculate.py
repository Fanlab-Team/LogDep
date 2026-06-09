import os
import pandas as pd
from benchmark.evaluation.utils.common import common_args
# from . import getPA
# from . import getPTA
# from . import getRTA

import getPA
import getPTA
import getRTA

def turn_to(folder_path):
    for filename in os.listdir(folder_path):
        if filename.endswith('.log_templates.csv'):
            input_file = os.path.join(folder_path, filename)
            output_file = os.path.join(folder_path, filename.replace('.log_templates.csv', '_extracted.csv'))

            df = pd.read_csv(input_file)

            # 提取第二列和第三列，并转换为字符串类型
            col1 = df.iloc[:, 1].astype(str)
            # 注意：如果添加了Occurrences列，第三列索引需要调整
            col_idx = 2
            # 添加边界检查防止索引越界
            if col_idx >= len(df.columns):
                raise IndexError(
                    f"Column index {col_idx} is out of bounds for DataFrame with {len(df.columns)} columns")

            col2 = df.iloc[:, col_idx].astype(str)

            # 合并两列内容，用空格连接，避免逗号
            combined = col1 + ' ' + col2

            # 去除每行开头和结尾的双引号
            combined = combined.str.strip('"')

            # 保存为纯文本文件（每行一条记录）
            with open(output_file, 'w', encoding='utf-8') as f:
                for line in combined:
                    f.write(f"{line}\n")

            print(f"已处理并保存：{output_file}")


def go_caculate(data_size='2k',write_flag = True):

    if data_size == '2k':
        datasets = [
            'HDFS', 'Hadoop', 'Spark', 'Zookeeper', 'BGL', 'HPC',
            'Thunderbird', 'Linux', 'HealthApp', 'Android', 'Windows',
            'Apache', 'OpenSSH', 'OpenStack', 'Mac', 'Proxifier'
        ]
    else:
        datasets = ['HDFS', 'Hadoop', 'Spark', 'Zookeeper', 'BGL', 'HPC', 'Thunderbird',
                    'Windows', 'Linux', 'Android', 'HealthApp', 'Apache', 'OpenSSH',
                    'OpenStack', 'Mac', 'Proxifier']

    # 存储所有结果
    results = []

    for dataset in datasets:
        try:
            # 获取评估指标
            pa = getPA.getSinglePA(dataset, data_size) if hasattr(getPA, 'getSinglePA') else None
            pta = getPTA.getSinglePTA(dataset, data_size) if hasattr(getPTA, 'getSinglePTA') else None
            rta = getRTA.getSingleRTA(dataset, data_size) if hasattr(getRTA, 'getSingleRTA') else None
            # 添加到结果列表
            results.append({
                'dataset': dataset,
                'PA': pa,
                'PTA': pta,
                'RTA': rta
            })
        except Exception as e:
            print(f"Error evaluating on {dataset}: {e}")
            results.append({
                'dataset': dataset,
                'PA': None,
                'PTA': None,
                'RTA': None
            })

    # 计算平均值
    valid_pa_values = [r['PA'] for r in results if r['PA'] is not None]
    valid_pta_values = [r['PTA'] for r in results if r['PTA'] is not None]
    valid_rta_values = [r['RTA'] for r in results if r['RTA'] is not None]

    avg_pa = sum(valid_pa_values) / len(valid_pa_values) if valid_pa_values else None
    avg_pta = sum(valid_pta_values) / len(valid_pta_values) if valid_pta_values else None
    avg_rta = sum(valid_rta_values) / len(valid_rta_values) if valid_rta_values else None

    # 添加平均值行
    results.append({
        'dataset': 'Average',
        'PA': round(avg_pa, 4) if avg_pa is not None else None,
        'PTA': round(avg_pta, 4) if avg_pta is not None else None,
        'RTA': round(avg_rta, 4) if avg_rta is not None else None
    })

    if write_flag:
         # 将结果写入CSV文件
        output_file = "../evaluation_results.csv"
        results_df = pd.DataFrame(results)
        results_df.to_csv(output_file, index=False)
        print(f"评估结果已保存到: {output_file}")

    # 打印结果概览
    print("\n评估结果概览:")
    print(results_df.to_string(index=False))

    return avg_pa, avg_pta, avg_rta


def go_caculate_single(data_size='2k'):
    args = common_args()
    data_type = data_size
    args.shot = 8  # 可以根据需要修改为 0, 1, 3, 5 等值
    args.example_size = 32  # 可以根据需要修改
    args.model = "deepseek-chat"  # 可以根据需要修改为其他模型名称
    args.oracle_template_correction = True
    #
    # 显式指定这三个参数
    args.shot = 8  # 可以根据需要修改为 0, 1, 3, 5 等值
    args.example_size = 32  # 可以根据需要修改
    args.model = "deepseek-chat"  # 可以根据需要修改为其他模型名称
    args.oracle_template_correction = True
    output_dir = f"../../result/result_LILAC_{data_type}_{args.shot}_{args.example_size}_{args.model}"
    turn_to(output_dir)
    avg_pa, avg_pta, avg_rta = go_caculate(data_size)
    return avg_pa, avg_pta, avg_rta



if __name__ == '__main__':

    args = common_args()
    data_type = "2k"
    args.shot = 8  # 可以根据需要修改为 0, 1, 3, 5 等值
    args.example_size = 32  # 可以根据需要修改
    args.model = "deepseek-chat"  # 可以根据需要修改为其他模型名称
    args.oracle_template_correction = True
    #
    # 显式指定这三个参数
    args.shot = 8  # 可以根据需要修改为 0, 1, 3, 5 等值
    args.example_size = 32  # 可以根据需要修改
    args.model = "deepseek-chat"  # 可以根据需要修改为其他模型名称
    args.oracle_template_correction = True
    output_dir = f"../../../result/result_LILAC_{data_type}_{args.shot}_{args.example_size}_{args.model}"
    turn_to(output_dir)
    go_caculate(data_type)