import pickle
import json
import pandas as pd
def cache_to_file(log_tuples, cached_file):
    with open(cached_file, "w") as fw:
        for tuples in log_tuples:
            fw.write(f"{tuples[1]} {tuples[0]}\n")


def load_pickle(file_path):
    try:
        with open(file_path, 'rb') as file:
            data = pickle.load(file)
            return data
    except FileNotFoundError:
        print("No file:", file_path)
        return None
    except Exception as e:
        print("Load Error:", str(e))
        return None


def save_pickle(data, file_path):
    try:
        with open(file_path, 'wb') as file:
            pickle.dump(data, file)
        #print("Save success:", file_path)
    except Exception as e:
        print("Save error:", str(e))

def load_tuple_list(file_path):
    with open(file_path, 'r') as f:
        lines = f.readlines()
    tuple_list = []
    for line in lines:
        idx, s = line.strip().split(' ', 1)
        tuple_list.append((s, int(idx)))
    return tuple_list


def read_json_file(file_path):
    data = []
    with open(file_path, 'r') as file:
        for line in file:
            json_dict = json.loads(line)
            data.append(json_dict)
    return data

def count_templates(str_dir,tmp_dir):
    # 读取结构化日志文件
    structured_df = pd.read_csv(str_dir)

    # 读取模板文件
    templates_df = pd.read_csv(tmp_dir)

    # 统计每个EventTemplate的出现次数
    template_counts = structured_df['EventTemplate'].value_counts()

    # 将统计结果添加到模板文件中
    templates_df['Occurrences'] = templates_df['EventTemplate'].map(template_counts).fillna(0).astype(int)

    # 保存更新后的模板文件
    templates_df.to_csv(tmp_dir, index=False)

print("统计完成并已更新模板文件")