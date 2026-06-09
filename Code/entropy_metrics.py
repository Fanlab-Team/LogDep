import datetime


import brain_parser as Ba
import csv
import re
import nltk
import pandas as pd


# ============================================================
# 鍦ㄨ繖閲屼慨鏀瑰弬鏁?
# ============================================================
DATA_DIR = 'dir_dedup_2'          # 鍙€? 'raw_2k', 'dir_dedup_1', 'dir_dedup_2'
DATA_SETS = ['HDFS', 'Hadoop', 'Spark', 'Zookeeper', 'BGL', 'HPC', 'Thunderbird',
             'Windows', 'Linux', 'Android', 'HealthApp', 'Apache', 'OpenSSH', 'OpenStack', 'Mac', 'Proxifier']
# DATA_SETS = ['BGL', 'HDFS', 'Spark', 'Thunderbird']  # 蹇€熸祴璇曠敤
# ============================================================


def main():
    results = []

    for dataset in DATA_SETS:
        entropy = calculate_diversity(dataset, DATA_DIR)

        results.append({
            'Dataset': dataset,
            'Diversity_Score': entropy,
        })

    df = pd.DataFrame(results)
    output_file = f'diversity_{DATA_DIR}.csv'
    df.to_csv(output_file, index=False, encoding='utf-8-sig')

    avg = df['Diversity_Score'].mean()
    print(f"\n[Done] 缁撴灉宸蹭繚瀛樿嚦 {output_file}")
    print(f"AVERAGE Diversity Score: {avg:.4f}")


def calculate_diversity(dataset_name, data_dir='raw_2k'):
    # Calculate the dataset diversity score using Brain-based grouping.
    print(f"Processing: {dataset_name} (from {data_dir})...")

    if data_dir == 'raw_2k':
        log_file = dataset_name + '_2k.log'
    elif data_dir == 'dir_dedup_1':
        log_file = dataset_name + '_dedup_1.log'
    elif data_dir == 'dir_dedup_2':
        log_file = dataset_name + '_dedup_2.log'
    else:
        log_file = dataset_name + '_full.log'

    input_dir = f'../data/{data_dir}/{dataset_name}/'
    diversity_score = E_dataset(input_dir, log_file, dataset_name)

    print(f'  {dataset_name}: Diversity Score = {diversity_score:.4f}')
    return diversity_score



def load_log_to_list(file_path):
    try:
        with open(file_path, 'r') as file:  # 鎵撳紑鏂囦欢
            log_lines = file.readlines()  # 璇诲彇鎵€鏈夎
        return [line.strip() for line in log_lines]  # 鍘婚櫎姣忚鐨勫墠鍚庣┖鐧藉瓧绗︼紝骞惰繑鍥炲垪琛?
    except FileNotFoundError:
        print(f"鎵句笉鍒版枃浠? {file_path}")
        return []
    except Exception as e:
        print(f"璇诲彇鏂囦欢鏃跺彂鐢熼敊璇? {e}")
        return []


