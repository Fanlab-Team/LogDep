import re
import os

def dataClean(sentences, filter, delimiter, dataset):
    clean_sentences = []

    for indexes, s in sentences:  # 拆分为编号列表和日志字符串
        # 只清洗日志字符串部分
        for rgex in filter:
            s = re.sub(rgex, '<*>', s)

        for de in delimiter:
            s = re.sub(de, '', s)
        if dataset == 'HealthApp':
            s = re.sub(':', ': ', s)
            s = re.sub('=', '= ', s)
            s = re.sub('\|', '| ', s)
        elif dataset == 'Android':
            s = re.sub('\(', '( ', s)
            s = re.sub('\)', ') ', s)
            s = re.sub(':', ': ', s)
            s = re.sub('=', '= ', s)
        elif dataset == 'HPC':
            s = re.sub('=', '= ', s)
            s = re.sub('-', '- ', s)
            s = re.sub(':', ': ', s)
        elif dataset == 'BGL':
            s = re.sub('=', '= ', s)
            s = re.sub(':', ': ', s)
            s = re.sub('\.\.', '.. ', s)
            s = re.sub('\(', '( ', s)
            s = re.sub('\)', ') ', s)
        # elif dataset == 'Hadoop':
        #     s = re.sub(':', ': ', s)
        #     s = re.sub('=', '= ', s)
        #     s = re.sub('\(', '( ', s)
        #     s = re.sub('\)', ') ', s)
        elif dataset == 'HDFS':
            s = re.sub(':', ': ', s)
        elif dataset == 'Linux':
            s = re.sub('=', '= ', s)
            s = re.sub(':', ': ', s)
        elif dataset == 'Spark':
            s = re.sub(':', ': ', s)
        elif dataset == 'Thunderbird':
            s = re.sub(':', ': ', s)
            s = re.sub('=', '= ', s)
        elif dataset == 'Windows':
            s = re.sub(':', ': ', s)
            s = re.sub('=', '= ', s)
            s = re.sub('\[', '[ ', s)
            s = re.sub(']', '] ', s)
        elif dataset == 'Zookeeper':
            s = re.sub(':', ': ', s)
            s = re.sub('=', '= ', s)
        elif dataset == 'OpenStack':
            s = re.sub('=', '= ', s)

        s = re.sub('=', '=  ', s)
        s = re.sub(',', ', ', s)
        s = re.sub(' +', ' ', s).strip()


        # 清洗完成后，将编号列表和清洗后的字符串重新组合成元组
        clean_sentences.append((indexes, s))

    clean_sentences = output_result(clean_sentences)

    return clean_sentences



def exclude_digits(string):
    '''
    exclude the digits-domain words from partial constant
    '''
    pattern = r'\d'
    digits = re.findall(pattern, string)
    if len(digits)==0:
        return False
    return len(digits)/len(string) >= 0.3

def exclude_slashes(string):
    '''
    exclude the strings with more than 3 slashes '/'
    '''
    pattern = r'/'
    slashes = re.findall(pattern, string)
    return len(slashes) >= 3


def output_result(template_set):
    template_result = []
    for indexes, template in template_set:
        words = template.split(" ")
        for i in range(len(words)):
            if '<*>' in words[i]:
                words[i] = '<*>'
            elif exclude_digits(words[i]):
                words[i] = '<*>'
            elif exclude_slashes(words[i]):
                words[i] = '<*>'
        new_template = " ".join(words)
        template_result.append((indexes, new_template))
    return template_result



def addSpaces(sentences):
    # 定义需要检查的符号
    symbols = ['=', ':', '：']

    # 遍历 sentences 列表中的每个语句
    for i in range(len(sentences)):
        sentence = sentences[i]

        # # 遍历每个符号
        # for symbol in symbols:
        #     # 查找符号在语句中的所有位置
        #     index = sentence.find(symbol)
        #     while index != -1:  # 如果找到符号
        #         # 检查符号右侧是否为空格
        #         if index + len(symbol) < len(sentence) and sentence[index + len(symbol)] != ' ':
        #             # 在符号后面插入一个空格
        #             sentence = sentence[:index + len(symbol)] + ' ' + sentence[index + len(symbol):]
        #
        #         # 更新索引，继续查找下一个相同符号
        #         index = sentence.find(symbol, index + len(symbol) + 1)

        sentence = ' '.join(sentence.split())

        # 更新 sentences 列表中的当前语句
        sentences[i] = sentence

    return sentences


