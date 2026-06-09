import re
import pandas as pd

def runGetPTA():
    dataSet = ['HDFS', 'Hadoop', 'Spark', 'Zookeeper', 'BGL', 'HPC', 'Thunderbird', 'Windows', 'Linux', 'Android',
                'HealthApp', 'Apache', 'OpenSSH', 'OpenStack', 'Mac','Proxifier']
    precision_list = []  # 用于存储每个数据集的 precision 值

    for dataset in dataSet:
        standard = read_Standard(dataset)
        generated = read_Generated(dataset + '/' + dataset + '_new_template_with_idx.csv')
        precision = calculate_precision(generated, standard)
        print(dataset+f" Precision: {precision:.4f}")
        precision_list.append(precision)  # 将 precision 添加到列表中

    # 计算平均 Precision
    average_precision = sum(precision_list) / len(precision_list)
    print(f"Average Precision: {average_precision:.4f}")

def getSinglePTA(dataset):
    standard = read_Standard(dataset)
    generated = read_Generated(dataset + '/' + dataset + '_new_template_with_idx.csv')
    precision = calculate_precision(generated, standard)
    print(dataset+f" PTA: {precision:.4f}")
    return precision

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
    不要求数量一致，也不要求顺序一致。
    """
    if not standard_templates:
        return 0.0
    correct_count = 0
    for gen in generated_templates:
        gen = gen[0]
        ct=0
        for std in standard_templates:
            if is_match(gen, std):
                # print("匹配成功：", gen)
                # print(std)
                correct_count += 1
                # break
            else:
                ct+=1
        # if ct==len(standard_templates):
        #     print("没有匹配到标准模板:",gen)
    # print("标准模板数量：", len(standard_templates))
    # print("生成模板数量：", len(generated_templates))
    # print("匹配成功数量：", correct_count)
    return correct_count / len(generated_templates) if len(generated_templates) > 0 else 0


def read_Standard(dataset):
    df = pd.read_csv(f'../data/dir_2k/{dataset}/{dataset}_2k.log_templates_corrected.csv')
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
def read_Generated(file_name):
    # file_path = '../result/Brain/' + file_name
    file_path = '../result/' + file_name
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
                    result.append((line, None))  # 或者 append((line, 0))
        return result


# 示例用法
if __name__ == "__main__":
    # standard = read_Standard('Zookeeper')
    # print(standard)
    # generated = read_Generated('Zookeeper/Zookeeper_new_template_with_idx.csv')
    # print("------------------------分界线------------------------")
    # print(generated)
    # precision = calculate_precision(generated, standard)
    # print(f"Precision: {precision:.2f}")
    runGetPTA()
    # getSinglePTA('Spark')
