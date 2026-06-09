import re
import pandas as pd
def calculate_precision(generated_templates, dataset):
    standard_templates = read_Standard(dataset)
    # 构建 {tuple of indices: template_string} 的映射，并对所有索引减 1
    standard_groups = standard_templates.groupby(standard_templates).apply(
        lambda x: tuple(i + 1 for i in x.index.tolist())
    )
    standard_index_sets = set(standard_groups.values)
    count = 0
    for index, content in generated_templates:
        converted_index = tuple(index)  # 确保是 tuple 类型
        if converted_index in standard_index_sets:
            count += len(index)

    precision = count / len(standard_templates)
    return precision


def read_Standard(dataset):
    df = pd.read_csv(f'../data/dir_2k/{dataset}/{dataset}_2k.log_structured_corrected.csv')
    return df['EventTemplate']





