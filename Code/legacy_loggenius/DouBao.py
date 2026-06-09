import openai
import os
import re
import csv
import time
import datetime
from volcenginesdkarkruntime import Ark


def build_prompt(sentence, dataset=''):
    if dataset == 'Apache':
        return (
            "你是一个Apache error log数据生成器。请根据下面这条Apache日志生成10条同结构日志。\n"
            "规则：\n"
            "1. 只替换明显是变量的字段（如IP地址、端口号、进程号、纯数字等），固定文本和日志事件类型必须一字不改\n"
            "2. 如果不确定某个字段是否为变量，请保留原值，不要随意改动\n"
            "3. 每行一条日志，只输出10行\n"
            "4. 不要编号、不要解释、不要Markdown、不要代码块\n"
            "5. 不要输出任何非日志内容\n"
            "6. 每条扩充日志必须是完整Apache日志行，必须以 [Sun Dec 04 HH:MM:SS 2005] [notice] 或 [Sun Dec 04 HH:MM:SS 2005] [error] 开头\n"
            "7. 绝对不能只输出Content部分，必须包含完整的三部分： [日期时间] [级别] Content\n"
            "8. 日期时间格式严格为 [Sun Dec 04 HH:MM:SS 2005]，级别必须加方括号如 [notice] 或 [error]\n"
            "9. 如果原句包含 workerEnv.init() ok 或 jk2_init() Found child，则使用 [notice]\n"
            "10. 如果原句包含 mod_jk、mod_proxy、mod_rewrite、mod_headers、error state、Can't find child、Directory index forbidden，则使用 [error]\n"
            "\n原始日志：" + sentence + "\n\n"
            "直接输出10行完整Apache日志："
        )
    elif dataset == 'HDFS':
        return (
            "你是一个HDFS日志数据生成器。请根据下面这条HDFS日志生成10条同结构日志。\n"
            "规则：\n"
            "1. 只替换明显是变量的字段（如block ID、IP地址、端口号、Date、Time、Pid、纯数字等），固定文本和日志事件类型必须一字不改\n"
            "2. 如果不确定某个字段是否为变量，请保留原值，不要随意改动\n"
            "3. 每行一条日志，只输出10行\n"
            "4. 不要编号、不要解释、不要Markdown、不要代码块\n"
            "5. 不要输出任何非日志内容\n"
            "6. 每条扩充日志必须是完整HDFS日志行，必须保持格式：<Date> <Time> <Pid> <Level> <Component>: <Content>\n"
            "7. 绝对不能只输出Content部分，必须包含完整的头部，示例格式：081110 211541 18 INFO dfs.DataNode: 10.250.15.198:50010 Starting thread to transfer block blk_4292382298896622412 to 10.250.15.240:50010\n"
            "8. Date为6位数字如081110，Time为6位数字如211541，Pid为纯数字，Level为全大写如INFO/WARN/ERROR，Component保持原句的组件名不变\n"
            "9. 只能生成和原句同类型的HDFS日志，不能改变日志事件类型\n"
            "10. 如果原句是Starting thread to transfer block类型，就只能生成同类型transfer block日志，不能改成replicate或delete\n"
            "11. 如果原句是ask ... to replicate ...类型，就只能生成同类型replicate日志，不能改成transfer或delete\n"
            "12. 如果原句是ask ... to delete ...类型，就只能生成同类型delete日志，不能改成transfer或replicate\n"
            "13. Date、Time、Pid、IP地址、端口号、block id这些变量可以变化，但日志结构和固定文本不能变\n"
            "\n原始日志：" + sentence + "\n\n"
            "直接输出10行完整HDFS日志："
        )
    elif dataset == 'HealthApp':
        return (
            "你是一个HealthApp日志数据生成器。请根据下面这条HealthApp日志生成10条同结构日志。\n"
            "规则：\n"
            "1. 只替换明显是变量的字段（如时间戳、纯数字等），固定文本和日志事件类型必须一字不改\n"
            "2. 如果不确定某个字段是否为变量，请保留原值，不要随意改动\n"
            "3. 每行一条日志，只输出10行\n"
            "4. 不要编号、不要解释、不要Markdown、不要代码块\n"
            "5. 不要输出任何非日志内容\n"
            "6. 每条扩充日志必须是完整HealthApp日志行，必须保持格式：<Time>|<Component>|<Pid>|<Content>\n"
            "7. 绝对不能只输出Content部分，必须包含完整的头部，示例格式：20171223-22:16:0:119|Step_LSC|30002312|processHandleBroadcastAction action:android.intent.action.TIME_TICK\n"
            "8. Component必须保持和原句一致，不要新增原始数据中没有的组件名\n"
            "9. Pid保持30002312不变\n"
            "10. Time字段可以变化，但必须保持格式如 20171223-23:7:6:86 或 20171224-0:0:0:229\n"
            "11. Content结构必须和原句一致，不要换成其他业务语义\n"
            "12. 只能生成和原句同类型的日志\n"
            "\n原始日志：" + sentence + "\n\n"
            "直接输出10行完整HealthApp日志："
        )
    elif dataset == 'Android':
        return (
            "你是一个Android日志数据生成器。请根据下面这条Android日志生成10条同结构日志。\n"
            "规则：\n"
            "1. 只替换明显是变量的字段（如时间戳、pid、uid、数字、十六进制ID、包名等），固定文本和日志事件类型必须一字不改\n"
            "2. 如果不确定某个字段是否为变量，请保留原值，不要随意改动\n"
            "3. 每行一条日志，只输出10行\n"
            "4. 不要编号、不要解释、不要Markdown、不要代码块\n"
            "5. 不要输出任何非日志内容\n"
            "6. 每条扩充日志必须是完整Android日志行，必须保持格式：<Date> <Time> <Pid> <Tid> <Level> <Component>: <Content>\n"
            "7. 绝对不能只输出Content部分，必须包含完整的日志头部，示例：03-17 16:13:38.819  1702  8671 D PowerManagerService: acquire lock=233570404, flags=0x1, tag=\"View Lock\", name=com.android.systemui, ws=null, uid=10037, pid=2227\n"
            "8. Component必须保持和原句一致，例如 TextView、ActivityManager、WifiController、MediaPlayer、PhoneInterfaceManager，不要凭空新增新的组件名\n"
            "9. 日志级别 D/I/W/V/E 要尽量保持和原句一致\n"
            "10. Content结构必须和原句一致，只允许替换变量值，不要改变固定文本\n"
            "11. 对 TextView 类日志，固定部分如 visible is system.xxx 必须保持\n"
            "12. 对 PhoneInterfaceManager 类日志，固定部分如 [PhoneIntfMgr] getDataEnabled 必须保持\n"
            "13. 对 MediaPlayer 类日志，固定部分如 MediaPlayer destructor 或 [HSM] stayAwake 必须保持\n"
            "14. 只能生成和原句同类型的日志\n"
            "\n原始日志：" + sentence + "\n\n"
            "直接输出10行完整Android日志："
        )
    elif dataset == 'Mac':
        return (
            "你是一个Mac系统日志数据生成器。请根据下面这条Mac日志生成5条同结构日志。\n"
            "规则：\n"
            "1. 只替换明显是变量的字段（如IP地址、端口号、进程号、纯数字、十六进制值、文件路径等），固定文本和日志事件类型必须一字不改\n"
            "2. 如果不确定某个字段是否为变量，请保留原值，不要随意改动\n"
            "3. 每行一条日志，只输出5行\n"
            "4. 不要编号、不要解释、不要Markdown、不要代码块\n"
            "5. 不要输出任何非日志内容\n"
            "6. 每条扩充日志必须是完整Mac日志行，必须保持格式：<Month> <Date> <Time> <Host> <Component>[<PID>]: <Content>\n"
            "7. 绝对不能只输出Content部分，必须包含完整的日志头部，示例：Jul  1 09:00:55 calvisitor-10-105-160-95 kernel[0]: IOThunderboltSwitch<0>(0x0)::listenerCallback - Thunderbolt HPD packet for route = 0x0 port = 11 unplug = 0\n"
            "8. Component必须保持和原句一致，如 kernel、configd、mDNSResponder、QQ、symptomsd 等，不要凭空新增新的组件名\n"
            "9. PID可以变化，但必须放在方括号内如 [0] 或 [10018]\n"
            "10. Host可以变化，可以为 calvisitor-数字串 或 authorMacBook-Pro 或 airbears2-数字串\n"
            "11. Month为三字母缩写如 Jul Aug Sep，Date为1-2位数字，Time为 HH:MM:SS 格式\n"
            "12. Content结构必须和原句一致，只允许替换变量值，不要改变固定文本\n"
            "13. 不要生成 URL\n"
            "14. 不要生成邮箱地址\n"
            "15. 不要生成超长路径\n"
            "16. 不要生成 JSON\n"
            "17. 不要生成 <KSUpdateEngine...> 这种超长对象结构\n"
            "18. 不要生成随机新组件名\n"
            "19. 不要生成新的事件类型\n"
            "20. 不要生成 GoogleSoftwareUpdateAgent、ksfetch、CalendarAgent 这类复杂日志类型\n"
            "21. 只能生成和原句同类型的日志\n"
            "\n原始日志：" + sentence + "\n\n"
            "直接输出3行完整Mac日志："
        )
    else:
        return (
            "你是一个日志数据生成器。请根据下面这条日志生成10条同结构日志。\n"
            "规则：\n"
            "1. 只替换明显是变量的字段（如IP地址、端口号、时间、进程号、纯数字等），固定文本和日志事件类型必须一字不改\n"
            "2. 如果不确定某个字段是否为变量，请保留原值，不要随意改动\n"
            "3. 每行一条日志，只输出10行\n"
            "4. 不要编号、不要解释、不要Markdown、不要代码块\n"
            "5. 不要输出任何非日志内容\n\n"
            "原始日志：" + sentence + "\n\n"
            "直接输出10行日志："
        )