def anchorVarTofreq(sentences):
    anchorVar_freq = {}
    min_freq = 1000000

    for i in range(len(sentences)):
        _, log_str = sentences[i]  # 拆分为编号列表和日志字符串
        words = re.findall(r'\S+=|\S+', log_str)  # 使用原始逻辑对字符串进行分词

        for j in range(len(words)):
            if words[j] == '<*>':
                continue
            idx = j
            anchorVar = '{' + str(len(words)) + '}{' + str(idx) + '}' + words[j]

            if anchorVar not in anchorVar_freq:
                anchorVar_freq[anchorVar] = [1, [i]]  # 初始化：出现次数、对应的句子索引列表
            else:
                anchorVar_freq[anchorVar][0] += 1         # 出现次数 +1
                anchorVar_freq[anchorVar][1].append(i)    # 添加当前句子索引

    # 排序找出最小频率项
    freq_list = sorted(anchorVar_freq.items(), key=lambda x: x[1][0], reverse=False)
    if freq_list:
        min_freq = freq_list[0][1][0]
    else:
        min_freq = 0

    return anchorVar_freq, min_freq




def deduplicate(data):         #去重且合并编号
    from collections import defaultdict

    mapping = defaultdict(list)

    # 根据字符串做 key，收集所有的 index list
    for indexes, content in data:
        mapping[content].extend(indexes)  # 合并编号列表

    # 构造去重后的结果
    result = [(indexes, content) for content, indexes in mapping.items()]
    return result



def torun(sentences, templates, templates_with_idx,threshold):
    tempSentences = [s for _, s in sentences]  # 只提取日志字符串部分
    tempSentences_with_idx = list(sentences)
    anchorVar_freq, min_freq = anchorVarTofreq(sentences)
    # print(sentences)

    for key in anchorVar_freq:
        if anchorVar_freq[key][0] == min_freq:
            for logSentence in anchorVar_freq[key][1]:
                _, log_str = sentences[logSentence]  # 只取日志字符串部分
                words = re.findall(r'\S+=|\S+', log_str)

                idx = int(key.split('{')[2].split('}')[0])
                if idx < len(words):
                    words[idx] = "<*>"
                    # 替换后重新组装回编号 + 新字符串
                    sentences[logSentence] = (sentences[logSentence][0], " ".join(words))


    new_sentences = []
    for i in range(len(sentences)):
        indexes, log_str = sentences[i]
        words = log_str.split(" ")
        wildcard_count = words.count("<*>")
        wildcard_ratio = wildcard_count / len(words) if words else 0
        # if len(words) <= 5:
        #     real_threshold = 0.45
        # else:
        #     real_threshold = threshold

        if wildcard_ratio <= threshold:
            new_sentences.append(sentences[i])
        else:
            templates.append(tempSentences[i])
            templates_with_idx.append(tempSentences_with_idx[i])

    # print(new_sentences)
    return new_sentences, templates, templates_with_idx

def to_csv(form,templates_with_idx,output_dir,dataset_name):
    # 1. 初始化两列空数据，长度与原始日志一致
    event_templates = [None] * len(form)
    event_ids = [None] * len(form)
    # 2. 遍历你迭代出来的结果库 templates_with_idx
    # 注意：templates_with_idx 的格式应为 [( [line_ids], "template_content" ), ...]
    for eid, (line_ids, template_str) in enumerate(templates_with_idx):
        for lid in line_ids:
            # 因为 lid 是从 1 开始的 LineId，对应 list 索引需减 1
            event_templates[lid - 1] = template_str
            event_ids[lid - 1] = f"E{eid}"
    # 3. 将这两列直接加到原始的 form 中
    form['EventId'] = event_ids
    form['EventTemplate'] = event_templates
    # 保存为结构化 CSV
    output_structured_file = os.path.join(output_dir, dataset_name + "_structured_result.csv")
    form.to_csv(output_structured_file, index=False)




