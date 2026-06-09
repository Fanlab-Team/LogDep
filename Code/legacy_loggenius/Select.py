#规整生成的扩充句子
import jieba

import csv
import re
import pandas as pd

#固定token提取，进一步加上了IP 地址 带端口 IP URL
def is_variable_token(token):
    if not token:
        return True
    if token == '<*>' or token == '*':
        return True
    if '<*>' in token:
        return True
    if re.search(r'\d+\.\d+\.\d+\.\d+', token):
        return True
    if '://' in token:
        return True
    if re.match(r'^-?\d+$', token):
        return True
    if re.match(r'^\d{2}:\d{2}:\d{2}$', token):
        return True
    if token.startswith('/'):
        return True
    return False


def extract_fixed_tokens_E(sentence, dataset):
    tokens = split_sentence_E_dataset(sentence, dataset)
    return [t for t in tokens if not is_variable_token(t)]


def is_garbage_line_E(line):
    s = line.strip()
    if not s:
        return True
    if s.startswith('#'):
        return True
    if s.startswith('```'):
        return True
    if s.startswith('---'):
        return True
    if s.startswith('**'):
        return True
    if s.startswith('>'):
        return True
    chinese_chars = len(re.findall(r'[一-鿿]', s))
    if chinese_chars > 0 and chinese_chars >= len(s) * 0.3:
        return True
    return False


def clean_numbered_prefix(line):
    return re.sub(r'^\d+[\.\)、．]\s*', '', line).strip()


def get_variable_type(token):
    clean = token.strip('[](),;:\'"')
    if not clean:
        return None
    if clean == '<*>' or clean == '*':
        return 'placeholder'
    if '<*>' in clean:
        return 'placeholder'
    if re.search(r'\d+\.\d+\.\d+\.\d+', clean):
        return 'ip'
    if re.match(r'^-\d+$', clean):
        return 'negative'
    if re.match(r'^\+?\d+$', clean):
        return 'positive'
    if re.match(r'^\d{2}:\d{2}:\d{2}$', clean):
        return 'time'
    if clean.startswith('/'):
        return 'path'
    if '://' in clean:
        return 'url'
    return None

#新增变量类型对比函数
def check_variable_types_match(ori_tokens, gen_tokens):
    for i in range(min(len(ori_tokens), len(gen_tokens))):
        ori_type = get_variable_type(ori_tokens[i])
        if ori_type is None:
            continue
        gen_type = get_variable_type(gen_tokens[i])
        if gen_type is None or ori_type != gen_type:
            return False
    return True

#检查生成日志是否保留了原始日志的固定token,保持结构稳定
def contains_all_fixed_tokens_E(gen_sentence, fixed_tokens, dataset):
    gen_tokens = split_sentence_E_dataset(gen_sentence, dataset)
    for ft in fixed_tokens:
        if ft not in gen_tokens:
            return False
    return True


# Mac安全白名单模板
MAC_SAFE_TEMPLATES = [
    r'\[HID\] \[MT\] MTActuatorManagement::getActuatorRef Calling MTActuatorOpen\(\) outside of MTTrackpadHIDManager\.',
    r'Internal name did not resolve to internal address!',
    r'hciControllerOnline; HID devices\?',
    r'extension com\.apple\.ncplugin\.WorldClock -> \(null\)',
    r'Checking iCDP status for DSID',
]

# Mac专用拒绝关键词（单个关键词命中即拒）
MAC_REJECT_KEYWORDS = [
    'ksfetch', 'GoogleSoftwareUpdateAgent', 'KSUpdateEngine',
    'KSPersistentTicketStore', 'KSOutOfProcessFetcher',
    'NSLayoutConstraint', 'CalendarAgent', 'CalDAV', 'CardDAV',
    'ChromeExistion', 'NSMutableURLRequest',
    'IMMacNotificationCenterManager', 'hibernate_teardown',
]

# Mac专用强拒绝组合规则（需要两个条件同时满足或正则匹配）
MAC_REJECT_COMBO_RULES = [
    (lambda s, t: 'WindowServer' in s and 'authw' in s, 'WindowServer+authw'),
    (lambda s, t: 'com.apple.xpc.launchd' in s and 'WebKit.Networking' in s, 'xpc.launchd+WebKit'),
    (lambda s, t: 'pkd' in s and ('plug-in' in s or '/System/Library' in s), 'pkd+plug-in/path'),
    (lambda s, t: re.search(r'https?://', s) is not None, 'contains URL'),
    (lambda s, t: re.search(r'\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b', s) is not None, 'contains UUID'),
    (lambda s, t: s.count('0x') >= 2, '0x count >=2'),
    (lambda s, t: len(s) > 180, f'length >180'),
    (lambda s, t: t.count('<*>') > 6, 'template <*> >6'),
    (lambda s, t: '/System/Library' in s or '/Applications/' in s, 'system path'),
    (lambda s, t: 'mDNS_RegisterInterface' in s and re.search(r'(?:[0-9A-Fa-f]{1,4}:){2,}[0-9A-Fa-f]{0,4}', s), 'mDNS+IPv6'),
    (lambda s, t: 'payload Data' in s, 'payload Data'),
    (lambda s, t: 'WeChat' in s and 'Arranged view frame' in s, 'WeChat+view frame'),
]


def _count_bracket_excess(s):
    """统计括号、尖括号、大括号的过多数量"""
    score = 0
    for ch, limit in [('(', 4), (')', 4), ('[', 4), (']', 4), ('{', 2), ('}', 2), ('<', 2), ('>', 2)]:
        score += max(0, s.count(ch) - limit)
    return score


def _check_mac_reject(origin_sentence, template=''):
    """检查Mac专用拒绝规则，返回 (is_rejected, reasons)"""
    reasons = []
    for kw in MAC_REJECT_KEYWORDS:
        if kw in origin_sentence:
            reasons.append(f'keyword: {kw}')
    for rule_fn, label in MAC_REJECT_COMBO_RULES:
        if rule_fn(origin_sentence, template):
            reasons.append(label)
    return len(reasons) > 0, reasons


def _check_mac_strong_reject(origin_sentence, template=''):
    """
    检查Mac强拒绝规则，返回 (is_rejected, reasons)。
    比 _check_mac_reject 更严格，包含更多硬拒绝条件。
    """
    reasons = []
    # 关键词检查
    for kw in MAC_REJECT_KEYWORDS:
        if kw in origin_sentence:
            reasons.append(f'strong_reject_keyword: {kw}')
    # 组合规则检查
    for rule_fn, label in MAC_REJECT_COMBO_RULES:
        if rule_fn(origin_sentence, template):
            reasons.append(f'strong_reject: {label}')
    return len(reasons) > 0, reasons