def E_dataset(input_dir, log_file, dataset_name):
    # input_dir = '../Dataset/'
    # new_input_dir = '../new_dataset/'
    # dataset_name = 'OpenSSH'
    # log_file = dataset_name + '_2k.log'

    # Benchmark log format settings.


    benchmark_settings = {

        'Proxifier': {
            'log_file': log_file,
            'log_format': r'\[<Time>\] <Program> - <Content>',
            'regex': [r'<\d+\ssec', r'([\w-]+\.)+[\w-]+(:\d+)?', r'\d{2}:\d{2}(:\d{2})*', r'[KGTM]B'],
            'delimiter': [r'\(.*?\)'],
            'tag': 0,
            'theshold': 3
        },
        'HDFS': {
            'log_file': log_file,
            'log_format': '<Date> <Time> <Pid> <Level> <Component>: <Content>',
            'regex': [r'blk_-?\d+', r'(\d+\.){3}\d+(:\d+)?'],
            'delimiter': [''],
            'tag': 0,
            'theshold': 2
        },

        'Hadoop': {
            'log_file': log_file,
            'log_format': r'<Date> <Time> <Level> \[<Process>\] <Component>: <Content>',
            'regex': [r'(\d+\.){3}\d+'],
            'delimiter': [],
            'tag': 1,
            'theshold': 6
        },

        'Spark': {
            'log_file': log_file,
            'log_format': '<Date> <Time> <Level> <Component>: <Content>',
            'regex': [r'(\d+\.){3}\d+', r'\b[KGTM]?B\b', r'([\w-]+\.){2,}[\w-]+'],
            'delimiter': [],
            'tag': 0,
            'theshold': 4
        },

        'Zookeeper': {
            'log_file': log_file,
            'log_format': r'<Date> <Time> - <Level>  \[<Node>:<Component>@<Id>\] - <Content>',
            'regex': [r'(/|)(\d+\.){3}\d+(:\d+)?'],
            'delimiter': [],
            'tag': 1,
            'theshold': 3
        },

        'BGL': {
            'log_file': log_file,
            'log_format': '<Label> <Timestamp> <Date> <Node> <Time> <NodeRepeat> <Type> <Component> <Level> <Content>',
            'regex': [r'core\.\d+'],
            'delimiter': [],
            'tag': 0,
            'theshold': 6
        },

        'HPC': {
            'log_file': log_file,
            'log_format': '<LogId> <Node> <Component> <State> <Time> <Flag> <Content>',
            'regex': [],
            'delimiter': [],
            'tag': 0,
            'theshold': 5
        },

        'Thunderbird': {
            'log_file': log_file,
            'log_format': r'<Label> <Timestamp> <Date> <User> <Month> <Day> <Time> <Location> <Component>(\[<PID>\])?: <Content>',
            'regex': [r'(\d+\.){3}\d+'],
            'delimiter': [],
            'tag': 0,
            'theshold': 3
        },

        'Windows': {
            'log_file': log_file,
            'log_format': '<Date> <Time>, <Level>                  <Component>    <Content>',
            'regex': [r'0x.*?\s'],
            'delimiter': [],
            'tag': 0,
            'theshold': 3
        },

        'Linux': {
            'log_file': log_file,
            'log_format': r'<Month> <Date> <Time> <Level> <Component>(\[<PID>\])?: <Content>',
            'regex': [r'(\d+\.){3}\d+', r'\d{2}:\d{2}:\d{2}', r'J([a-z]{2})'],
            'delimiter': [r''],
            'tag': 0,
            'theshold': 4
        },

        'Android': {
            'log_file': log_file,
            'log_format': '<Date> <Time>  <Pid>  <Tid> <Level> <Component>: <Content>',
            'regex': [r'(/[\w-]+)+', r'([\w-]+\.){2,}[\w-]+',
                      r'\b(\-?\+?\d+)\b|\b0[Xx][a-fA-F\d]+\b|\b[a-fA-F\d]{4,}\b'],
            'delimiter': [r''],
            'tag': 0,
            'theshold': 5
        },

        'HealthApp': {
            'log_file': log_file,
            'log_format': r'<Time>\|<Component>\|<Pid>\|<Content>',
            'regex': [],
            'delimiter': [r''],
            'tag': 0,
            'theshold': 4
        },

        'Apache': {
            'log_file': log_file,
            'log_format': r'\[<Time>\] \[<Level>\] <Content>',
            'regex': [r'(\d+\.){3}\d+'],
            'delimiter': [],
            'tag': 0,
            'theshold': 4
        },

        'OpenSSH': {
            'log_file': log_file,
            'log_format': r'<Date> <Day> <Time> <Component> sshd\[<Pid>\]: <Content>',
            'regex': [r'(\d+\.){3}\d+', r'([\w-]+\.){2,}[\w-]+'],
            'delimiter': [],
            'tag': 0,
            'theshold': 6
        },

        'OpenStack': {
            'log_file': log_file,
            'log_format': r'<Logrecord> <Date> <Time> <Pid> <Level> <Component> \[<ADDR>\] <Content>',
            'regex': [r'((\d+\.){3}\d+,?)+', r'/.+?\s ', r'\d+'],
            'delimiter': [],
            'tag': 0,
            'theshold': 6,
        },

        'Mac': {
            'log_file': log_file,
            'log_format': r'<Month>  <Date> <Time> <User> <Component>\[<PID>\]( \(<Address>\))?: <Content>',
            'regex': [r'([\w-]+\.){2,}[\w-]+'],
            'delimiter': [],
            'tag': 0,
            'theshold': 5
        },
    }

    for dataset, setting in benchmark_settings.items():

        if dataset == dataset_name:
            starttime = datetime.datetime.now()
            sentences = load_log_to_list(input_dir + log_file)

            # 鍏堥澶勭悊锛屽啀浼犵粰 Brain 鍜?log_entropy_E锛屼繚璇佷袱鑰呯敤鍚屼竴濂楀彞瀛?
            preprocessed = get_united_sentences(sentences, dataset, setting['regex'])

            GA = Ba.parse_E(preprocessed, setting['regex'], dataset, setting['theshold'], setting['delimiter'],
                            setting['tag'], starttime, efficiency=False)

            diversity = log_entropy_E(preprocessed, dataset)

            return diversity


#-----------------------------------------------------------------#
#-----------------------------------------------------------------#


