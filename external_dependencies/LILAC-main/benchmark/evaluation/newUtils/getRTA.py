import re
import pandas as pd
import os

from benchmark.evaluation.newUtils.getPA import base_dir

base_dir = os.path.dirname(os.path.abspath(__file__))

def runGetRTA():
    dataSet = ['HDFS', 'Hadoop', 'Spark', 'Zookeeper', 'BGL', 'HPC', 'Thunderbird', 'Windows','Linux','Android',
               'HealthApp', 'Apache', 'OpenSSH', 'OpenStack', 'Mac', 'Proxifier']
    recall_list = []  # 用于存储每个数据集的 recall 值

    for dataset in dataSet:
        standard = read_Standard(dataset)
        generated = read_Generated(dataset + '_2k_extracted.csv')
        recall = calculate_recall(generated, standard)
        print(dataset + f" RTA: {recall:.4f}")
        recall_list.append(recall)  # 将 recall 添加到列表中

    # 计算平均 RTA
    average_recall = sum(recall_list) / len(recall_list)
    print(f"Average RTA: {average_recall:.2f}")


def getSingleRTA(dataset,data_size='2k'):
    """
    计算单个数据集的 RTA。
    """
    standard = read_Standard(dataset)
    if data_size == '2k':
        generated = read_Generated(dataset + '_2k_extracted.csv', data_size)
    else:
        generated = read_Generated(dataset + f'_{data_size}_extracted.csv', data_size)
    recall = calculate_recall(generated, standard)
    print(dataset + f" RTA: {recall:.4f}")
    return round(recall, 4)


def tokenize(template):
    """
    分词函数，可根据实际需求替换为预处理中的分词方法。
    示例中使用简单的正则表达式分词。
    """
    words = re.findall(r'\S+=|\S+', template)
    return words


def message_split(message):
    """
    使用与PA_calculator.py中相同的分词方法
    """
    punc = "!\"#$%&'()+,-/:;=?@.[\]^_`{|}~"
    splitters = "\s\\" + "\\".join(punc)
    splitter_regex = re.compile("([{}]+)".format(splitters))
    tokens = re.split(splitter_regex, message)
    tokens = list(filter(lambda x: x != "", tokens))

    # 后处理标记
    tokens = post_process_tokens(tokens, punc)
    tokens = [
        token.strip()
        for token in tokens
        if token != "" and token != ' '
    ]
    tokens = [
        token
        for idx, token in enumerate(tokens)
        if not (token == "<*>" and idx > 0 and tokens[idx - 1] == "<*>")
    ]
    return tokens


def post_process_tokens(tokens, punc):
    """
    与PA_calculator.py中相同的后处理函数
    """
    excluded_str = ['=', '|', '(', ')']
    for i in range(len(tokens)):
        if tokens[i].find("<*>") != -1:
            tokens[i] = "<*>"
        else:
            new_str = ""
            for s in tokens[i]:
                if (s not in punc and s != ' ') or s in excluded_str:
                    new_str += s
            tokens[i] = new_str
    return tokens


def is_match(gen_template, std_template):
    """
    使用改进的分词方法判断两个模板是否匹配
    """
    gen_tokens = message_split(gen_template)
    std_tokens = message_split(std_template)

    return gen_tokens == std_tokens

def calculate_recall(generated_templates, standard_templates):
    """
    计算 Recall-TA (RTA)：能匹配到标准模板的生成模板数量 / 标准模板总数。
    这里我们统计的是：对于每一个标准模板，只要有一个生成的模板与之完全匹配，就算该标准模板被“召回”。
    """
    if not standard_templates:
        return 0.0

    # 提取生成模板的字符串部分（去除计数）
    generated_strings = [tpl[0] for tpl in generated_templates]

    correct_count = 0
    for std in standard_templates:
        # 检查当前这个标准模板是否能被任何一个生成的模板匹配
        matched = False
        for gen_str in generated_strings:
            if is_match(gen_str, std):
                matched = True
                break  # 找到一个匹配即可，跳出内层循环

        if matched:
            correct_count += 1
        else:
            a =1
            # print("没有生成的模板匹配标准模板:", std)

    # print("标准模板数量：", len(standard_templates))
    # print("生成模板数量：", len(generated_strings))
    # print("被正确召回的标准模板数量：", correct_count)

    # RTA = 正确识别的模板数 / 标准模板总数
    return correct_count / len(standard_templates)


def read_Standard(dataset):
    df = pd.read_csv(os.path.join(base_dir,f'../../../2k_dataset/{dataset}/{dataset}_2k.log_templates_corrected.csv'))
    return df['EventTemplate'].tolist()


def read_Generated(file_name,data_size='2k'):
    file_path = os.path.join(base_dir,f'../../../result/result_LILAC_{data_size}_0_0_deepseek-chat/{file_name}')
    # file_path = '../result/Brain/' + file_name

    if 'txt' in file_name:
        with open(file_path, 'r', encoding='utf-8') as f:
            return [(line.strip(), None) for line in f if line.strip()]

    elif 'csv' in file_name:
        result = []
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                parts = line.rsplit(' ', 1)  # 只从右侧分割一次
                if len(parts) == 2 and parts[1].isdigit():
                    template = parts[0]
                    count = int(parts[1])
                    result.append((template, count))
                else:
                    result.append((line, None))  # 如果没有计数，则设为None
        return result


def turn_to(logparser_name):
    folder_path = logparser_name+'_result'
    for filename in os.listdir(folder_path):
        if filename.endswith('.log_templates.csv'):
            input_file = os.path.join(folder_path, filename)
            output_file = os.path.join(folder_path, filename.replace('.log_templates.csv', '_extracted.csv'))

            df = pd.read_csv(input_file)

            # 提取第二列和第三列，并转换为字符串类型
            col1 = df.iloc[:, 1].astype(str)
            col2 = df.iloc[:, 2].astype(str)

            # 合并两列内容，用空格连接，避免逗号
            combined = col1 + ' ' + col2

            # 去除每行开头和结尾的双引号
            combined = combined.str.strip('"')

            # 保存为纯文本文件（每行一条记录）
            with open(output_file, 'w', encoding='utf-8') as f:
                for line in combined:
                    f.write(f"{line}\n")

            print(f"已处理并保存：{output_file}")

# 示例用法
if __name__ == "__main__":
    # 单独计算一个数据集的 RTA
    # turn_to('MoLFI')
    # getSingleRTA('Apache')

    # 计算多个数据集并求平均
    runGetRTA()