def _check_mac_safe(origin_sentence):
    """检查Mac安全白名单，返回是否命中"""
    for tmpl in MAC_SAFE_TEMPLATES:
        if re.search(tmpl, origin_sentence):
            return True
    return False


def compute_auto_quality_pass(dataset, origin_sentence, template, risk_score):
    """
    统一判断候选是否通过自动质量筛选。
    返回 (auto_quality_pass, reason_string)
    """
    if dataset == 'Mac':
        # 1. 强白名单优先
        if _check_mac_safe(origin_sentence):
            return True, 'mac_whitelist'

        # 2. 强拒绝检查
        is_reject, reasons = _check_mac_strong_reject(origin_sentence, template)
        if is_reject:
            return False, 'strong_reject: ' + '; '.join(reasons)

        # 3. 放宽质量标准：risk<=1 且 len<=220 且 stars<=8
        ok = (risk_score <= 1 and len(origin_sentence) <= 220
              and template.count('<*>') <= 8)
        if ok:
            return True, 'quality_pass'
        else:
            return False, (f'quality_fail: risk={risk_score} '
                           f'len={len(origin_sentence)} '
                           f'stars={template.count("<*>")}')
    else:
        return (risk_score <= 2), 'generic'


def score_candidate_risk(dataset, origin_sentence, template):
    """
    返回 (risk_score, reasons)
    risk_score 0=安全 1=低风险 2=中风险 3+=高风险
    """
    risk_score = 0
    reasons = []

    # ---- 通用规则 ----
    if re.search(r'https?://', origin_sentence):
        risk_score += 2; reasons.append('contains URL')
    if re.search(r'\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b', origin_sentence):
        risk_score += 2; reasons.append('contains UUID')
    if re.search(r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}', origin_sentence):
        risk_score += 2; reasons.append('contains email')
    if re.search(r'[\{\}]', origin_sentence) and (':' in origin_sentence):
        risk_score += 1; reasons.append('contains JSON-like braces')
    if len(re.findall(r'/[A-Za-z0-9_./-]{40,}', origin_sentence)) > 0:
        risk_score += 1; reasons.append('contains very long path')
    if re.search(r'0x[0-9a-fA-F]{6,}', origin_sentence):
        risk_score += 2; reasons.append('contains hex object address')

    if len(origin_sentence) > 220:
        risk_score += 1; reasons.append(f'origin length > 220 ({len(origin_sentence)})')

    star_count = template.count('<*>')
    if star_count > 6:
        risk_score += 1; reasons.append(f'template <*> count > 6 ({star_count})')

    bracket_excess = _count_bracket_excess(origin_sentence)
    if bracket_excess > 4:
        risk_score += 1; reasons.append(f'excessive brackets ({bracket_excess})')

    # ---- Mac专用规则 ----
    if dataset == 'Mac':
        is_reject, mac_reasons = _check_mac_reject(origin_sentence)
        if is_reject:
            risk_score += 3
            reasons.extend(mac_reasons)

        if _check_mac_safe(origin_sentence):
            risk_score = max(0, risk_score - 2)
            reasons.append('Mac whitelist: risk lowered')

    return risk_score, reasons


def _extract_mac_content(sentence):
    """从完整Mac日志行提取 Content 部分（]: 之后的所有内容）"""
    m = re.match(r'^[A-Z][a-z]{2}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2}\s+[\w-]+\s+[\w. ]+\[\d+\]:\s+(.+)', sentence)
    return m.group(1) if m else sentence


def _extract_mac_component(sentence):
    """提取Mac日志的 Component 名称（不含[Pid]）"""
    m = re.match(r'^[A-Z][a-z]{2}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2}\s+[\w-]+\s+([\w.]+)\[\d+\]:', sentence)
    return m.group(1) if m else None


def normalize_content_skeleton(dataset, sentence, content_only=False):
    """
    对句子做归一化。
    若 content_only=True：只比较 Content 部分，数字/hex/IP/UUID统一替换为 <*>。
    返回固定骨架，用于对比原始句和生成句的结构一致性。
    """
    if content_only and dataset == 'Mac':
        s = _extract_mac_content(sentence)
    else:
        s = sentence

    # 统一替换变量为 <*>
    s = re.sub(r'\b\d+(?:\.\d+)?\b', '<*>', s)          # 数字
    s = re.sub(r'0x[0-9a-fA-F]+', '<*>', s)             # 十六进制
    s = re.sub(r'(\d+\.){3}\d+', '<*>', s)               # IPv4
    s = re.sub(r'\ben\d+\b', '<*>', s)                    # 网络接口 en0/en1
    s = re.sub(r'\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b',
               '<*>', s)                                  # UUID
    s = re.sub(r'\(\d+\)', '(<*>)', s)                   # (数字) → 统一
    s = re.sub(r'\(\d+/\d+\)', '(<*>)', s)               # (数字/数字) → 统一
    s = re.sub(r' +', ' ', s).strip()                    # 多余空格归一化
    return s