def log_entropy_E(sentences, dataset):

    template_df = pd.read_csv('../log_after_group/' + dataset + '_template.csv', usecols=['妯℃澘', '鍙ュ瓙鏍囧彿'],
                              encoding='GBK')
    templates = template_df['妯℃澘'].dropna()
    templates = templates.tolist()

    csv.field_size_limit(10 * 1024 * 1024)

    with open('../log_after_group/' + dataset + '_template.csv', newline='') as csvfile:
        reader = csv.DictReader(csvfile)
        sentence_numbers = [row['鍙ュ瓙鏍囧彿'].strip('"').split(',') for row in reader]

    total_diversity = 0
    template_count = 0

    for i in range(len(sentence_numbers)):
        template = templates[i]

        if is_english_sentence(template):
            if 'user' not in template:
                words = template.split()
                if all(has_meaning(word) for word in words):
                    continue

        if len(sentence_numbers[i]) == 1:
            continue

        elif '*' not in templates[i]:
            continue

        else:
            indices = [int(idx) for idx in sentence_numbers[i]]
            sentence_list = [sentences[idx] for idx in indices]
            diversity = get_template_diversity(template, sentence_list)
            total_diversity += diversity
            template_count += 1

    if template_count == 0:
        return 0.0

    return total_diversity / template_count


def get_united_sentences(sentences, dataset, filter):
    replaced_sentences = []

    for s in sentences:

        for rgex in filter:
            s = re.sub(rgex, '<*>', s)

        if dataset == 'HealthApp':
            s = re.sub(':', ': ', s)
            s = re.sub('=', '= ', s)
            s = re.sub(r'\|', '| ', s)
        if dataset == 'Android':
            s = re.sub(r'\(', '( ', s)
            s = re.sub(r'\)', ') ', s)
        if dataset == 'Android':
            s = re.sub(':', ': ', s)
            s = re.sub('=', '= ', s)
        if dataset == 'HPC':
            s = re.sub('=', '= ', s)
            s = re.sub('-', '- ', s)
            s = re.sub(':', ': ', s)
        if dataset == 'BGL':
            s = re.sub('=', '= ', s)
            s = re.sub(r'\.\.', '.. ', s)
            s = re.sub(r'\(', '( ', s)
            s = re.sub(r'\)', ') ', s)
        if dataset == 'Hadoop':
            s = re.sub('_', '_ ', s)
            s = re.sub(':', ': ', s)
            s = re.sub('=', '= ', s)
            s = re.sub(r'\(', '( ', s)
            s = re.sub(r'\)', ') ', s)
        if dataset == 'HDFS':
            s = re.sub(':', ': ', s)
        if dataset == 'Linux':
            s = re.sub('=', '= ', s)
            s = re.sub(':', ': ', s)
        if dataset == 'Spark':
            s = re.sub(':', ': ', s)
        if dataset == 'Thunderbird':
            s = re.sub(':', ': ', s)
            s = re.sub('=', '= ', s)
        if dataset == 'Windows':
            s = re.sub(':', ': ', s)
            s = re.sub('=', '= ', s)
            s = re.sub(r'\[', '[ ', s)
            s = re.sub(']', '] ', s)
        if dataset == 'Zookeeper':
            s = re.sub(':', ': ', s)
            s = re.sub('=', '= ', s)

        s = re.sub(',', ', ', s)

        replaced_sentences.append(s)

    # replaced_sentences = cleanTool.output_result(replaced_sentences)

    return replaced_sentences


def get_template_diversity(template, sentences):
    # Ratio of token positions with at least two distinct values.
    new_sentences = [split_sentence(s) for s in sentences]

    max_length = len(max(new_sentences, key=len))

    for i in range(len(new_sentences)):
        new_sentences[i] += ['%'] * (max_length - len(new_sentences[i]))

    diverse_count = 0
    for i in range(max_length):
        values = set(sentence[i] for sentence in new_sentences)
        if len(values) >= 2:
            diverse_count += 1

    return diverse_count / max_length if max_length > 0 else 0.0


def split_sentence(s):
    s = re.sub(' +', ' ', s).split(' ')
    return s


def is_english_sentence(sentence):
    pattern = r'^[A-Za-z\s]+$'
    return re.match(pattern, sentence) is not None


def has_meaning(word):
    dictionary = set(nltk.corpus.words.words())
    if word.lower() in dictionary:
        return True

    if word.islower() or word.isupper():
        return False

    word_parts = []
    current_part = ""
    for char in word:
        if char.isupper():
            if current_part:
                word_parts.append(current_part)
            current_part = char
        else:
            current_part += char
    word_parts.append(current_part)

    for part in word_parts:
        if part.lower() in dictionary:
            return True

    return False

if __name__ == "__main__":
    main()