def ensure_apache_header(line):
    """为缺少头部的Apache日志行补全 [DateTime] [Level] 头部"""
    import random

    # 已有完整头部，直接返回
    if re.match(r'\[[A-Z][a-z]{2}\s+[A-Z][a-z]{2}\s+\d{2}\s+\d{2}:\d{2}:\d{2}\s+\d{4}\]\s+\[(notice|error|warn|debug|info|crit|alert|emerg)\]', line):
        return line

    # 检查是否有孤立的 [error] 或 [notice] 等头部
    bare_level_match = re.match(r'^\[(notice|error|warn|debug|info|crit|alert|emerg)\]\s*(.*)', line)
    if bare_level_match:
        existing_level = bare_level_match.group(1)
        content = bare_level_match.group(2)
    else:
        existing_level = None
        content = line

    # 判断日志级别
    if existing_level:
        level = existing_level
    elif re.search(r'workerEnv\.init\(\) ok|jk2_init\(\) Found child', content):
        level = 'notice'
    else:
        level = 'error'

    # 轮换使用合理时间戳
    timestamps = [
        '[Sun Dec 04 04:47:44 2005]',
        '[Sun Dec 04 04:51:08 2005]',
        '[Sun Dec 04 04:52:12 2005]',
        '[Sun Dec 04 05:15:09 2005]',
    ]
    ts = random.choice(timestamps)

    return f'{ts} [{level}] {content.strip()}'