def validate_generated_log(dataset, origin_sentence, generated_sentence):
    """
    校验生成日志结构是否与原句一致。
    返回 (is_valid, reject_reason)
    """
    # ---- 通用检查 ----
    if is_garbage_line_E(generated_sentence):
        return False, 'garbage/markdown line'

    # 不得包含URL/UUID/long_path/JSON
    if re.search(r'https?://', generated_sentence):
        return False, 'generated log contains URL'
    if re.search(r'\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b', generated_sentence):
        return False, 'generated log contains UUID'
    if len(re.findall(r'/[A-Za-z0-9_./-]{40,}', generated_sentence)) > 0:
        return False, 'generated log contains very long path'
    # JSON检查：排除 Cocoa CGRect 格式 {{0, 0}, {260, 877}}
    if re.search(r'[\{\}]', generated_sentence) and (':' in generated_sentence):
        if not re.search(r'\{\{\d+,\s*\d+\},\s*\{\d+,\s*\d+\}\}', generated_sentence):
            return False, 'generated log contains JSON'

    if len(generated_sentence) > 400:
        return False, 'generated log too long (>400 chars)'

    # ---- Mac专用检查 ----
    if dataset == 'Mac':
        # 必须匹配完整Mac日志格式（允许带点的Component名如 com.apple.WebKit.Networking）
        mac_pattern = r'^[A-Z][a-z]{2}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2}\s+[\w-]+\s+[\w. ]+\[\d+\]:\s+.+'
        if not re.match(mac_pattern, generated_sentence):
            return False, 'not a complete Mac log line'

        # Component 必须一致
        ori_comp = _extract_mac_component(origin_sentence)
        gen_comp = _extract_mac_component(generated_sentence)
        if ori_comp and gen_comp and ori_comp != gen_comp:
            return False, f'Component mismatch: {ori_comp} vs {gen_comp}'

        # ---- Mac强拒绝检查 ----
        for kw in MAC_REJECT_KEYWORDS:
            if kw in generated_sentence:
                return False, f'Mac reject keyword in generated: {kw}'
        for rule_fn, label in MAC_REJECT_COMBO_RULES:
            if rule_fn(generated_sentence, ''):
                return False, f'Mac reject: {label}'

        # ---- Content归一化骨架对比（忽略header变量） ----
        ori_skel = normalize_content_skeleton(dataset, origin_sentence, content_only=True)
        gen_skel = normalize_content_skeleton(dataset, generated_sentence, content_only=True)
        if ori_skel != gen_skel:
            return False, f'skeleton mismatch:\n  ORI: {ori_skel[:120]}\n  GEN: {gen_skel[:120]}'

    return True, 'ok'


def log_select_E(dataset, num, y1, y2):
    expand_sentences = []
    rejected_records = []

    with open('../log_after_gpt/'+ dataset + '_gpt_data.csv', 'r', encoding='gbk') as file:
        reader = csv.reader(file)

        next(reader)

        for row in reader:
            ori_s = row[1]
            expand_sentence = [cell for cell in row[2:] if cell.strip()]

            # ---- 生成结果结构校验 ----
            validated = []
            for sentence in expand_sentence:
                sentence = clean_numbered_prefix(sentence)
                is_valid, reason = validate_generated_log(dataset, ori_s, sentence)
                if is_valid:
                    validated.append(sentence)
                else:
                    rejected_records.append([ori_s, sentence, reason])

            # ---- 距离筛选 ----
            distances = []

            ori_s_token = split_sentence_E_dataset(ori_s,dataset)
            fixed_tokens = extract_fixed_tokens_E(ori_s, dataset)

            for sentence in validated:

                sentence = filter_head_E(sentence)

                # 全行固定token匹配
                if not contains_all_fixed_tokens_E(sentence, fixed_tokens, dataset):
                    # Mac fallback: 只匹配Content部分的固定token，忽略header变量
                    if dataset == 'Mac':
                        ori_content = _extract_mac_content(ori_s) if ori_s else ori_s
                        gen_content = _extract_mac_content(sentence) if sentence else sentence
                        content_fixed = extract_fixed_tokens_E(ori_content, dataset)
                        if not contains_all_fixed_tokens_E(gen_content, content_fixed, dataset):
                            continue
                    else:
                        continue

                sentence_token = split_sentence_E_dataset(sentence,dataset)

                if not check_variable_types_match(ori_s_token, sentence_token):
                    continue

                if len(sentence_token) < y1*len(ori_s_token) or len(sentence_token) > y2*len(ori_s_token):
                    continue

                distance = get_distance_E_dataset(sentence_token, ori_s_token)
                distances.append((sentence, distance))

            if not distances:
                continue

            distances.sort(key=lambda x: x[1])

            for i in range(num):
                if i >= len(distances):
                    break
                expand_sentences.append(distances[i][0])


    with open('../log_after_select/'+ dataset + '_select_top_'+str(num)+'.csv', 'w', encoding='gbk', newline='') as file:
        writer = csv.writer(file)

        for sentence in expand_sentences:
            writer.writerow([sentence])

    # ---- 写入被拒绝的生成日志 ----
    if rejected_records:
        with open('../log_after_gpt/' + dataset + '_gpt_rejected.csv', 'w', encoding='gbk', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['origin_sentence', 'generated_sentence', 'reject_reason'])
            for rec in rejected_records:
                writer.writerow(rec)

    with open('../logs/'+dataset+'_2k.logs', 'r') as f:
        original_content = f.read()

    with open('../new_dataset/'+dataset+'_new_dataset.txt', 'w') as f:
        f.write(original_content)
        for sentence in expand_sentences:
            f.write('\n'+sentence)

def get_distance_E_dataset(s1_token_list, s2_token_list):
    distance = 0

    for i in range(min(len(s1_token_list),len(s2_token_list))):
        token1 = s1_token_list[i]
        token2 = s2_token_list[i]
        if token1 != token2:
            distance += 1

    distance += max(len(s1_token_list),len(s2_token_list)) - min(len(s1_token_list),len(s2_token_list))

    return distance

