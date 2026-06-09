import datetime
import os

import Brain as Ba
import Entropy_E as EE
import Entropy_C as EC
import GPT
import DouBao
import Select as Se

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(SCRIPT_DIR)

def main():
    os.chdir(SCRIPT_DIR)
    E_dataset()
    # C_dataset()

def load_log_to_list(file_path):
    try:
        with open(file_path, 'r') as file:  # 打开文件
            log_lines = file.readlines()  # 读取所有行
        return [line.strip() for line in log_lines if line.strip()]
    except FileNotFoundError:
        print(f"找不到文件: {file_path}")
        return []
    except Exception as e:
        print(f"读取文件时发生错误: {e}")
        return []
 
def E_dataset():
    input_dir = os.path.join(BASE_DIR, 'logs', '')
    output_dir = os.path.join(BASE_DIR, 'new_dataset', '')
    log_file = 'Mac_2k.logs'
    dataset_name = 'Mac'

    """
    日志格式设置
    """
    benchmark_settings = {
        'Apache': {
            'log_file': log_file,
            'log_format': r'[<DateTime>] [<Level>] <Content>',
            'regex': [],
            'delimiter': [],
            'tag': 0,
            'theshold': 5
        },
        'Zookeeper': {
            'log_file': log_file,
            'log_format': r'<Date> <Time> - <Level>  \[<Node>:<Component>@<Id>\] - <Content>',
            'regex': [r'(/|)(\d+\.){3}\d+(:\d+)?'],
            'delimiter': [],
            'tag': 1,
            'theshold': 3
        },
        'OpenSSH': {
            'log_file': log_file,
            'log_format': r'<Date> <Day> <Time> <Component> sshd\[<Pid>\]: <Content>',
            'regex': [r'(\d+\.){3}\d+', r'([\w-]+\.){2,}[\w-]+', r'\d{2}:\d{2}:\d{2}', r'(?<=sshd\[)\d+(?=\])', r'(?<=port )\d+'],
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
            'theshold': 5,
        },
        'Android': {
            'log_file': log_file,
            'log_format': r'<Date> <Time> <Pid> <Tid> <Level> <Component>: <Content>',
            'regex': [],
            'delimiter': [],
            'tag': 0,
            'theshold': 5,
        },
        'Mac': {
            'log_file': log_file,
            'log_format': r'<Month> <Date> <Time> <Host> <Component>[<Pid>]: <Content>',
            'regex': [],
            'delimiter': [],
            'tag': 0,
            'theshold': 5
        },
        'BGL': {
            'log_file': log_file,
            'log_format': r'<Label> <Timestamp> <Date> <Node> <Time> <NodeRepeat> <RAS> <Component> <Level> <Content>',
            'regex': [],
            'delimiter': [],
            'tag': 0,
            'theshold': 5
        },
        'Hadoop': {
            'log_file': log_file,
            'log_format': r'<Date> <Time> <Level> [<Thread>] <Component>: <Content>',
            'regex': [],
            'delimiter': [],
            'tag': 0,
            'theshold': 5
        },
        'HDFS': {
            'log_file': log_file,
            'log_format': '<Date> <Time> <Pid> <Level> <Component>: <Content>',
            'regex': [],
            'delimiter': [],
            'tag': 0,
            'theshold': 2
        },
        'HPC': {
            'log_file': log_file,
            'log_format': r'<EventId> <Entity> <Component> <EventType> <Timestamp> <Flag> <Content>',
            'regex': [],
            'delimiter': [],
            'tag': 0,
            'theshold': 5
        },
        'Linux': {
            'log_file': log_file,
            'log_format': r'<Month> <Date> <Time> <Host> <Process>: <Content>',
            'regex': [],
            'delimiter': [],
            'tag': 0,
            'theshold': 5
        },
        'HealthApp': {
            'log_file': log_file,
            'log_format': r'<Time>|<Component>|<Pid>|<Content>',
            'regex': [],
            'delimiter': [r'\|'],
            'tag': 0,
            'theshold': 2
        },
        'Windows': {
            'log_file': log_file,
            'log_format': r'<Date> <Time>, <Level> <Component> <Content>',
            'regex': [],
            'delimiter': [],
            'tag': 0,
            'theshold': 5
        },
        'Thunderbird': {
            'log_file': log_file,
            'log_format': r'<Timestamp> <Date> <Node> <Month> <Day> <Time> <Host> <Content>',
            'regex': [],
            'delimiter': [],
            'tag': 0,
            'theshold': 5
        },
        'Spark': {
            'log_file': log_file,
            'log_format': r'<Date> <Time> <Level> <Component>: <Content>',
            'regex': [],
            'delimiter': [],
            'tag': 0,
            'theshold': 5
        },
        'Proxifier': {
            'log_file': log_file,
            'log_format': r'[<Date> <Time>] <Program> - <Content>',
            'regex': [],
            'delimiter': [],
            'tag': 0,
            'theshold': 5
        },
    }
    for dataset, setting in benchmark_settings.items():

        if dataset == dataset_name:
            starttime = datetime.datetime.now()
            # parse = Ba.format_log(
            #     log_format=setting['log_format'],
            #     indir='../logs/')
            # form = parse.format(setting['log_file'])
            # content = form['Content']
            # # logID = form['LineId']
            # # Date = form['Date']
            # # Time = form['Time']
            # start = datetime.datetime.now()
            # sentences = content.tolist()
            sentences = load_log_to_list(os.path.join(input_dir, log_file))

            origin_sentences = sentences.copy()


            setting['regex'] = Se.get_dataset_regex(dataset)
            GA = Ba.parse_E(sentences, setting['regex'], dataset, setting['theshold'], setting['delimiter'],setting['tag'], starttime, efficiency=False)
            print('=====' + dataset + '======   :' + str(GA))

            thre = 0
            # EE.log_entropy_E(
            #     origin_sentences,
            #     thre,
            #     dataset,
            #     setting['regex'],
            #     priority_filter='all',
            #     max_llm_calls=60
            # )


            # filename = "../log_after_gpt/" + dataset + "_gpt_data.csv"
            # DouBao.write_head(filename)
            # api_key = os.environ.get("ARK_API_KEY", "")
            # model = "ep-20260517223345-x4v58"
            # DouBao.log_gpt_E(origin_sentences,dataset,0,api_key,model)

            num = 2
            y1 = 0.8
            y2 = 1.2
            Se.log_select_E(dataset, num, y1, y2)


