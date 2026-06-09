import csv
import re
import math
import nltk
from collections import Counter
import pandas as pd
import Select as Se

 
def log_entropy_E(sentences,threshold,dataset,filter,priority_filter='all',max_llm_calls=None):

    if priority_filter not in ('all', 'high_only'):
        raise ValueError(f"priority_filter must be 'all' or 'high_only', got '{priority_filter}'")

    if max_llm_calls is not None:
        if not isinstance(max_llm_calls, int) or max_llm_calls < 0:
            raise ValueError(
                f"max_llm_calls must be a non-negative integer or None, got {max_llm_calls!r}")

    original_sentences = sentences.copy()
    sentences = get_united_sentences(sentences,dataset,filter)


    template_df = pd.read_csv('../log_after_group/'+ dataset +'_template.csv', usecols=['模板', '句子标号'], encoding='GBK')
    templates = template_df['模板'].dropna()
    templates = templates.tolist()

    csv.field_size_limit(10 * 1024 * 1024)

    with open('../log_after_group/'+ dataset +'_template.csv', newline='') as csvfile:
        reader = csv.DictReader(csvfile)
        sentence_numbers = [row['句子标号'].strip('"').split(',') for row in reader]

    template_indices, selection_reasons = get_low_entropy_template(templates, sentences, sentence_numbers, threshold)

    if priority_filter == 'high_only':
        selected_mask = [r['priority'] == 'high' for r in selection_reasons]
    else:
        selected_mask = [True] * len(selection_reasons)

    if max_llm_calls is not None:
        remaining = max_llm_calls
        for i in range(len(selected_mask)):
            if selected_mask[i]:
                if remaining > 0:
                    remaining -= 1
                else:
                    selected_mask[i] = False

    # ---- 风险评分与质量过滤 ----
    risk_scores = []
    risk_reasons_list = []
    auto_quality_flags = []

    for i in range(len(template_indices)):
        tpos = template_indices[i]
        rep_idx_int = int(sentence_numbers[tpos][0])
        origin_sentence = original_sentences[rep_idx_int]
        template = templates[tpos]

        risk_score, risk_reasons = Se.score_candidate_risk(dataset, origin_sentence, template)
        risk_scores.append(risk_score)

        auto_quality_pass, quality_reason = Se.compute_auto_quality_pass(
            dataset, origin_sentence, template, risk_score)
        if quality_reason:
            risk_reasons.append(quality_reason)
        auto_quality_flags.append(auto_quality_pass)

        risk_reasons_list.append('; '.join(risk_reasons) if risk_reasons else '')

    # ---- 构建最终 sentence_indices ----
    sentence_indices = []

    for i, (idx, selected) in enumerate(zip(template_indices, selected_mask)):
        final_pass = selected and auto_quality_flags[i]

        if final_pass:
            sentence_indices.append(sentence_numbers[idx][0])

    with open('../log_after_entropy/'+ dataset +'_expanded_indices_thre_'+str(threshold)+'.csv', 'w', newline='') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(['待扩充句子'])

        writer.writerow(sentence_indices)

    with open('../log_after_entropy/'+ dataset +'_expand_reason.csv', 'w', newline='', encoding='gbk') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(['represent_index', 'origin_sentence', 'template', 'template_size',
                         'variable_count', 'reason', 'priority', 'risk_score', 'risk_reasons',
                         'auto_quality_pass', 'selected_for_llm'])

        for idx, reason_info, selected, risk_score, risk_reasons, quality_pass in zip(
                template_indices, selection_reasons, selected_mask,
                risk_scores, risk_reasons_list, auto_quality_flags):
            rep_idx_str = sentence_numbers[idx][0]
            rep_idx_int = int(rep_idx_str)
            writer.writerow([
                rep_idx_str,
                original_sentences[rep_idx_int],
                templates[idx],
                len(sentence_numbers[idx]),
                templates[idx].count('<*>'),
                reason_info['reason'],
                reason_info['priority'],
                risk_score,
                risk_reasons,
                quality_pass,
                selected,
            ])

 
def get_low_entropy_template(templates,sentences,sentence_numbers,threshold):
    template_indices = []
    selection_reasons = []
    cnt = 0

    for i in range(len(sentence_numbers)):
        template = templates[i]
        reason = None
        entropy_val = None

        if is_english_sentence(template):
            print(templates[i])
            if 'user'not in template:
                words = template.split()

                all_words_have_meaning = all(has_meaning(word) for word in words)

                if all_words_have_meaning:
                    continue


        if len(sentence_numbers[i]) == 1:
            template_indices.append(i)
            reason = 'singleton_template'

        elif '*' not in templates[i]:
            template_indices.append(i)
            reason = 'no_variable_template'

        else:
            indices = [int(idx) for idx in sentence_numbers[i]]
            sentence_list = [sentences[idx] for idx in indices]
            entropy_val = get_sentences_entropy(template, sentence_list)

            if entropy_val <= threshold:
                template_indices.append(i)
                reason = 'low_entropy_template'

        if reason is not None:
            priority = 'high' if reason in ('singleton_template', 'no_variable_template') else 'medium'
            selection_reasons.append({
                'reason': reason,
                'priority': priority,
                'entropy': entropy_val,
            })

    return template_indices, selection_reasons


  
def get_united_sentences(sentences,dataset,filter):
    replaced_sentences = []

    for s in sentences:

        for rgex in filter:
            s = re.sub(rgex, '<*>', s)

        if dataset=='HealthApp':
            s = re.sub(':', ': ', s)
            s = re.sub('=', '= ', s)
            s = re.sub(r'\|', '| ', s)
        if dataset=='Android':
            s = re.sub(r'\(', '( ', s)
            s = re.sub(r'\)', ') ', s)
        if dataset=='Android':
            s = re.sub(':', ': ', s)
            s = re.sub('=', '= ', s)
        if dataset=='HPC':
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

    return replaced_sentences

 
def get_sentences_entropy(template,sentences):

    no_need_indices = []

    new_sentences = [split_sentence(s) for s in sentences]

    max_length = len(max(new_sentences, key=len))

    for i in range(len(new_sentences)):
        new_sentences[i] += ['%'] * (max_length - len(new_sentences[i]))

    new_lists = [[sentence[i] for sentence in new_sentences] for i in range(max_length) if i not in no_need_indices]

    entropies = [calculate_entropy(sentence) for sentence in new_lists]

    average_entropy = sum(entropies) / len(entropies)

    return average_entropy

def split_sentence(s):
    s = re.sub(' +', ' ', s).split(' ')
    return s

 
def calculate_entropy(sentence_list):
    total_count = len(sentence_list)
    counter = Counter(sentence_list)
    entropy = 0.0
    for count in counter.values():
        probability = count / total_count
        entropy -= probability * math.log2(probability)
    return entropy


 
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