def get_dataset_regex(dataset):
    if dataset == 'Apache':
        return [
            r'\[[A-Z][a-z]{2}\s+[A-Z][a-z]{2}\s+\d{2}\s+\d{2}:\d{2}:\d{2}\s+\d{4}\]',
            r'\[(notice|error|warn|debug|info|crit|alert|emerg)\]',
            r'\[client\s+\d{1,3}(?:\.\d{1,3}){3}\]',
            r'\d{1,3}(?:\.\d{1,3}){3}',
            r'(?<=child )\d+',
            r'(?<=slot )\d+',
            r'(?<=state )\d+',
            r'(?<=init )\d+\s+-?\d+',
            r'/[A-Za-z0-9_./-]+',
            r'workers2\.properties',
            r'Directory index forbidden by rule',
            r'jk2_init\(\) Found child',
            r'jk2_init\(\) Can\'t find child',
            r'workerEnv\.init\(\) ok',
            r'mod_jk child workerEnv in error state',
            r'mod_jk child init',
            r'mod_proxy child init',
            r'mod_rewrite child init',
            r'mod_headers child init',
        ]
    elif dataset == 'OpenSSH':
        return [
            r'(\d+\.){3}\d+',
            r'([\w-]+\.){2,}[\w-]+',
            r'\d{2}:\d{2}:\d{2}',
            r'(?<=sshd\[)\d+(?=\])',
            r'(?<=port )\d+',
            r'(?<=password for invalid user )\S+(?= from)',
            r'(?<=password for )\S+(?= from)',
            r'(?<=[Ii]nvalid user )\S+(?= from)',
            r'(?<=[Ii]nvalid user )\S+(?= \[)',
            r'(?<=for user )\S+',
            r'(?<=failures for )\S+(?= \[)',
            r'(?<=user=)\S+',
        ]
    elif dataset == 'OpenStack':
        return [r'((\d+\.){3}\d+,?)+', r'/.+?\s ', r'\d+']
    elif dataset == 'Zookeeper':
        return [
            r'(/|)(\d+\.){3}\d+(:\d+)?',
            r'\d{4}-\d{2}-\d{2}',
            r'\d{2}:\d{2}:\d{2},\d{3}',
            r'(?<=@)[0-9a-fA-F]+',
            r'0x[0-9a-fA-F]+',
            r'(?<=Thread-)\d+',
            r'(?<=myid=)\d+',
            r'(?<=sid:)\d+',
            r'(?<=cport:)-?\d+',
            r'(?<=snapshot\.b)[0-9a-fA-F]+',
        ]
    elif dataset == 'Android':
        return [
            # 完整时间戳
            r'\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}\.\d+',
            # Pid Tid Level 模式
            r'\s+\d+\s+\d+\s+[A-Z]\s+',
            # 十六进制
            r'0x[0-9a-fA-F]+',
            # 标识符@hex
            r'\b[A-Za-z0-9_.$/-]+@[0-9a-fA-F]+\b',
            # 组件名后跟冒号
            r'\b[A-Za-z0-9_.$/-]+:\s*',
            # 布尔和 null
            r'\b(?:true|false|null)\b',
            # 浮点数
            r'\b\d+\.\d+\b',
            # 毫秒
            r'\d+ms',
            # 包名/类名
            r'com\.[\w\.:\-/]+',
            # 常见数字上下文
            r'(?<=uid=)\d+',
            r'(?<=pid=)\d+',
            r'(?<=pid )\d+',
            r'(?<=id=)\d+',
            r'(?<=width:\[)\d+(?=\])',
            r'(?<=height:\[)\d+(?=\])',
            r'(?<=minLayer:\[)\d+(?=\])',
            r'(?<=maxLayer:\[)\d+(?=\])',
            r'(?<=rot:\[)-?\d+(?=\])',
            r'(?<=x=)\d+\.\d+',
            r'(?<=y=)\d+\.\d+',
            r'(?<=vel=)\d+\.\d+',
            r'(?<=target=)\d+\.\d+',
            r'(?<=Translation=)-?\d+\.\d+',
            # Android 动态字段专用正则
            r'AppWindowToken\{[0-9a-fA-F]+',
            r'Token\{[0-9a-fA-F]+',
            r'ActivityRecord\{[0-9a-fA-F]+',
            r'Alarm\{[0-9a-fA-F]+',
            r'PendingIntent\{[0-9a-fA-F]+:',
            r'PendingIntentRecord\{[0-9a-fA-F]+',
            r'BinderProxy@[0-9a-fA-F]+',
            r'0x[0-9a-fA-F]+',
            r'lock=\d+',
            r'uid=\d+',
            r'pid=\d+',
            r'\bu\d+\b',
            r't\d+\b',
            r'when\s+\d+',
            r'type\s+\d+',
            r'repeatInterval\s*=\s*\d+',
            r'listenerTag\s*=\s*[A-Za-z0-9_]+',
            r'flags=\d+',
            r'flags=0x[0-9a-fA-F]+',
            r'name=[A-Za-z0-9_.$/-]+',
            r'ws=null',
            r'android\.intent\.action\.[A-Z_]+',
            r'com\.[A-Za-z0-9_.$/]+',
            r'[A-Za-z0-9_.$/]+Activity',
            r'[A-Za-z0-9_.$/]+UI',
        ]
    elif dataset == 'Mac':
        return [
            r'(\d+\.){3}\d+',
            r'([0-9A-Fa-f]{1,4}:){2,}[0-9A-Fa-f]{0,4}',
            r'\d{2}:\d{2}:\d{2}(?:\.\d+)?',
            r'(?<=\[)\d+(?=\])',
            r'0x[0-9a-fA-F]+',
            r'(?<=port = )\d+',
            r'(?<=port: )\d+',
            r'(?<=Local port: )\d+',
            r'(?<=Remote port: )\d+',
            r'(?<=uid: )\d+',
            r'(?<=pid: )\d+',
            r'(?<=pid )\d+',
            r'\d+ms',
            r'\d+ seconds',
            r'\d+\.\d+',
            r'(?<=Seq: )\d+',
            r'(?<=Ack: )\d+',
            r'(?<=Win size: )\d+',
            r'(?<=taskID\[)\d+(?=\])',
            r'/[A-Za-z0-9_\-./]+',
            r'\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\b',
            r'calvisitor-\d+-\d+-\d+-\d+',
            r'airbears2-\d+-\d+-\d+-\d+',
            r'authorMacBook-Pro',
            r'\d{4}/\d{2}/\d{2}',
            r'\d{4}-\d{2}-\d{2}',
            r'\d{2}:\d{2}:\d{2}\.\d{3}',
            r'(?<=llFriendUIN = )\*+\d+',
            r'(?<=llFriendUIN = )\d+',
            r'(?<=act )\d+',
            r'(?<=act )\d+(?=,)',
            r'(?<=inact )\d+',
            r'(?<=inact )\d+(?=,)',
            r'(?<=anon )\d+',
            r'(?<=throt )\d+',
            r'(?<=spec )\d+',
            r'(?<=wire )\d+',
            r'(?<=wireinit )\d+',
            r'(?<=wired_pages )\d+',
            r'(?<=free_pages )\d+',
            r'(?<=active_pages )\d+',
            r'(?<=inactive_pages )\d+',
            r'(?<=speculative_pages )\d+',
            r'(?<=cleaned_pages )\d+',
            r'(?<=compressor_pages )\d+',
            r'(?<=bmccmd )\d+',
            r'(?<=framecnt )\d+',
            r'(?<=BAbitmap\(0-3\) )[\d ]+',
            r'cup2hreq=[0-9a-fA-F]+',
            r'cup2key=\d+:\d+',
            r'https?://\S+',
            r'[0-9a-fA-F]{16,}',
            r'(?<=<NSMutableURLRequest: )0x[0-9a-fA-F]+',
            r'(?<== )\d+',
            r'(?<=: )\d+',
        ]
    elif dataset == 'BGL':
        return [
            r'\b\d{10}\b',
            r'\d{4}\.\d{2}\.\d{2}',
            r'\d{4}-\d{2}-\d{2}-\d{2}\.\d{2}\.\d{2}\.\d+',
            r'R\d{2}-M\d-N[0-9A-F]-[CI]:J\d{2}-U\d{2}',
            r'(\d+\.){3}\d+:\d+',
            r'(\d+\.){3}\d+',
            r'0x[0-9a-fA-F]+',
            r'core\.\d+',
            r'(?<=sym )\d+',
            r'(?<=mask )0x[0-9a-fA-F]+',
            r'(?<=at )0x[0-9a-fA-F]+',
            r'(?<=treeaddr )\d+',
            r'(?<=cpu )\d+',
            r'(?<=rank )\d+',
            r'(?<=symbol )\d+',
            r'(?<=bit )\d+',
            r'(?<=Message code )\d+',
            r'(?<=is not )\d+',
            r'\d+(?= double-hummer alignment exceptions)',
            r'\d+(?= ddr errors)',
            r'(?<=instruction address: )0x[0-9a-fA-F]+',
            r'(?<=data address: )0x[0-9a-fA-F]+',
            r'(?<=exception syndrome register: )0x[0-9a-fA-F]+',
        ]
    elif dataset == 'Hadoop':
        return [
            r'\d{4}-\d{2}-\d{2}',
            r'\d{2}:\d{2}:\d{2},\d{3}',
            r'application_\d+_\d+',
            r'appattempt_\d+_\d+_\d+',
            r'job_\d+_\d+',
            r'attempt_\d+_\d+_[mr]_\d+_\d+',
            r'container_\d+_\d+_\d+_\d+',
            r'(\d+\.){3}\d+:\d+',
            r'(\d+\.){3}\d+',
            r'hdfs://\S+',
            r'/[A-Za-z0-9_\-./]+',
            r'memory:\d+',
            r'vCores:-?\d+',
            r'(?<=ask=)\d+',
            r'(?<=release= )\d+',
            r'(?<=newContainers=)\d+',
            r'(?<=finishedContainers=)\d+',
            r'(?<=knownNMs=)\d+',
            r'(?<=PendingReds:)\d+',
            r'(?<=ScheduledMaps:)\d+',
            r'(?<=ScheduledReds:)\d+',
            r'(?<=AssignedMaps:)\d+',
            r'(?<=AssignedReds:)\d+',
            r'(?<=CompletedMaps:)\d+',
            r'(?<=CompletedReds:)\d+',
            r'(?<=ContAlloc:)\d+',
            r'(?<=ContRel:)\d+',
            r'(?<=HostLocal:)\d+',
            r'(?<=RackLocal:)\d+',
            r'(?<=progress=)\d+\.\d+',
            r'[\w-]+\.fareast\.corp\.microsoft\.com',
            r'(?<=port )\d+',
            r'(?<=keyId: )-?\d+',
            r'(?<=cluster_timestamp: )\d+',
            r'(?<=attemptId: )\d+',
            r'Input size for job job_\d+_\d+ = \d+',
            r'(?<=Number of splits = )\d+',
            r'Number of reduces for job job_\d+_\d+ = \d+',
        ]
    elif dataset == 'HPC':
        return [
            r'^\d+',
            r'\b\d{10}\b',
            r'SCSI-WWID:[0-9A-Fa-f:]+',
            r'Interconnect-\d[NT]\d+',
            r'node-\[\d+-\d+\]',
            r'node-\[[\d\\ ]+\]',
            r'node-D\[\d+\\ \d+\]',
            r'node--tc\d+',
            r'node-D\d+',
            r'node-C\d+',
            r'node-\d+',
            r'0x[0-9a-fA-F]+',
            r'HWID=\d+',
            r'command \d+',
            r'storage\d+',
            r'ambient=\d+',
            r'Temperature \(\d+C\)',
            r'Fan speeds: \d+',
            r'network \d+\.\d+\.\d+\.\d+',
            r'alt0',
            r'root volume \w+',
        ]
    elif dataset == 'HealthApp':
        return [
            # 时间戳
            r'\d{8}-\d{1,2}:\d{1,2}:\d{1,2}:\d+',
            # 组件名: |Step_XXX|
            r'\|Step_[A-Za-z0-9_]+\|',
            # PID 数字
            r'\|\d+\|',
            # 毫秒级时间戳
            r'\d{10,13}',
            # 步数详情 ##链
            r'\d+##\d+##\d+##\d+##\d+##\d+',
            # 常见数值字段
            r'totalCalories=\d+',
            r'totalAltitude=\d+',
            r'totalSteps=\d+',
            r'onStandStepChanged \d+',
            r'onExtend:\d+ \d+ \d+ \d+',
            r'REPORT : \d+ \d+ \d+ \d+',
            # Intent action
            r'action:android\.intent\.action\.[A-Z_]+',
            r'android\.intent\.action\.[A-Z_]+',
            # 步数存储
            r'getTodayTotalDetailSteps = \d+(##\d+)+',
            r'setTodayTotalDetailSteps=\d+(##\d+)+',
            # bool 值
            r'\btrue\b',
            r'\bfalse\b',
            r'obj=(true|false)',
            r'data=(true|false)',
            # 常见数字上下文
            r'(?<=begin:)\d+',
            r'(?<=end:)\d+',
            r'(?<=size = )\d+',
            r'(?<=totalTime = )\d+',
            r'(?<=type = )\d+',
            r'(?<=Calories:)\d+',
            r'(?<=Floor:)\d+',
            r'(?<=Distance:)\d+',
            r'(?<=steps)\d+',
            r'(?<=setGoalNotifiShownRecord )\d+',
            r'(?<=mLastReport)\d+',
            r'(?<=appSynTimes is )\d+',
            r'(?<=bWrite )true',
            r'(?<=bWrite )false',
            r'(?<=getStepCounterStatus= )true',
            r'(?<=getStepCounterStatus= )false',
        ]
    elif dataset == 'Windows':
        return [
            r'\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2},',
            r'\b[0-9a-fA-F]{8}@\d{4}/\d{1,2}/\d{1,2}:\d{2}:\d{2}:\d{2}\.\d+',
            r'\b[0-9a-fA-F]{8}\b',
            r'(?<=Session: )\d+_\d+',
            r'0x[0-9a-fA-F]+',
            r'CBS_E_[A-Z_]+',
            r'E_[A-Z_]+',
            r'@0x[0-9a-fA-F]+',
            r'[A-Za-z]:\\[^\s,]+',
            r'[A-Za-z0-9_.-]+\.(dll|sqm|cab|mum|manifest|cat)',
            r'KB\d+',
            r'Package_for_KB\d+~[A-Za-z0-9~._-]+',
            r'\b\d+(?:\.\d+){2,4}\b',
            r'(?<=ApplicableState: )\d+',
            r'(?<=CurrentState:)\d+',
            r'(?<=flags: )0x[0-9a-fA-F]+',
            r'(?<=flags = )[0-9a-fA-F]+',
            r'(?<=seq )\d+',
            r'(?<=call )\d+',
            r'(?<=phase = )\d+',
            r'(?<=handle @)0x[0-9a-fA-F]+',
            r'(?<=result )0x[0-9a-fA-F]+',
            r'(?<=Queued )\d+(?= file)',
            r'(?<=older than )\d+(?= days)',
            r'(?<=CSI Store )\d+',
            r'\(0x[0-9a-fA-F]+\)',
            r'(?<=version )\d+(?:\.\d+)+',
        ]
    elif dataset == 'Thunderbird':
        return [
            r'^\d{10}',
            r'\b\d{4}\.\d{2}\.\d{2}\b',
            r'\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2}\s+\d{2}:\d{2}:\d{2}\b',
            r'\b(?:dn|cn|bn|en)\d+\b',
            r'\b[a-d]admin\d+\b',
            r'\beadmin\d+\b',
            r'\btbird-[A-Za-z0-9_-]+\b',
            r'#\d+#',
            r'\b(?:src|local)@[A-Za-z0-9_.#-]+\b',
            r'\b[A-Za-z0-9#_-]+/[A-Za-z0-9#_-]+\b',
            r'(?<=\[)\d+(?=\])',
            r'uid=\d+',
            r'\(uid=\d+\)',
            r'(\d+\.){3}\d+',
            r'\b[0-9a-fA-F]{2}(?::[0-9a-fA-F]{2}){5}\b',
            r'\[Thunderbird_[A-Z]\d+\]',
            r'/[A-Za-z0-9_./-]+',
            r'\[[A-Za-z0-9_.-]+\.c:\d+\]',
            r'\bj[A-Za-z0-9]{10,}\b',
            r'msgid=<[^>]+>',
            r'(?<=size=)\d+',
            r'(?<=class=)\d+',
            r'(?<=nrcpts=)\d+',
            r'(?<=pri=)\d+',
            r'(?<=delay=)\d{2}:\d{2}:\d{2}',
            r'(?<=xdelay=)\d{2}:\d{2}:\d{2}',
            r'(?<=dsn=)\d+\.\d+\.\d+',
            r'\(\d+/\d+\)',
            r'relay=\[[^\]]+\]',
            r'relay=#[0-9]+#@[A-Za-z0-9_.-]+',
            r'(?<=stratum )\d+',
            r'(?<=on )(\d+\.){3}\d+',
            r'(?<=for )(\d+\.){3}\d+',
            r'(?<=from )[0-9a-fA-F]{2}(?::[0-9a-fA-F]{2}){5}',
            r'(?<=via )eth\d+',
            r'network [A-Za-z0-9_]+',
            r'(?<=pid=)\d+',
            r'(?<=from=)(\d+\.){3}\d+',
            r'(?<=acpi_id\[)0x[0-9a-fA-F]+(?=\])',
            r'(?<=lint\[)0x[0-9a-fA-F]+(?=\])',
            r'(?<=apic_id )\d+',
            r'(?<=address )0x[0-9a-fA-F]+',
            r'(?<=GSI )\d+-\d+',
            r'(?<=bus_irq )\d+',
            r'(?<=global_irq )\d+',
            r'(?<=bus )\d{2}',
            r'(?<=bus )\d+',
            r'(?<=irq )\d+',
            r'(?<=version )\d+',
            r'(?<=hash table of )\d+(?= buckets)',
            r'(?<=ioctl32\(fdisk: )\d+(?=\))',
            r'fd\(\d+\)',
            r'cmd\([0-9a-fA-F]+\)',
            r'arg\([0-9a-fA-F]+\)',
            r'(?<=LD )\d+',
            r'(?<=RAID)\d+',
            r'(?<=Rev: )[A-Za-z0-9]+',
            r'(?<=Release Date: )[A-Za-z]{3}\s+[A-Za-z]{3}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2}\s+[A-Z]{3}\s+\d{4}',
            r'(?<=scsi channel )\d+',
            r'\[Phy \d+\]',
            r'\[virtual\]',
            r'(?<=Temperature changed )-?\d+',
            r'(?<=Celsius to )-?\d+',
            r'\$Id: [^$]+\$',
            r'(?<=v )\d+(?:\.\d+)+',
            r'\bsda\d+\b',
            r'(?<=Received SNMP packet\(s\) )\d+',
            r'(?<=START: tftp pid= )\d+',
            r'\d+Kbytes',
            r'0x[0-9a-fA-F]+',
            r'(?<=port )\d+',
        ]
    elif dataset == 'Spark':
        return [
            r'\d{2}/\d{2}/\d{2}\s+\d{2}:\d{2}:\d{2}',
            r'(\d+\.){3}\d+',
            r'\bmesos-slave-\d+\b',
            r'akka\.tcp://[^ \]]+',
            r'spark://[^ \]]+',
            r'hdfs://[^ ]+',
            r'/[A-Za-z0-9_./=-]+',
            r'application_\d+_\d+',
            r'\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b',
            r'(?<=port )\d+',
            r'(?<=on port )\d+',
            r'(?<=on )\d+(?=\.)',
            r'(?<=:)\d+(?=\])',
            r'(?<=executor ID )\d+',
            r'(?<=Got assigned task )\d+',
            r'(?<=Running task )\d+(?:\.\d+)?',
            r'(?<=Finished task )\d+(?:\.\d+)?',
            r'(?<=stage )\d+(?:\.\d+)?',
            r'(?<=TID )\d+',
            r'rdd_\d+_\d+',
            r'broadcast_\d+',
            r'broadcast_\d+_piece\d+',
            r'Block broadcast_\d+',
            r'Block broadcast_\d+_piece\d+',
            r':\d+\+\d+',
            r'\d+(?:\.\d+)?\s*(?:B|KB|MB|GB|Kbytes)',
            r'(?<=capacity )\d+(?:\.\d+)?\s*GB',
            r'(?<=estimated size )\d+(?:\.\d+)?\s*(?:B|KB|MB|GB)',
            r'(?<=free )\d+(?:\.\d+)?\s*(?:B|KB|MB|GB)',
            r'(?<=total = )-?\d+',
            r'(?<=boot = )-?\d+',
            r'(?<=init = )-?\d+',
            r'(?<=finish = )-?\d+',
            r'(?<=\.) \d+ bytes result sent to driver',
            r'(?<=Finished task )\d+\.\d+',
            r'\d+ bytes result sent to driver',
            r'Set\([^)]+\)',
            r'\[[A-Z, ]+\]',
        ]
    elif dataset == 'Proxifier':
        return [
            r'\[\d{2}\.\d{2}\s+\d{2}:\d{2}:\d{2}\]',
            r'\b[A-Za-z0-9_.-]+\.exe(?: \*64)?\b',
            r'(\d+\.){3}\d+',
            r'\b(?:[A-Za-z0-9-]+\.)+[A-Za-z]{2,}:\d+\b',
            r'\b(?:\d+\.){3}\d+:\d+\b',
            r'\b(?:[A-Za-z0-9-]+\.)+[A-Za-z]{2,}\b',
            r'(?<=through proxy )[A-Za-z0-9_.-]+:\d+',
            r'(?<=proxy )[A-Za-z0-9_.-]+:\d+',
            r'(?<=:)\d+\b',
            r'\d+\s+bytes\s+\([0-9.]+\s*(?:KB|MB|GB)\)',
            r'\d+\s+bytes\s+sent',
            r'\d+\s+bytes\s+received',
            r'\d+\s+bytes',
            r'\(\d+(?:\.\d+)?\s*(?:B|KB|MB|GB)\)',
            r'lifetime\s+<\d+\s+sec',
            r'lifetime\s+\d{2}:\d{2}:\d{2}',
            r'lifetime\s+\d{2}:\d{2}',
            r'lifetime\s+\d{1,3}:\d{2}',
            r'\bHTTPS\b',
            r'\bSOCKS5\b',
            r'\bHTTP\b',
            r'\bopen through proxy\b',
            r'\bclose\b',
            r'\berror\b',
            r'\b[A-Za-z0-9_-]+:\d+\b',
            r'\b\d{1,3}(?:\.\d{1,3}){3}:\d+\b',
            r'Could not connect to proxy [A-Za-z0-9_.-]+:\d+',
            r'Could not resolve [A-Za-z0-9_.-]+ error \d+',
            r'error \d+',
            r'A connection request was canceled before the completion',
            r'Could not connect through proxy [A-Za-z0-9_.-]+:\d+',
            r'Proxy closed the connection unexpectedly',
        ]
    elif dataset == 'Linux':
        return [
            r'\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2}\s+\d{2}:\d{2}:\d{2}\b',
            r'(?<=\[)\d+(?=\])',
            r'(\d+\.){3}\d+:\d+',
            r'(\d+\.){3}\d+',
            r'(?<=rhost=)\S+',
            r'(?<=user=)\S+',
            r'uid=\d+',
            r'euid=\d+',
            r'[A-Za-z0-9_.-]+\.(?:com|net|org|edu|cn|kr|jp|tw|hk|de|fr|it|au|uk)\S*',
            r'\d{1,3}(?:-\d{1,3}){3}\.[A-Za-z0-9_.-]+',
            r'\b(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2}\s+\d{2}:\d{2}:\d{2}\s+\d{4}\b',
            r'(?<=Normal zone: )\d+(?= pages)',
            r'(?<=HighMem zone: )\d+(?= pages)',
            r'(?<=DMA zone: )\d+(?= pages)',
            r'(?<=LIFO batch:)\d+',
            r'(?<=totalpages: )\d+',
            r'CPU#\d+',
            r'(?<=CPU )\d+(?= irqstacks)',
            r'\d+\.\d+(?= MHz)',
            r'\d+\.\d+(?= BogoMIPS)',
            r'(?<=stepping )\d+',
            r'(?<=L2 cache: )\d+K',
            r'(?<=hard=)[0-9a-fA-F]+',
            r'(?<=soft=)[0-9a-fA-F]+',
            r'(?<=to )[0-9a-fA-F]+(?=\.)',
            r'\[[0-9a-fA-F]{4}/[0-9a-fA-F]{4}\]',
            r'\b[0-9a-fA-F]{4}:\d{2}:\d{2}\.\d\b',
            r'(?<=Subsystem revision )\d+',
            r'(?<=protocol family )\d+',
            r'(?<=Total HugeTLB memory allocated, )\d+',
            r'(?<=mice\.c\()\d+(?=\))',
            r'\(uid=\d+\)',
            r'LOGIN\(uid=\d+\)',
            r'(?<=with \[)\d+(?=\])',
            r'\[\d+\]',
        ]
    elif dataset == 'HDFS':
        return [
            r'blk_-?\d+',
            r'\b\d{1,3}(?:\.\d{1,3}){3}(?::\d+)?\b',
            r'/[A-Za-z0-9_./-]+',
            r'task_\d+_\d+_[mr]_\d+_\d+',
            r'part-\d+',
            r'(?<=size )\d+',
            r'(?<=PacketResponder )\d+',
            r'PacketResponder \d+ for block',
            r'Received block',
            r'Receiving block',
            r'Served block',
            r'Got exception while serving',
            r'Verification succeeded for',
            r'Deleting block',
            r'NameSystem\.addStoredBlock',
            r'NameSystem\.allocateBlock',
            r'NameSystem\.delete',
            r'blockMap updated',
            r'is added to',
            r'is added to invalidSet of',
        ]
    else:
        return []