def clean_llm_response(answer, dataset=''):
    lines = answer.split("\n")
    cleaned = []
    for line in lines:
        s = line.strip()
        if not s:
            continue
        if s.startswith("```"):
            continue
        if s.startswith("---"):
            continue
        if s.startswith("#"):
            continue
        if s.startswith("**"):
            continue
        if s.startswith(">"):
            continue
        s = re.sub(r'^\d+[\.\)、．]\s*', '', s).strip()
        if not s:
            continue
        if re.match(r'^(以下是|说明|这些日志|所有可变|构造|解释|以下为|请确保|严格|仅替换|这里提供|如果需要|请注意|供参考|版本\d)', s):
            continue
        if dataset == 'Apache':
            s = ensure_apache_header(s)
        cleaned.append(s)
    return cleaned


def call_doubao_with_retry(words, api_key, model, max_retries=3):
    last_error = None
    for attempt in range(max_retries):
        try:
            response = use_DouBao_api(words, api_key, model)
            return response
        except Exception as e:
            last_error = e
            if attempt < max_retries - 1:
                wait = 3 + attempt
                print(f"  API retry {attempt+1}/{max_retries-1} after {type(e).__name__}, wait {wait}s: {e}")
                time.sleep(wait)
    raise last_error


def log_failed(dataset, idx, sentence, error):
    filename = "../log_after_gpt/" + dataset + "_failed_indices.csv"
    file_exists = os.path.exists(filename)
    with open(filename, "a", newline="", encoding="gbk") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["index", "origin_sentence", "error_type", "error_message"])
        writer.writerow([idx, sentence, type(error).__name__, str(error)])


def load_processed_sentences(filename):
    if not os.path.exists(filename):
        return set()
    processed = set()
    with open(filename, "r", encoding="gbk") as f:
        reader = csv.reader(f)
        header = next(reader, None)
        if header is None:
            return set()
        origin_col = header.index("原句子") if "原句子" in header else 1
        for row in reader:
            if len(row) > origin_col:
                processed.add(row[origin_col])
    return processed


