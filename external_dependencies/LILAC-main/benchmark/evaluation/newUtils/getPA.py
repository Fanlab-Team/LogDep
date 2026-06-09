import re
import pandas as pd
import os

base_dir = os.path.dirname(os.path.abspath(__file__))

def runGetPA():
    dataSet = ['HDFS', 'Hadoop', 'Spark', 'Zookeeper', 'BGL', 'HPC', 'Thunderbird', 'Linux',
                'HealthApp', 'Apache', 'OpenSSH', 'OpenStack', 'Mac','Proxifier']
    precision_list = []  # 用于存储每个数据集的 precision 值

    for dataset in dataSet:
        standard = read_Standard(dataset)
        generated = read_Generated(dataset + '_2k_extracted.csv')
        precision = calculate_precision(generated, standard)
        print(dataset+f" Precision: {precision:.4f}")
        precision_list.append(precision)  # 将 precision 添加到列表中

    # 计算平均 Precision
    average_precision = sum(precision_list) / len(precision_list)
    print(f"Average Precision: {average_precision:.4f}")

def getSinglePA(dataset,data_size='2k'):
    print(dataset)
    standard = read_Standard(dataset)
    # print(standard)
    if data_size == '2k':
        generated = read_Generated(dataset + '_2k_extracted.csv', data_size)
    else:
        generated = read_Generated(dataset + f'_{data_size}_extracted.csv', data_size)
    return calculate_precision(generated, standard)

def tokenize(template):
    """
    分词函数，可根据实际需求替换为预处理中的分词方法。
    示例中使用简单的空格分词。
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

def calculate_precision(generated_templates, standard_templates):
    """
    计算准确率：生成模板中能匹配到标准模板的数量 / 标准模板总数。
    输入：
        generated_templates: 列表，每个元素为 (模板字符串, 数字)，如 ("login success", 3)
        standard_templates: 列表，每个元素为 模板字符串，如 "Accepted password..."
    匹配逻辑只使用模板字符串部分，忽略数字字段。
    """
    if not standard_templates:
        return 0.0
    correct_count = 0
    total_count = 0
    for gen_tuple in generated_templates:
        gen_template = gen_tuple[0]  # 提取模板部分
        count = gen_tuple[1]
        total_count += count
        for std_template in standard_templates:
            if is_match(gen_template, std_template):
                # print("匹配成功：", gen_template)
                # print(std_template)
                correct_count += count
                break  # 一旦匹配成功就跳出循环，避免重复计数
            # else:
            #     print("匹配失败：", gen_template)
            #     print(std_template)

    precision = correct_count / total_count if total_count else 0.0

    # print("生成模板数量：", len(generated_templates))
    # print("匹配总数：", total_count)
    # print("匹配成功数量：", correct_count)

    return precision


def read_Standard(dataset):

    df = pd.read_csv(os.path.join(base_dir,f'../../../2k_dataset/{dataset}/{dataset}_2k.log_templates_corrected.csv'))
    return df['EventTemplate'].tolist()

# def read_Generated(file_name):
#     file_path = '../result/'+file_name
#     if 'txt' in file_name:
#         with open(file_path, 'r', encoding='utf-8') as f:
#             templates = [line.strip() for line in f if line.strip()]
#     elif 'csv' in file_name:
#         df = pd.read_csv(file_path,header=None)
#         templates = [
#             ' '.join(template.rsplit(' ', 1)[:-1]) if ' ' in template else ''
#             for template in df[0].tolist()
#         ]
#     return templates
def read_Generated(file_name,data_size='2k'):
    file_path = os.path.join(base_dir,f'../../../result/result_LILAC_{data_size}_0_0_deepseek-chat/{file_name}')

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
                    result.append((line, None))  # 或者 append((line, 0))
        return result





# 示例用法
if __name__ == "__main__":
    PA = getSinglePA('Proxifier')
    print(PA)
    # runGetPA()