def split_sentence_E_dataset(s,dataset):

    filter = get_dataset_regex(dataset)

    for rgex in filter:
        s = re.sub(rgex, '<*>', s)

    if dataset == 'HealthApp':
        s = re.sub(':', ': ', s)
        s = re.sub('=', '= ', s)
        s = re.sub(r'\|', '| ', s)
    if dataset == 'Android':
        s = re.sub(r'\(', '( ', s)
        s = re.sub(r'\)', ') ', s)
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
    s = re.sub(' +', ' ', s).split(' ')

    return s


def filter_head_E(s):

    patterns = [
        r'^\d+\.\s*',
    ]

    for pattern in patterns:
        s = re.sub(pattern, '', s)

    s = s.strip()

    return s


def extract_fixed_tokens_C(sentence):
    tokens = split_sentence_C_dataset(sentence)
    fixed = []
    for t in tokens:
        if is_variable_token(t):
            continue
        if t.startswith('<') and t.endswith('>'):
            continue
        fixed.append(t)
    return fixed


def is_garbage_line_C(line):
    s = line.strip()
    if not s:
        return True
    if s.startswith('#'):
        return True
    if s.startswith('```'):
        return True
    if s.startswith('---'):
        return True
    if s.startswith('**'):
        return True
    if s.startswith('>'):
        return True
    return False