def log_gpt_E(sentences, dataset, thre, api_key, model):
    with open('../log_after_entropy/' + dataset + '_expanded_indices_thre_' + str(thre) + '.csv', 'r') as csvfile:
        reader = csv.reader(csvfile)
        next(reader)
        sentence_indices = next(reader)

    filename = "../log_after_gpt/" + dataset + "_gpt_data.csv"
    processed_sentences = load_processed_sentences(filename)

    for i in range(0, len(sentence_indices), 1):

        sentence_index = int(sentence_indices[i])
        sentence = sentences[sentence_index]
        print(sentence_index)
        print(sentence)

        if sentence in processed_sentences:
            print(f"  Skip (already processed)")
            continue

        try:
            if "\n" in sentence:
                words = "请根据这条日志构造1条仅改变变量字段的类似数据，只输出日志行：" + sentence
                expanded_sentences = []

                for _ in range(4):
                    response = call_doubao_with_retry(words, api_key, model)
                    answer = response.choices[0].message.content
                    cleaned = clean_llm_response(answer, dataset)
                    if cleaned:
                        expanded_sentences.append(cleaned[0])
                    time.sleep(16)

            else:
                words = build_prompt(sentence, dataset)
                response = call_doubao_with_retry(words, api_key, model)
                answer = response.choices[0].message.content
                expanded_sentences = clean_llm_response(answer, dataset)
                print(expanded_sentences)

                if len(expanded_sentences) < 5:
                    print(f"  WARNING: only {len(expanded_sentences)} valid lines after cleaning (need >=5)")

        except Exception as e:
            print(f"  FAILED [{sentence_index}]: {type(e).__name__}: {e}")
            log_failed(dataset, sentence_index, sentence, e)
            continue

        with open(filename, "a", newline="", encoding="gbk") as file:
            writer = csv.writer(file)
            row = [str(i), sentence] + expanded_sentences
            writer.writerow(row)


def log_gpt_C(sentences, dataset, thre, api_key, model):
    with open('../log_after_entropy/' + dataset + '_expanded_indices_thre_' + str(thre) + '.csv', 'r') as csvfile:
        reader = csv.reader(csvfile)
        next(reader)
        sentence_indices = next(reader)

    filename = "../log_after_gpt/" + dataset + "_gpt_data.csv"
    processed_sentences = load_processed_sentences(filename)

    for i in range(1, len(sentence_indices), 1):

        sentence_index = int(sentence_indices[i])
        sentence = sentences[sentence_index]
        print(sentence_index)
        print(sentence)

        if sentence in processed_sentences:
            print(f"  Skip (already processed)")
            continue

        try:
            if "\n" in sentence:
                words = "请根据这条日志构造1条仅改变变量字段的类似数据，只输出日志行：" + sentence
                expanded_sentences = []

                for _ in range(4):
                    response = call_doubao_with_retry(words, api_key, model)
                    answer = response.choices[0].message.content
                    cleaned = clean_llm_response(answer)
                    if cleaned:
                        expanded_sentences.append(cleaned[0])
                    time.sleep(16)

            else:
                words = build_prompt(sentence)
                response = call_doubao_with_retry(words, api_key, model)
                answer = response.choices[0].message.content
                expanded_sentences = clean_llm_response(answer)
                print(expanded_sentences)

                if len(expanded_sentences) < 5:
                    print(f"  WARNING: only {len(expanded_sentences)} valid lines after cleaning (need >=5)")

            """
            if i == 1:
                answer = "Sure, here are 10 similar sentences with variable changes:\n1.服务器的可配置内存大小为100GB，已使用95GB，使用率超过95/100，即将无法运行更多的虚拟机，请将虚拟机不必要的内存配置降低或者进行扩容。\n2.服务器的可配置内存大小为120GB，已使用110GB，使用率超过110/120，即将无法运行更多的虚拟机，请将虚拟机不必要的内存配置降低或者进行扩容。\n3.服务器的可配置内存大小为80GB，已使用75GB，使用率超过75/80，即将无法运行更多的虚拟机，请将虚拟机不必要的内存配置降低或者进行扩容。"
            else:
                answer = ""
            expanded_sentences = answer.split("\n")
            """

        except Exception as e:
            print(f"  FAILED [{sentence_index}]: {type(e).__name__}: {e}")
            log_failed(dataset, sentence_index, sentence, e)
            continue

        with open(filename, "a", newline="", encoding="gbk") as file:
            writer = csv.writer(file)
            row = [str(i), sentence] + expanded_sentences
            writer.writerow(row)


def use_openai_api(words, api_key, model):
    openai.api_key = api_key
    response = openai.ChatCompletion.create(
        model=model,
        messages=[{"role": "user", "content": words}]
    )
    return response

def use_DouBao_api(words, api_key, model):
    client = Ark(api_key=api_key)
    response = client.chat.completions.create(
        model = model,
        messages=[{"role": "user", "content": words}]
    )
    return response


def write_head(filename):
    if os.path.exists(filename) and os.path.getsize(filename) > 0:
        return
    with open(filename, "w", newline="", encoding="gbk") as file:
        writer = csv.writer(file)
        writer.writerow(["index", "原句子", "扩充句子1", "扩充句子2", "扩充句子3", "扩充句子4"])