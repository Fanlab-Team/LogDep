import datetime
import time

import logTool
import getGA
import getPA
import getPTA
import getRTA


import initializeData as i_Data


def main():
    datasets = ['HDFS', 'Hadoop', 'Spark', 'Zookeeper', 'BGL', 'HPC', 'Thunderbird', 'Windows', 'Linux', 'Android',
                'HealthApp', 'Apache', 'OpenSSH', 'OpenStack', 'Mac', 'Proxifier']

    total_start_time = time.time()  # 记录开始时间

    for dataset_name in datasets:
        print(f"正在处理数据集: {dataset_name}")
        E_Analyze(dataset_name)

    total_end_time = time.time()  # 记录结束时间
    total_parse_time = total_end_time - total_start_time  # 计算总耗时

    print(f"所有数据集解析完成，总耗时: {total_parse_time:.4f} 秒")

def E_Analyze(dataset_name,data_size='2k'):

    start_time = time.time()    #将记录时间的起点放在解析方法的入口，最宽口径记录，包括了读取文件的IO时间

    if data_size == '2k' or 'dedup' in data_size or 'genius' in data_size or 'diverse' in data_size:
        if data_size == '2k':
            log_file = dataset_name+'_2k.log'
        elif data_size == 'genius':
            log_file = dataset_name+'_new_dataset.log'
        else:
            log_file = dataset_name+f'_{data_size}.log'
        benchmark_settings = {

            'Proxifier': {
                'log_file': log_file,
                'log_format': '\[<Time>\] <Program> - <Content>',
                'regex': [r'<\d+\ssec', r'([\w-]+\.)+[\w-]+(:\d+)?', r'\d{2}:\d{2}(:\d{2})*', r'[KGTM]B'],
                'delimiter': [r'\(.*?\)'],
                'tag': 0,
                'theshold': 3,
                'var_theshold': 0.4
            },
            'HDFS': {
                'log_file': log_file,
                'log_format': '<Date> <Time> <Pid> <Level> <Component>: <Content>',
                'regex': [r'blk_-?\d+', r'(\d+\.){3}\d+(:\d+)?'],
                'delimiter': [''],
                'tag': 0,
                'theshold': 2,
                'var_theshold': 0.4
            },

            'Hadoop': {
                'log_file': log_file,
                'log_format': '<Date> <Time> <Level> \[<Process>\] <Component>: <Content>',
                'regex': [r'(\d+\.){3}\d+'],
                'delimiter': [],
                'tag': 1,
                'theshold': 6,
                'var_theshold': 0.45
            },

            'Spark': {
                'log_file': log_file,
                'log_format': '<Date> <Time> <Level> <Component>: <Content>',
                'regex': [r'(\d+\.){3}\d+', r'\b[KGTM]?B\b', r'([\w-]+\.){2,}[\w-]+'],
                'delimiter': [],
                'tag': 0,
                'theshold': 4,
                'var_theshold': 0.86
            },

            'Zookeeper': {
                'log_file': log_file,
                'log_format': '<Date> <Time> - <Level>  \[<Node>:<Component>@<Id>\] - <Content>',
                'regex': [r'(/|)(\d+\.){3}\d+(:\d+)?'],
                'delimiter': [],
                'tag': 1,
                'theshold': 3,
                'var_theshold': 0.3
            },

            'BGL': {
                'log_file': log_file,
                'log_format': '<Label> <Timestamp> <Date> <Node> <Time> <NodeRepeat> <Type> <Component> <Level> <Content>',
                'regex': [r'core\.\d+'],
                'delimiter': [],
                'theshold': 6,
                'var_theshold': 0.66
            },

            'HPC': {
                'log_file': log_file,
                'log_format': '<LogId> <Node> <Component> <State> <Time> <Flag> <Content>',
                'regex': [],
                'delimiter': [],
                'theshold': 5,
                'var_theshold': 0.4
            },

            'Thunderbird': {
                'log_file': log_file,
                'log_format': '<Label> <Timestamp> <Date> <User> <Month> <Day> <Time> <Location> <Component>(\[<PID>\])?: <Content>',
                'regex': [r'(\d+\.){3}\d+'],
                'delimiter': [],
                'theshold': 3,
                'var_theshold': 0.74
            },

            'Windows': {
                'log_file': log_file,
                'log_format': '<Date> <Time>, <Level>                  <Component>    <Content>',
                'regex': [r'0x.*?\s'],
                'delimiter': [],
                'theshold': 3,
                'var_theshold': 0.3
            },

            'Linux': {
                'log_file': log_file,
                'log_format': '<Month> <Date> <Time> <Level> <Component>(\[<PID>\])?: <Content>',
                'regex': [r'(\d+\.){3}\d+', r'\d{2}:\d{2}:\d{2}', r'J([a-z]{2})'],
                'delimiter': [r''],
                'theshold': 4,
                'var_theshold': 0.3
            },

            'Android': {
                'log_file': log_file,
                'log_format': '<Date> <Time>  <Pid>  <Tid> <Level> <Component>: <Content>',
                'regex': [r'(/[\w-]+)+', r'([\w-]+\.){2,}[\w-]+',
                          r'\b(\-?\+?\d+)\b|\b0[Xx][a-fA-F\d]+\b|\b[a-fA-F\d]{4,}\b'],
                'delimiter': [r''],
                'theshold': 5,
                'var_theshold': 0.07
            },

            'HealthApp': {
                'log_file': log_file,
                'log_format': '<Time>\|<Component>\|<Pid>\|<Content>',
                'regex': [],
                'delimiter': [r''],
                'theshold': 4,
                'var_theshold': 0.25
            },

            'Apache': {
                'log_file': log_file,
                'log_format': '\[<Time>\] \[<Level>\] <Content>',
                'regex': [r'(\d+\.){3}\d+'],
                'delimiter': [],
                'theshold': 4,
                'var_theshold': 0.4
            },

            'OpenSSH': {
                'log_file': log_file,
                'log_format': '<Date> <Day> <Time> <Component> sshd\[<Pid>\]: <Content>',
                'regex': [r'(\d+\.){3}\d+', r'([\w-]+\.){2,}[\w-]+'],
                'delimiter': [],
                'theshold': 6,
                'var_theshold': 0.4
            },

            'OpenStack': {
                'log_file': log_file,
                'log_format': '<Logrecord> <Date> <Time> <Pid> <Level> <Component> \[<ADDR>\] <Content>',
                'regex': [r'((\d+\.){3}\d+,?)+', r'/.+?\s ', r'\d+'],
                'delimiter': [],
                'theshold': 6,
                'var_theshold': 0.01
            },

            'Mac': {
                'log_file': log_file,
                'log_format': '<Month>  <Date> <Time> <User> <Component>\[<PID>\]( \(<Address>\))?: <Content>',
                'regex': [r'([\w-]+\.){2,}[\w-]+'],
                'delimiter': [],
                'theshold': 5,
                'var_theshold': 0.01
            },
        }
    else:
        log_file = dataset_name+'_full.log'
        benchmark_settings = {

            'Proxifier': {
                'log_file': log_file,
                'log_format': '\[<Time>\] <Program> - <Content>',
                'regex': [r'<\d+\ssec', r'([\w-]+\.)+[\w-]+(:\d+)?', r'\d{2}:\d{2}(:\d{2})*', r'[KGTM]B'],
                'delimiter': [r'\(.*?\)'],
                'tag': 0,
                'theshold': 3,
                'var_theshold': 0.4
            },
            'HDFS': {
                'log_file': log_file,
                'log_format': '<Date> <Time> <Pid> <Level> <Component>: <Content>',
                'regex': [r'blk_-?\d+', r'(\d+\.){3}\d+(:\d+)?'],
                'delimiter': [''],
                'tag': 0,
                'theshold': 2,
                'var_theshold': 0.4
            },

            'Hadoop': {
                'log_file': log_file,
                'log_format': '<Date> <Time> <Level> \[<Process>\] <Component>: <Content>',
                'regex': [r'(\d+\.){3}\d+'],
                'delimiter': [],
                'tag': 1,
                'theshold': 6,
                'var_theshold': 0.45
            },

            'Spark': {
                'log_file': log_file,
                'log_format': '<Date> <Time> <Level> <Component>: <Content>',
                'regex': [r'(\d+\.){3}\d+', r'\b[KGTM]?B\b', r'([\w-]+\.){2,}[\w-]+'],
                'delimiter': [],
                'tag': 0,
                'theshold': 4,
                'var_theshold': 0.86
            },

            'Zookeeper': {
                'log_file': log_file,
                'log_format': '<Date> <Time> - <Level>  \[<Node>:<Component>@<Id>\] - <Content>',
                'regex': [r'(/|)(\d+\.){3}\d+(:\d+)?'],
                'delimiter': [],
                'tag': 1,
                'theshold': 3,
                'var_theshold': 0.3
            },

            'BGL': {
                'log_file': log_file,
                'log_format': '<Label> <Timestamp> <Date> <Node> <Time> <NodeRepeat> <Type> <Component> <Level> <Content>',
                'regex': [r'core\.\d+'],
                'delimiter': [],
                'theshold': 6,
                'var_theshold': 0.66
            },

            'HPC': {
                'log_file': log_file,
                'log_format': '<LogId> <Node> <Component> <State> <Time> <Flag> <Content>',
                'regex': [],
                'delimiter': [],
                'theshold': 5,
                'var_theshold': 0.4
            },

            'Thunderbird': {
                'log_file': log_file,
                'log_format': '<Label> <Timestamp> <Date> <User> <Month> <Day> <Time> <Location> <Component>(\[<PID>\])?: <Content>',
                'regex': [r'(\d+\.){3}\d+'],
                'delimiter': [],
                'theshold': 3,
                'var_theshold': 0.74
            },

            'Linux': {
                'log_file': log_file,
                'log_format': '<Month> <Date> <Time> <Level> <Component>(\[<PID>\])?: <Content>',
                'regex': [r'(\d+\.){3}\d+', r'\d{2}:\d{2}:\d{2}', r'J([a-z]{2})'],
                'delimiter': [r''],
                'theshold': 4,
                'var_theshold': 0.3
            },
            'HealthApp': {
                'log_file': log_file,
                'log_format': '<Time>\|<Component>\|<Pid>\|<Content>',
                'regex': [],
                'delimiter': [r''],
                'theshold': 4,
                'var_theshold': 0.25
            },

            'Apache': {
                'log_file': log_file,
                'log_format': '\[<Time>\] \[<Level>\] <Content>',
                'regex': [r'(\d+\.){3}\d+'],
                'delimiter': [],
                'theshold': 4,
                'var_theshold': 0.4
            },

            'OpenSSH': {
                'log_file': log_file,
                'log_format': '<Date> <Day> <Time> <Component> sshd\[<Pid>\]: <Content>',
                'regex': [r'(\d+\.){3}\d+', r'([\w-]+\.){2,}[\w-]+'],
                'delimiter': [],
                'theshold': 6,
                'var_theshold': 0.4
            },
            'OpenStack': {
                'log_file': log_file,
                'log_format': '<Logrecord> <Date> <Time> <Pid> <Level> <Component> \[<ADDR>\] <Content>',
                'regex': [r'((\d+\.){3}\d+,?)+', r'/.+?\s ', r'\d+'],
                'delimiter': [],
                'theshold': 6,
                'var_theshold': 0.01
            },

            'Mac': {
                'log_file': log_file,
                'log_format': '<Month>  <Date> <Time> <User> <Component>\[<PID>\]( \(<Address>\))?: <Content>',
                'regex': [r'([\w-]+\.){2,}[\w-]+'],
                'delimiter': [],
                'theshold': 5,
                'var_theshold': 0.01
            },
        }

    output_dir = '../result/'+dataset_name+'/'

    # with open(input_dir+log_file, 'r') as file:
    #     lines = file.readlines()
    #
    # lines = [line.strip() for line in lines]
    # sentences = list(set(lines))
    #
    # sentences = logTool.addSpaces(sentences)
    # templates = set()
    # count = 0
    # while(sentences!=[]):
    #     count+=1
    #     sentences, templates = logTool.torun(sentences,templates)
    #     sentences = list(set(sentences))
    #     print("第"+str(count)+"次迭代:")
    #     print("日志数据:",end='')
    #     print(sentences)
    #     print("模版库:", end='')
    #     print(templates)
    #
    # print("最终结果:")
    # print("模版数量："+str(len(templates)))
    # print(templates)

    all_history_data = []

    for dataset, setting in benchmark_settings.items():
        if dataset == dataset_name:

            if data_size == 'genius':
                input_dir = f'../data/dir_{data_size}/'
            else:
                input_dir = f'../data/dir_{data_size}/'+dataset_name+'/'


            parse = i_Data.format_log(
                log_format=setting['log_format'],
                indir=input_dir)

            # 根据数据规模决定是否限制读取行数
            if data_size == 'full':
                form = parse.format(setting['log_file'], max_lines=None)  # 不限制，读取全部
            else:
                form = parse.format(setting['log_file'])

            content = form['Content']
            # 转换为 (idx+1, item) 的形式，其中 idx+1 放在一个 list 中
            content = [([idx + 1], item) for idx, item in enumerate(content)]
            sentences = logTool.deduplicate(content)

            #【修改1】初始化时记录
            all_history_data.append([dataset, "Initial", len(sentences)])

            # 加了下面的这句代码会解析出错
            # sentences = logTool.addSpaces(sentences)

            templates = list()
            templates_with_idx = list()
            count = 0
            with open('test2.txt', 'w') as file:
                for _,s in sentences:
                    file.write(s + '\n')
            sentences = logTool.dataClean(sentences,setting['regex'],setting['delimiter'],dataset)

            #【修改2】清理结束后记录
            all_history_data.append([dataset, "Cleaned", len(sentences)])


            sentences = logTool.deduplicate(sentences)

            while(sentences!=[]):
                count+=1
                sentences, templates, templates_with_idx = logTool.torun(sentences,templates,templates_with_idx,setting['var_theshold'])
                sentences = logTool.deduplicate(sentences) # 去重
                #【修改3】记录每次迭代后的数据结果
                all_history_data.append([dataset, f"Iter_{count}", len(sentences)])

            parse_time = time.time() - start_time
            # print("最终结果:")
            templates_with_idx = [(sorted(indexes), content) for indexes, content in templates_with_idx]

            logTool.to_csv(form, templates_with_idx, output_dir, dataset_name)

    # 【修改3】改为追加模式写入，避免覆盖之前的数据集记录
    summary_path = f'../result/迭代次数/{data_size}迭代次数.csv'
    # 检查文件是否已经存在，如果不存在则需要写入表头
    file_exists = os.path.isfile(summary_path)
    # 使用 'a' 模式（append）打开文件
    with open(summary_path, 'a', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        # 如果是第一次创建该文件，写入表头
        if not file_exists:
            writer.writerow(["Dataset", "Step", "Count"])
        # 写入当前数据集的所有追踪数据
        writer.writerows(all_history_data)
    print(f"数据集 {dataset_name} 的记录已追加至总表：{summary_path}")

    # 确保 result 目录存在
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    # 文件名
    output_file = os.path.join(output_dir, dataset_name + "_new_template.txt")

    # 将 templates 中的每个元素逐行写入文件
    with open(output_file, 'w') as file:
        for template in templates:
            file.write(template + '\n')

    output_file = os.path.join(output_dir, dataset_name + "_new_template_with_idx.csv")

    with open(output_file, 'w', encoding='utf-8') as f:
        for indexes, content in templates_with_idx:
            f.write(f"{content} {len(indexes)}\n")
    print(f"已写入文件：{output_file}")


    #
    GA = getGA.calculate_precision(templates_with_idx, dataset_name)
    PA = getPA.getSinglePA(dataset_name)
    PTA = getPTA.getSinglePTA(dataset_name)
    RTA = getRTA.getSingleRTA(dataset_name)
    print("PA:"+str(PA))
    # print("PTA:"+str(PTA))
    # print("RTA:"+str(RTA))

    return PA,PTA,RTA,GA,parse_time


def test_threshold_range(dataset_name,data_size='2k'):
    """
    测试指定数据集在不同threshold值下的PA, PTA, RTA指标
    threshold范围从0.01到0.99
    """
    import numpy as np

    # 创建输出目录
    output_dir = '../result/' + dataset_name + '/'
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    # 输出文件路径
    output_file = os.path.join(output_dir, f"{dataset_name}_threshold_analysis.csv")

    # 获取数据集设置
    benchmark_settings = {
        'Proxifier': {
            'log_file': dataset_name + '_2k.log',
            'log_format': '\[<Time>\] <Program> - <Content>',
            'regex': [r'<\d+\ssec', r'([\w-]+\.)+[\w-]+(:\d+)?', r'\d{2}:\d{2}(:\d{2})*', r'[KGTM]B'],
            'delimiter': [r'\(.*?\)'],
            'tag': 0,
            'theshold': 3
        },
        'HDFS': {
            'log_file': dataset_name + '_2k.log',
            'log_format': '<Date> <Time> <Pid> <Level> <Component>: <Content>',
            'regex': [r'blk_-?\d+', r'(\d+\.){3}\d+(:\d+)?'],
            'delimiter': [''],
            'tag': 0,
            'theshold': 2
        },
        'Hadoop': {
            'log_file': dataset_name + '_2k.log',
            'log_format': '<Date> <Time> <Level> \[<Process>\] <Component>: <Content>',
            'regex': [r'(\d+\.){3}\d+'],
            'delimiter': [],
            'tag': 1,
            'theshold': 6
        },
        'Spark': {
            'log_file': dataset_name + '_2k.log',
            'log_format': '<Date> <Time> <Level> <Component>: <Content>',
            'regex': [r'(\d+\.){3}\d+', r'\b[KGTM]?B\b', r'([\w-]+\.){2,}[\w-]+'],
            'delimiter': [],
            'tag': 0,
            'theshold': 4
        },
        'Zookeeper': {
            'log_file': dataset_name + '_2k.log',
            'log_format': '<Date> <Time> - <Level>  \[<Node>:<Component>@<Id>\] - <Content>',
            'regex': [r'(/|)(\d+\.){3}\d+(:\d+)?'],
            'delimiter': [],
            'tag': 1,
            'theshold': 3
        },
        'BGL': {
            'log_file': dataset_name + '_2k.log',
            'log_format': '<Label> <Timestamp> <Date> <Node> <Time> <NodeRepeat> <Type> <Component> <Level> <Content>',
            'regex': [r'core\.\d+'],
            'delimiter': [],
            'theshold': 6
        },
        'HPC': {
            'log_file': dataset_name + '_2k.log',
            'log_format': '<LogId> <Node> <Component> <State> <Time> <Flag> <Content>',
            'regex': [],
            'delimiter': [],
            'theshold': 5
        },
        'Thunderbird': {
            'log_file': dataset_name + '_2k.log',
            'log_format': '<Label> <Timestamp> <Date> <User> <Month> <Day> <Time> <Location> <Component>(\[<PID>\])?: <Content>',
            'regex': [r'(\d+\.){3}\d+'],
            'delimiter': [],
            'theshold': 3
        },
        'Windows': {
            'log_file': dataset_name + '_2k.log',
            'log_format': '<Date> <Time>, <Level>                  <Component>    <Content>',
            'regex': [r'0x.*?\s'],
            'delimiter': [],
            'theshold': 3
        },
        'Linux': {
            'log_file': dataset_name + '_2k.log',
            'log_format': '<Month> <Date> <Time> <Level> <Component>(\[<PID>\])?: <Content>',
            'regex': [r'(\d+\.){3}\d+', r'\d{2}:\d{2}:\d{2}', r'J([a-z]{2})'],
            'delimiter': [r''],
            'theshold': 4
        },
        'Android': {
            'log_file': dataset_name + '_2k.log',
            'log_format': '<Date> <Time>  <Pid>  <Tid> <Level> <Component>: <Content>',
            'regex': [r'(/[\w-]+)+', r'([\w-]+\.){2,}[\w-]+',
                      r'\b(\-?\+?\d+)\b|\b0[Xx][a-fA-F\d]+\b|\b[a-fA-F\d]{4,}\b'],
            'delimiter': [r''],
            'theshold': 5
        },
        'HealthApp': {
            'log_file': dataset_name + '_2k.log',
            'log_format': '<Time>\|<Component>\|<Pid>\|<Content>',
            'regex': [],
            'delimiter': [r''],
            'theshold': 4
        },
        'Apache': {
            'log_file': dataset_name + '_2k.log',
            'log_format': '\[<Time>\] \[<Level>\] <Content>',
            'regex': [r'(\d+\.){3}\d+'],
            'delimiter': [],
            'theshold': 4
        },
        'OpenSSH': {
            'log_file': dataset_name + '_2k.log',
            'log_format': '<Date> <Day> <Time> <Component> sshd\[<Pid>\]: <Content>',
            'regex': [r'(\d+\.){3}\d+', r'([\w-]+\.){2,}[\w-]+'],
            'delimiter': [],
            'theshold': 6
        },
        'OpenStack': {
            'log_file': dataset_name + '_2k.log',
            'log_format': '<Logrecord> <Date> <Time> <Pid> <Level> <Component> \[<ADDR>\] <Content>',
            'regex': [r'((\d+\.){3}\d+,?)+', r'/.+?\s ', r'\d+'],
            'delimiter': [],
            'theshold': 6,
        },
        'Mac': {
            'log_file': dataset_name + '_2k.log',
            'log_format': '<Month>  <Date> <Time> <User> <Component>\[<PID>\]( \(<Address>\))?: <Content>',
            'regex': [r'([\w-]+\.){2,}[\w-]+'],
            'delimiter': [],
            'theshold': 5
        },
    }

    # 获取当前数据集设置
    setting = benchmark_settings.get(dataset_name)
    if not setting:
        print(f"数据集 {dataset_name} 未找到配置")
        return

    # 初始化日志解析器
    parse = i_Data.format_log(
        log_format=setting['log_format'],
        indir=f'../data/dir_{data_size}/' + dataset_name + '/')
    form = parse.format(setting['log_file'])

    content = form['Content']
    # 转换为 (idx+1, item) 的形式
    content = [([idx + 1], item) for idx, item in enumerate(content)]
    sentences = logTool.deduplicate(content)


    # 数据清理
    sentences = logTool.dataClean(sentences, setting['regex'], setting['delimiter'], dataset_name)
    sentences = logTool.deduplicate(sentences)

    # 打开CSV文件准备写入
    with open(output_file, 'w', newline='', encoding='utf-8') as csvfile:
        fieldnames = ['threshold', 'PA', 'PTA', 'RTA', 'template_count', 'execution_time']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()

        # 测试不同threshold值
        threshold_values = np.arange(0.01, 1.0, 0.01)

        for threshold in threshold_values:
            print(f"测试数据集 {dataset_name}，threshold={threshold:.2f}")

            # 复制处理后的句子用于当前测试
            test_sentences = sentences.copy()

            # 初始化变量
            templates = list()
            templates_with_idx = list()
            count = 0

            # 记录开始时间
            start_time = time.time()

            # 执行迭代处理
            while (test_sentences != []):
                count += 1
                test_sentences, templates, templates_with_idx = logTool.torun(
                    test_sentences, templates, templates_with_idx, threshold)
                test_sentences = logTool.deduplicate(test_sentences)

            # 记录结束时间
            end_time = time.time()
            execution_time = end_time - start_time

            # 计算指标
            templates_with_idx = [(sorted(indexes), content) for indexes, content in templates_with_idx]
            template_count = len(templates)

            # 保存templates_with_idx到文件，与E_Analyze方法保持一致
            template_output_file = os.path.join(output_dir, dataset_name + "_new_template_with_idx.csv")
            with open(template_output_file, 'w', encoding='utf-8') as f:
                for indexes, content in templates_with_idx:
                    f.write(f"{content} {len(indexes)}\n")

            # 获取PA, PTA, RTA
            PA = getPA.getSinglePA(dataset_name)
            PTA = getPTA.getSinglePTA(dataset_name)
            RTA = getRTA.getSingleRTA(dataset_name)

            # 写入结果
            writer.writerow({
                'threshold': f"{threshold:.2f}",
                'PA': f"{PA:.4f}",
                'PTA': f"{PTA:.4f}",
                'RTA': f"{RTA:.4f}",
                'template_count': template_count,
                'execution_time': f"{execution_time:.4f}"
            })

            print(
                f"threshold={threshold:.2f}, PA={PA:.4f}, PTA={PTA:.4f}, RTA={RTA:.4f}, 模板数={template_count}, 用时={execution_time:.4f}秒")

    print(f"已完成 {dataset_name} 的threshold分析，结果保存至: {output_file}")


def test_diversity_range():
    """
    对"7.30最低多样性实验"目录中的数据集进行PA、PTA、RTA测试
    数据集包括: HPC, OpenSSH, OpenStack, Proxifier, Thunderbird, Zookeeper
    每个数据集有两种文件: *_2kso.log 和 *_aug.log
    """
    import os
    import csv

    # 定义数据集列表
    datasets = ['HPC', 'OpenSSH', 'OpenStack', 'Proxifier', 'Thunderbird', 'Zookeeper','HealthApp']

    # 定义数据目录
    data_dir = "../7.30最低多样性实验"

    # 确保结果目录存在
    if not os.path.exists(data_dir):
        print(f"目录 {data_dir} 不存在")
        return

    # 创建结果文件
    result_file = os.path.join(data_dir, "diversity_analysis_results.csv")

    with open(result_file, 'w', newline='', encoding='utf-8') as csvfile:
        fieldnames = ['dataset', 'file_type', 'PA', 'PTA', 'RTA']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()

        # 遍历每个数据集
        for dataset in datasets:
            print(f"正在处理数据集: {dataset}")

            # 定义两种文件名
            standard_file = f"{dataset}_2kso.log"
            augmented_file = f"{dataset}_aug.log"

            # 处理标准数据文件
            standard_path = os.path.join(data_dir, standard_file)
            if os.path.exists(standard_path):
                print(f"  处理标准数据文件: {standard_file}")
                try:
                    # 临时修改log_file设置以适应新文件名
                    old_log_file = dataset + '_2k.log'
                    # 直接调用E_Analyze方法，但需要临时修改配置
                    pa, pta, rta = E_Analyze_with_custom_file(dataset, standard_path)

                    # 写入结果
                    writer.writerow({
                        'dataset': dataset,
                        'file_type': 'standard',
                        'PA': f"{pa:.4f}",
                        'PTA': f"{pta:.4f}",
                        'RTA': f"{rta:.4f}"
                    })
                    csvfile.flush()  # 确保数据写入磁盘
                except Exception as e:
                    print(f"  处理标准数据文件 {standard_file} 时出错: {e}")
                    # 写入错误结果
                    writer.writerow({
                        'dataset': dataset,
                        'file_type': 'standard',
                        'PA': 'ERROR',
                        'PTA': 'ERROR',
                        'RTA': 'ERROR'
                    })
            else:
                print(f"  标准数据文件不存在: {standard_path}")
                writer.writerow({
                    'dataset': dataset,
                    'file_type': 'standard',
                    'PA': 'FILE_NOT_FOUND',
                    'PTA': 'FILE_NOT_FOUND',
                    'RTA': 'FILE_NOT_FOUND'
                })

            # 处理增强数据文件
            augmented_path = os.path.join(data_dir, augmented_file)
            if os.path.exists(augmented_path):
                print(f"  处理增强数据文件: {augmented_file}")
                try:
                    # 调用E_Analyze方法处理增强数据
                    pa, pta, rta = E_Analyze_with_custom_file(dataset, augmented_path)

                    # 写入结果
                    writer.writerow({
                        'dataset': dataset,
                        'file_type': 'augmented',
                        'PA': f"{pa:.4f}",
                        'PTA': f"{pta:.4f}",
                        'RTA': f"{rta:.4f}"
                    })
                    csvfile.flush()  # 确保数据写入磁盘
                except Exception as e:
                    print(f"  处理增强数据文件 {augmented_file} 时出错: {e}")
                    # 写入错误结果
                    writer.writerow({
                        'dataset': dataset,
                        'file_type': 'augmented',
                        'PA': 'ERROR',
                        'PTA': 'ERROR',
                        'RTA': 'ERROR'
                    })
            else:
                print(f"  增强数据文件不存在: {augmented_path}")
                writer.writerow({
                    'dataset': dataset,
                    'file_type': 'augmented',
                    'PA': 'FILE_NOT_FOUND',
                    'PTA': 'FILE_NOT_FOUND',
                    'RTA': 'FILE_NOT_FOUND'
                })

    print(f"所有数据集处理完成，结果保存至: {result_file}")


def E_Analyze_with_custom_file(dataset_name, custom_file_path):
    """
    修改版的E_Analyze方法，支持自定义文件路径
    """
    import datetime
    import time
    import os
    import initializeData as i_Data
    import logTool
    import getPA
    import getPTA
    import getRTA

    # 从路径中提取文件名
    log_file = os.path.basename(custom_file_path)
    output_dir = '../result/' + dataset_name + '/'

    """
    日志格式设置
    """
    benchmark_settings = {
        'Proxifier': {
            'log_file': log_file,
            'log_format': '\[<Time>\] <Program> - <Content>',
            'regex': [r'<\d+\ssec', r'([\w-]+\.)+[\w-]+(:\d+)?', r'\d{2}:\d{2}(:\d{2})*', r'[KGTM]B'],
            'delimiter': [r'\(.*?\)'],
            'tag': 0,
            'theshold': 3,
            'var_theshold': 0.4
        },
        'HDFS': {
            'log_file': log_file,
            'log_format': '<Date> <Time> <Pid> <Level> <Component>: <Content>',
            'regex': [r'blk_-?\d+', r'(\d+\.){3}\d+(:\d+)?'],
            'delimiter': [''],
            'tag': 0,
            'theshold': 2,
            'var_theshold': 0.4
        },

        'Hadoop': {
            'log_file': log_file,
            'log_format': '<Date> <Time> <Level> \[<Process>\] <Component>: <Content>',
            'regex': [r'(\d+\.){3}\d+'],
            'delimiter': [],
            'tag': 1,
            'theshold': 6,
            'var_theshold': 0.45
        },

        'Spark': {
            'log_file': log_file,
            'log_format': '<Date> <Time> <Level> <Component>: <Content>',
            'regex': [r'(\d+\.){3}\d+', r'\b[KGTM]?B\b', r'([\w-]+\.){2,}[\w-]+'],
            'delimiter': [],
            'tag': 0,
            'theshold': 4,
            'var_theshold': 0.86
        },

        'Zookeeper': {
            'log_file': log_file,
            'log_format': '<Date> <Time> - <Level>  \[<Node>:<Component>@<Id>\] - <Content>',
            'regex': [r'(/|)(\d+\.){3}\d+(:\d+)?'],
            'delimiter': [],
            'tag': 1,
            'theshold': 3,
            'var_theshold': 0.3
        },

        'BGL': {
            'log_file': log_file,
            'log_format': '<Label> <Timestamp> <Date> <Node> <Time> <NodeRepeat> <Type> <Component> <Level> <Content>',
            'regex': [r'core\.\d+'],
            'delimiter': [],
            'theshold': 6,
            'var_theshold': 0.35
        },

        'HPC': {
            'log_file': log_file,
            'log_format': '<LogId> <Node> <Component> <State> <Time> <Flag> <Content>',
            'regex': [],
            'delimiter': [],
            'theshold': 5,
            'var_theshold': 0.4
        },

        'Thunderbird': {
            'log_file': log_file,
            'log_format': '<Label> <Timestamp> <Date> <User> <Month> <Day> <Time> <Location> <Component>(\[<PID>\])?: <Content>',
            'regex': [r'(\d+\.){3}\d+'],
            'delimiter': [],
            'theshold': 3,
            'var_theshold': 0.74
        },

        'Windows': {
            'log_file': log_file,
            'log_format': '<Date> <Time>, <Level>                  <Component>    <Content>',
            'regex': [r'0x.*?\s'],
            'delimiter': [],
            'theshold': 3,
            'var_theshold': 0.3
        },

        'Linux': {
            'log_file': log_file,
            'log_format': '<Month> <Date> <Time> <Level> <Component>(\[<PID>\])?: <Content>',
            'regex': [r'(\d+\.){3}\d+', r'\d{2}:\d{2}:\d{2}', r'J([a-z]{2})'],
            'delimiter': [r''],
            'theshold': 4,
            'var_theshold': 0.3
        },

        'Android': {
            'log_file': log_file,
            'log_format': '<Date> <Time>  <Pid>  <Tid> <Level> <Component>: <Content>',
            'regex': [r'(/[\w-]+)+', r'([\w-]+\.){2,}[\w-]+',
                      r'\b(\-?\+?\d+)\b|\b0[Xx][a-fA-F\d]+\b|\b[a-fA-F\d]{4,}\b'],
            'delimiter': [r''],
            'theshold': 5,
            'var_theshold': 0.07
        },

        'HealthApp': {
            'log_file': log_file,
            'log_format': '<Time>\|<Component>\|<Pid>\|<Content>',
            'regex': [],
            'delimiter': [r''],
            'theshold': 4,
            'var_theshold': 0.25
        },

        'Apache': {
            'log_file': log_file,
            'log_format': '\[<Time>\] \[<Level>\] <Content>',
            'regex': [r'(\d+\.){3}\d+'],
            'delimiter': [],
            'theshold': 4,
            'var_theshold': 0.4
        },

        'OpenSSH': {
            'log_file': log_file,
            'log_format': '<Date> <Day> <Time> <Component> sshd\[<Pid>\]: <Content>',
            'regex': [r'(\d+\.){3}\d+', r'([\w-]+\.){2,}[\w-]+'],
            'delimiter': [],
            'theshold': 6,
            'var_theshold': 0.4
        },

        'OpenStack': {
            'log_file': log_file,
            'log_format': '<Logrecord> <Date> <Time> <Pid> <Level> <Component> \[<ADDR>\] <Content>',
            'regex': [r'((\d+\.){3}\d+,?)+', r'/.+?\s ', r'\d+'],
            'delimiter': [],
            'theshold': 6,
            'var_theshold': 0.01
        },

        'Mac': {
            'log_file': log_file,
            'log_format': '<Month>  <Date> <Time> <User> <Component>\[<PID>\]( \(<Address>\))?: <Content>',
            'regex': [r'([\w-]+\.){2,}[\w-]+'],
            'delimiter': [],
            'theshold': 5,
            'var_theshold': 0.01
        },
    }

    for dataset, setting in benchmark_settings.items():
        if dataset == dataset_name:
            starttime = datetime.datetime.now()
            # 使用自定义文件路径的目录
            custom_dir = os.path.dirname(custom_file_path) + '/'
            parse = i_Data.format_log(
                log_format=setting['log_format'],
                indir=custom_dir)
            form = parse.format(setting['log_file'])

            content = form['Content']
            # 转换为 (idx+1, item) 的形式，其中 idx+1 放在一个 list 中
            content = [([idx + 1], item) for idx, item in enumerate(content)]
            sentences = logTool.deduplicate(content)

            templates = list()
            templates_with_idx = list()
            count = 0
            start_time = time.time()
            sentences = logTool.dataClean(sentences, setting['regex'], setting['delimiter'], dataset)
            sentences = logTool.deduplicate(sentences)

            while (sentences != []):
                count += 1
                sentences, templates, templates_with_idx = logTool.torun(sentences, templates, templates_with_idx,
                                                                         setting['var_theshold'])
                sentences = logTool.deduplicate(sentences)  # 去重

            end_time = time.time()

            templates_with_idx = [(sorted(indexes), content) for indexes, content in templates_with_idx]

    # 确保 result 目录存在
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    # 文件名
    output_file = os.path.join(output_dir, dataset_name + "_new_template.txt")

    # 将 templates 中的每个元素逐行写入文件
    with open(output_file, 'w') as file:
        for template in templates:
            file.write(template + '\n')

    output_file = os.path.join(output_dir, dataset_name + "_new_template_with_idx.csv")

    with open(output_file, 'w', encoding='utf-8') as f:
        for indexes, content in templates_with_idx:
            f.write(f"{content} {len(indexes)}\n")
    print(f"已写入文件：{output_file}")

    PA = getPA.getSinglePA(dataset_name)
    PTA = getPTA.getSinglePTA(dataset_name)
    RTA = getRTA.getSingleRTA(dataset_name)
    print("PA:" + str(PA))

    return PA, PTA, RTA


def save_evaluation_results_to_csv(data_size='2k'):
    """
    对所有数据集进行评估，并将指标及其平均值保存到CSV文件中
    """
    import csv
    import os

    if data_size == '2k' or data_size == 'deduplicated' or data_size == 'genius' or "dedup" in data_size or 'diverse' in data_size:
        datasets = ['HDFS', 'Hadoop', 'Spark', 'Zookeeper', 'BGL', 'HPC', 'Thunderbird', 'Windows', 'Linux', 'Android',
                'HealthApp', 'Apache', 'OpenSSH', 'OpenStack', 'Mac', 'Proxifier']
    else:
        datasets = ['HDFS', 'Spark', 'BGL','Thunderbird']
    print("开始评估所有数据集...")

    result_dir = '../result'
    if not os.path.exists(result_dir):
        os.makedirs(result_dir)

    result_file = os.path.join(result_dir, 'evaluation_results.csv')

    # --- 初始化累加器 ---
    metrics_sum = {'PA': 0.0, 'PTA': 0.0, 'RTA': 0.0, 'GA': 0.0, 'parse_time': 0.0}
    success_count = 0

    with open(result_file, 'w', newline='', encoding='utf-8') as csvfile:
        fieldnames = ['dataset', 'PA', 'PTA', 'RTA', 'GA', 'parse_time']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()

        for dataset_name in datasets:
            print(f"正在处理数据集: {dataset_name}")
            try:
                PA, PTA, RTA, GA, parse_time = E_Analyze(dataset_name, data_size)

                # 累加数据以便计算平均值
                metrics_sum['PA'] += PA
                metrics_sum['PTA'] += PTA
                metrics_sum['RTA'] += RTA
                metrics_sum['GA'] += GA
                metrics_sum['parse_time'] += parse_time
                success_count += 1

                writer.writerow({
                    'dataset': dataset_name,
                    'PA': f"{PA:.4f}",
                    'PTA': f"{PTA:.4f}",
                    'RTA': f"{RTA:.4f}",
                    'GA': f"{GA:.4f}",
                    'parse_time': f"{parse_time:.4f}"
                })
                csvfile.flush()
                print(f"  {dataset_name} 处理成功")

            except Exception as e:
                print(f"  处理数据集 {dataset_name} 时出错: {e}")
                writer.writerow({k: ('ERROR' if k != 'dataset' else dataset_name) for k in fieldnames})

        # --- 计算并写入平均值 ---
        if success_count > 0:
            avg_row = {'dataset': 'AVERAGE'}
            for key in metrics_sum:
                avg_val = metrics_sum[key] / success_count
                avg_row[key] = f"{avg_val:.4f}"

            writer.writerow(avg_row)
            print(f"\n所有数据集处理完毕。成功数量: {success_count}, 平均值已计算并写入。")
        else:
            print("\n没有成功评估的数据集，未计算平均值。")

    print(f"结果已保存至: {result_file}")


def merge_threshold_analysis_results():
    """
    将所有数据集的threshold分析结果整合到一个CSV文件中
    """
    import os
    import csv
    import glob

    # 定义数据集列表
    datasets = ['HDFS', 'Hadoop', 'Spark', 'Zookeeper', 'BGL', 'HPC', 'Thunderbird', 'Windows', 'Linux', 'Android',
                'HealthApp', 'Apache', 'OpenSSH', 'OpenStack', 'Mac', 'Proxifier']

    # 创建结果目录
    result_dir = '../result'
    if not os.path.exists(result_dir):
        os.makedirs(result_dir)

    # 创建整合结果文件路径
    merged_result_file = os.path.join(result_dir, 'merged_threshold_analysis_results.csv')

    # 打开整合结果文件准备写入
    with open(merged_result_file, 'w', newline='', encoding='utf-8') as merged_csvfile:
        # 定义字段名
        fieldnames = ['dataset', 'threshold', 'PA', 'PTA', 'RTA', 'template_count', 'execution_time']
        writer = csv.DictWriter(merged_csvfile, fieldnames=fieldnames)

        # 写入表头
        writer.writeheader()

        # 遍历每个数据集
        for dataset_name in datasets:
            # 定义单个数据集的结果文件路径
            dataset_result_dir = os.path.join(result_dir, dataset_name)
            dataset_result_file = os.path.join(dataset_result_dir, f"{dataset_name}_threshold_analysis.csv")

            # 检查文件是否存在
            if os.path.exists(dataset_result_file):
                print(f"正在处理数据集 {dataset_name} 的结果文件")

                try:
                    # 读取单个数据集的结果文件
                    with open(dataset_result_file, 'r', encoding='utf-8') as csvfile:
                        reader = csv.DictReader(csvfile)

                        # 将每行数据写入整合文件，添加数据集名称
                        for row in reader:
                            merged_row = {
                                'dataset': dataset_name,
                                'threshold': row.get('threshold', ''),
                                'PA': row.get('PA', ''),
                                'PTA': row.get('PTA', ''),
                                'RTA': row.get('RTA', ''),
                                'template_count': row.get('template_count', ''),
                                'execution_time': row.get('execution_time', '')
                            }
                            writer.writerow(merged_row)

                    print(f"  已处理 {dataset_name} 的结果")

                except Exception as e:
                    print(f"  处理数据集 {dataset_name} 的结果文件时出错: {e}")
                    # 写入错误记录
                    writer.writerow({
                        'dataset': dataset_name,
                        'threshold': 'ERROR',
                        'PA': 'ERROR',
                        'PTA': 'ERROR',
                        'RTA': 'ERROR',
                        'template_count': 'ERROR',
                        'execution_time': 'ERROR'
                    })
            else:
                print(f"数据集 {dataset_name} 的结果文件不存在: {dataset_result_file}")
                # 写入文件不存在记录
                writer.writerow({
                    'dataset': dataset_name,
                    'threshold': 'FILE_NOT_FOUND',
                    'PA': 'FILE_NOT_FOUND',
                    'PTA': 'FILE_NOT_FOUND',
                    'RTA': 'FILE_NOT_FOUND',
                    'template_count': 'FILE_NOT_FOUND',
                    'execution_time': 'FILE_NOT_FOUND'
                })

    print(f"所有数据集的threshold分析结果已整合，保存至: {merged_result_file}")

def time_cost(data_size='2k'):
    # datasets = ['HDFS', 'Hadoop', 'Spark', 'Zookeeper', 'BGL', 'HPC', 'Thunderbird', 'Windows', 'Linux', 'Android',
    #             'HealthApp', 'Apache', 'OpenSSH', 'OpenStack', 'Mac', 'Proxifier']

    datasets = ['HDFS', 'BGL', 'Spark', 'Thunderbird']

    # 创建时间记录目录
    time_dir = '../result/Brain26_2_20/time/'
    if not os.path.exists(time_dir):
        os.makedirs(time_dir)

    # 创建时间记录文件
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    time_file = os.path.join(time_dir, f"time_cost{timestamp}_{data_size}.csv")

    dataset_times = []
    total_parse_time = 0.0  # 初始化总耗时

    for dataset_name in datasets:
        print(f"正在处理数据集: {dataset_name}")
        PA, PTA, RTA, GA, parse_time = E_Analyze(dataset_name,data_size=data_size)  # 获取parse_time
        dataset_times.append((dataset_name, parse_time))
        total_parse_time += parse_time  # 累加parse_time
        print(f"{dataset_name} 解析完成，耗时: {parse_time:.4f} 秒")

    print(f"所有数据集解析完成，总耗时: {total_parse_time:.4f} 秒")

    # 将时间记录写入CSV文件
    with open(time_file, 'w', newline='', encoding='utf-8') as csvfile:
        fieldnames = ['dataset', 'parse_time']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()

        for dataset_name, parse_time in dataset_times:
            writer.writerow({'dataset': dataset_name, 'parse_time': f"{parse_time:.4f}"})

        writer.writerow({'dataset': 'Total', 'parse_time': f"{total_parse_time:.4f}"})

    print(f"时间记录已保存至: {time_file}")


import os
import csv


def test_diversity():
    # 测试每个数据集中从1到21的日志数据，步长为2
    # dedup_scale = [1, 3, 5, 7, 9, 11, 13, 15, 17, 19, 21]
    dedup_scale = [1,2,3,4,5,6,7,8]
    result_dir = '../result'
    if not os.path.exists(result_dir):
        os.makedirs(result_dir)

    result_file = os.path.join(result_dir, 'diversity_result.csv')

    # --- 初始化总累加器 (用于计算所有 N 的平均值) ---
    end_sum = {'PA': 0.0, 'PTA': 0.0, 'RTA': 0.0, 'GA': 0.0}
    end_count = 0

    # 定义数据集列表
    # datasets = ['HDFS', 'Hadoop', 'Spark', 'Zookeeper', 'BGL', 'HPC', 'Thunderbird',
    #             'Windows', 'Linux', 'Android', 'HealthApp', 'Apache', 'OpenSSH',
    #             'OpenStack', 'Mac', 'Proxifier']
    # 按平均数
    # datasets = ['HDFS', 'Hadoop', 'Spark', 'Zookeeper', 'Thunderbird',
    #             'HealthApp', 'Apache', 'OpenSSH','OpenStack', 'Proxifier']
    # 按零样本数
    datasets = ['HDFS','Spark', 'Zookeeper', 'HPC',
                'Windows', 'Apache', 'OpenSSH',
                'OpenStack', 'Proxifier']
    # 去除按平均数前三
    # datasets = ['HDFS', 'Hadoop', 'Spark', 'Zookeeper', 'HPC',
    #             'Windows', 'Linux', 'HealthApp', 'Apache', 'OpenSSH',
    #             'OpenStack', 'Proxifier']

    # datasets = ['HDFS', 'Hadoop', 'Spark', 'Zookeeper', 'Thunderbird',
    #             'Windows', 'Apache', 'OpenSSH',
    #             'OpenStack', 'Proxifier']

    with open(result_file, 'w', newline='', encoding='utf-8') as csvfile:
        fieldnames = ['dedup_scale', 'PA', 'PTA', 'RTA', 'GA']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()

        for n in dedup_scale:
            print(f"\n" + "=" * 40)
            print(f"正在处理 N={n} 丰富度数据集")
            print("=" * 40)

            metrics_sum = {'PA': 0.0, 'PTA': 0.0, 'RTA': 0.0, 'GA': 0.0}
            success_count = 0

            for dataset_name in datasets:
                print(f"  -> 正在分析: {dataset_name}")
                try:
                    # 假设 E_Analyze 能够接收 n 来定位目录 '../dir_dedup_n/...'
                    PA, PTA, RTA, GA, _ = E_Analyze(dataset_name, f'dedup_{n}')

                    metrics_sum['PA'] += PA
                    metrics_sum['PTA'] += PTA
                    metrics_sum['RTA'] += RTA
                    metrics_sum['GA'] += GA
                    success_count += 1
                    print(f"     [成功] {dataset_name} (N={n})")

                except Exception as e:
                    print(f"     [错误] {dataset_name}: {e}")

            # --- 计算并写入该 N 规模下的平均值 ---
            if success_count > 0:
                one_row = {'dedup_scale': n}
                # 用于累加到总平均值的中间变量
                current_n_avg = {}

                for key in metrics_sum:
                    avg_val = metrics_sum[key] / success_count
                    current_n_avg[key] = avg_val
                    one_row[key] = f"{avg_val:.4f}"  # 格式化用于 CSV 写入

                writer.writerow(one_row)

                # --- 累加到最终汇总 (使用浮点数而非字符串) ---
                for key in end_sum:
                    end_sum[key] += current_n_avg[key]
                end_count += 1

                print(f"\n[完成] N={n} 数据集。成功数: {success_count}, 均值已写入。")
            else:
                print(f"\n[警告] N={n} 没有成功评估的数据集。")

        # --- 循环结束后写入总平均值 ---
        if end_count > 0:
            end_row = {'dedup_scale': 'AVERAGE'}
            for key in end_sum:
                end_row[key] = f"{(end_sum[key] / end_count):.4f}"
            writer.writerow(end_row)
            print("\n" + "#" * 40)
            print(f"所有任务结束。总平均值已记录至: {result_file}")
            print("#" * 40)
        else:
            print("\n[错误] 未能生成任何有效的平均数据。")

    print(f"结果已保存至: {result_file}")






if __name__ == "__main__":

    # main()
    # time_cost()
    # test_diversity_range()
    # merge_threshold_analysis_results()
    # data_sizes = ['10k','100k']
    # for data_size in data_sizes:
    #     time_cost(data_size=data_size)
    #
    print("开始执行")
    save_evaluation_results_to_csv(data_size='dedup_1')

    test_diversity()

    # datasets = ['HDFS', 'Hadoop', 'Spark', 'Zookeeper', 'BGL', 'HPC', 'Thunderbird', 'Windows', 'Linux', 'Android',
    #             'HealthApp', 'Apache', 'OpenSSH', 'OpenStack', 'Mac','Proxifier']
    # for dataset_name in datasets:
    #     PA, PTA, RTA,GA, parse_time=E_Analyze(dataset_name)

    # data_sizes = ['450k','550k','600k','650k','700k','750k','800k','850k','900k','950k','1M']
    # for data_size in data_sizes:
    #     datasets = ['HDFS', 'Hadoop', 'Spark', 'Zookeeper', 'BGL', 'HPC', 'Thunderbird', 'Linux',
    #             'HealthApp', 'Apache', 'OpenSSH', 'OpenStack', 'Mac','Proxifier']
    #     for dataset_name in datasets:
    #         PA, PTA, RTA,GA, parse_time= E_Analyze(dataset_name, data_size=data_size)

    # for dataset_name in datasets:
    #     test_threshold_range(dataset_name)