def contains_all_fixed_tokens_C(gen_sentence, fixed_tokens):
    gen_tokens = split_sentence_C_dataset(gen_sentence)
    for ft in fixed_tokens:
        if ft not in gen_tokens:
            return False
    return True


def log_select_C(dataset,num,y1,y2):

    expand_sentences = []

    with open('../log_after_gpt/' + dataset + '_gpt_data.csv', 'r', encoding='gbk') as file:
        reader = csv.reader(file)


        next(reader)


        for row in reader:
            ori_s = row[1]
            expand_sentence = [cell for cell in row[2:] if cell.strip()]

            distances = []

            ori_s_token = split_sentence_C_dataset(ori_s)
            fixed_tokens = extract_fixed_tokens_C(ori_s)

            for sentence in expand_sentence:

                sentence = clean_numbered_prefix(sentence)

                if is_garbage_line_C(sentence):
                    continue

                sentence = filter_head_C(sentence)

                if not contains_all_fixed_tokens_C(sentence, fixed_tokens):
                    continue

                sentence_token = split_sentence_C_dataset(sentence)

                if not check_variable_types_match(ori_s_token, sentence_token):
                    continue

                if len(sentence_token) < y1 * len(ori_s_token) or len(sentence_token) > y2 * len(ori_s_token):
                    continue

                distance = get_distance_C_dataset(sentence_token, ori_s_token)
                distances.append((sentence, distance))

            if not distances:
                continue

            distances.sort(key=lambda x: x[1])

            for i in range(num):
                if i >= len(distances):
                    break
                expand_sentences.append(distances[i][0])

    with open('../log_after_select/' + dataset + '_select_top_' + str(num) + '.csv', 'w', encoding='gbk',
              newline='') as file:
        writer = csv.writer(file)

        for sentence in expand_sentences:
            writer.writerow([sentence])

    with open('../logs/' + dataset + '_1k.logs', 'r') as f:
        original_content = f.read()

    with open('../new_dataset/' + dataset + '_new_dataset.txt', 'w') as f:
        f.write(original_content)
        for sentence in expand_sentences:
            f.write('\n' + sentence)