def C_dataset():
    input_dir = os.path.join(BASE_DIR, 'logs', '')
    output_dir = os.path.join(BASE_DIR, 'new_dataset', '')
    log_file = "alarm_1k.logs"

    filter = [r'(\d+\.\d+\.\d+\.\d+)', r'\(([^\(\)]+)\)', r'（([^（）]+)）', r'\[([^\[\]]+)\]', r'\<([^\<\>]+)\>',
              r'【([^【】]+)】', r'\{([^\{\}]+)\}', r'｛([^｛｝]+)｝', r'<>']
    # filter = [r'(\d+\.\d+\.\d+\.\d+)']
    threshold = 3
    delimiter = []
    tag = 0
    starttime = datetime.datetime.now()
    efficiency = False
    dataset = 'alarm'

    sentences = []
    with open(os.path.join(BASE_DIR, 'logs', log_file), 'r') as f:
        for line in f:
            stripped = line.strip()
            if stripped:
                sentences.append(stripped)

    origin_sentences = sentences.copy()

    GA = Ba.parse_C(sentences, filter, dataset, threshold, delimiter, tag, starttime, efficiency)

    thre = 0
    # EC.log_entropy_C(origin_sentences, thre, dataset)
    # EC.log_entropy_C(
    # origin_sentences,
    # thre,
    # dataset,
    # priority_filter='high_only',
    # max_llm_calls=20
# )

    # filename = "../log_after_gpt/" + dataset + "_gpt_data.csv"
    # DouBao.write_head(filename)
    # api_key = os.environ.get("ARK_API_KEY", "")
    # model = "ep-20260517223345-x4v58"
    # DouBao.log_gpt_C(origin_sentences, dataset, 0, api_key, model)

    # top_n = 3
    # y1 = 0.8
    # y2 = 1.2
    # Se.log_select_C(dataset,top_n,y1,y2)


if __name__ == "__main__":
    main()