def split_sentence_C_dataset(s):
    pattern_comma = r','
    repl_comma = '，'
    pattern_left_bracket = r'[（({｛【[]'
    repl_left_bracket = '<'
    pattern_right_bracket = r'[）)}｝】\]]'
    repl_right_bracket = '>'
    s = re.sub(pattern_comma, repl_comma, s)
    s = re.sub(pattern_left_bracket, repl_left_bracket, s)
    s = re.sub(pattern_right_bracket, repl_right_bracket, s)

    filter = [r'(\d+\.\d+\.\d+\.\d+)', r'\(([^\(\)]+)\)', r'（([^（）]+)）', r'\[([^\[\]]+)\]', r'\<([^\<\>]+)\>',
              r'【([^【】]+)】', r'\{([^\{\}]+)\}', r'｛([^｛｝]+)｝', r'<>']

    s = s.rstrip()

    for rgex in filter:
        while re.search(rgex, s):
            s = re.sub(rgex, '*', s)


    pattern = r"(虚拟机列表：).*"
    replacement = r"\1*"
    s = re.sub(pattern, replacement, s, flags=re.DOTALL)

    pattern = r"(具体原因如下：).*"
    replacement = r"\1*"
    s = re.sub(pattern, replacement, s, flags=re.DOTALL)

    pattern = r"(请尽快按照下列方式进行处理：).*"
    replacement = r"\1*"
    s = re.sub(pattern, replacement, s, flags=re.DOTALL)

    pattern = r"(请联系供应商进行技术支持。).*"
    replacement = r"\1*"
    s = re.sub(pattern, replacement, s, flags=re.DOTALL)

    pattern = r"(请做以下检查：).*"
    replacement = r"\1*"
    s = re.sub(pattern, replacement, s, flags=re.DOTALL)

    pattern = r"(建议： ).*"
    replacement = r"\1*"
    s = re.sub(pattern, replacement, s, flags=re.DOTALL)

    pattern = r"(请检查： ).*"
    replacement = r"\1*"
    s = re.sub(pattern, replacement, s, flags=re.DOTALL)

    pattern = r"(可能原因\d+：).*"
    replacement = r"*"
    s = re.sub(pattern, replacement, s, flags=re.DOTALL)

    pattern = r'([\u4e00-\u9fff\u3000-\u303f\uff01-\uff0f\uff1a-\uff20\uff3b-\uff40\uff5b-\uff65℃]+|[a-zA-Z0-9\s!"#$%&\'()*+,\-./:;<=>?@\[\\\]^_`{|}~]+)'
    parts = re.findall(pattern, s)
    new_parts = []

    for part in parts:
        if re.match(r'[\u4e00-\u9fff\u3000-\u303f\uff01-\uff0f\uff1a-\uff20\uff3b-\uff40\uff5b-\uff65℃]+', part):
            new_parts.extend(jieba.lcut(part))
        else:
            temp_parts = re.findall(r'\s|[^\s]+', part)
            for temp_part in temp_parts:
                if 'f*' in temp_part:
                    new_parts.append(temp_part)
                elif '_*' in temp_part:
                    new_parts.append(temp_part)
                elif 's*' in temp_part:
                    new_parts.append(temp_part)


                else:
                    sub_parts = re.findall(r'\*|[^\*]+', temp_part)
                    new_parts.extend(sub_parts)

    return new_parts


def get_distance_C_dataset(s1_token_list, s2_token_list):
    distance = 0


    for i in range(min(len(s1_token_list),len(s2_token_list))):
        token1 = s1_token_list[i]
        token2 = s2_token_list[i]
        if token1 != token2:
            distance += 1

    distance += max(len(s1_token_list),len(s2_token_list)) - min(len(s1_token_list),len(s2_token_list))

    return distance

def filter_head_C(s):


    patterns = [
        r'^\d+\.\s*',
        r'^告警:\s*',
        r'^告警：\s*',
        r'^警告:\s*',
        r'^警告：\s*',
        r'^告警\d+\:\s*',
        r'^告警\d+\：\s*',
    ]

    for pattern in patterns:
        s = re.sub(pattern, '', s)

    return s