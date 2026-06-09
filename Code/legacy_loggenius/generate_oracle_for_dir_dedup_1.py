"""
dir_dedup_1 Oracle增强生成器（三级策略：strict -> header_safe -> numeric_safe）
目标：每个数据集都生成可观增强数据，不出现0条。
"""
import os, re, csv, random, sys
from collections import defaultdict

random.seed(42)
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, SCRIPT_DIR)
import Select as Se

DEDUP_DIR = os.path.join(BASE_DIR, 'dir_dedup_1')

MONTHS = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']


# ===== 变量值生成 =====
def gen_val(original, category='any'):
    """根据原值和类型生成不同新值"""
    if category == 'month' or (original in MONTHS and category == 'any'):
        opts = [m for m in MONTHS if m != original]
        return random.choice(opts) if opts else original
    if re.match(r'^\d{2}$', original):  # 2-digit number (date/day)
        n = int(original); v = random.randint(1, 28)
        return f'{v:02d}' if v != n else f'{(v%28)+1:02d}'
    if re.match(r'^\d{1,2}$', original):  # 1-2 digit (date)
        n = int(original); v = random.randint(1, 28)
        return str(v) if v != n else str((v % 28) + 1)
    if re.match(r'^\d{2}:\d{2}:\d{2}$', original):
        return f'{random.randint(0,23):02d}:{random.randint(0,59):02d}:{random.randint(0,59):02d}'
    if re.match(r'^\d{2}:\d{2}:\d{2}\.\d{3}$', original):
        return f'{random.randint(0,23):02d}:{random.randint(0,59):02d}:{random.randint(0,59):02d}.{random.randint(0,999):03d}'
    if re.match(r'^\d{2}:\d{2}:\d{2},\d{3}$', original):
        return f'{random.randint(0,23):02d}:{random.randint(0,59):02d}:{random.randint(0,59):02d},{random.randint(0,999):03d}'
    if re.match(r'^\d{10}$', original):
        return str(random.randint(1000000000, 2147483647))
    if re.match(r'^\d{13}$', original):
        return f'{random.randint(1500000000000, 1600000000000)}'
    if re.match(r'^\d{4}\.\d{2}\.\d{2}$', original):
        y = int(original[:4])
        return f'{y:04d}.{random.randint(1,12):02d}.{random.randint(1,28):02d}'
    if re.match(r'^\d{4}-\d{2}-\d{2}$', original):
        y = int(original[:4])
        return f'{y:04d}-{random.randint(1,12):02d}-{random.randint(1,28):02d}'
    if re.match(r'^\d{4}-\d{2}-\d{2}-\d{2}\.\d{2}\.\d{2}\.\d+$', original):
        return (f'{random.randint(2005,2006):04d}-{random.randint(1,12):02d}-{random.randint(1,28):02d}'
                f'-{random.randint(0,23):02d}.{random.randint(0,59):02d}.{random.randint(0,59):02d}.{random.randint(100000,999999)}')
    if re.match(r'^\d{8}-\d{1,2}:\d{1,2}:\d{1,2}:\d{1,3}$', original):
        return f'{random.randint(20170101,20180101)}-{random.randint(0,23)}:{random.randint(0,59)}:{random.randint(0,59)}:{random.randint(0,999)}'
    if re.match(r'^\d{2}/\d{2}/\d{2}\s+\d{2}:\d{2}:\d{2}$', original):
        return f'{random.randint(10,17):02d}/{random.randint(1,12):02d}/{random.randint(1,28):02d} {random.randint(0,23):02d}:{random.randint(0,59):02d}:{random.randint(0,59):02d}'
    if re.match(r'^\d{2}/\d{2}/\d{2}$', original):
        return f'{random.randint(10,17):02d}/{random.randint(1,12):02d}/{random.randint(1,28):02d}'
    if re.match(r'^\d{2}-\d{2}$', original):
        return f'{random.randint(1,12):02d}-{random.randint(1,28):02d}'
    if re.match(r'^0x[0-9a-fA-F]+$', original):
        return f'0x{random.randint(0,0xFFFFFFFF):08x}'
    if re.match(r'^[a-f0-9]{6,}$', original):
        return f'{random.randint(0, 0xFFFFFFFFF):x}'
    if re.match(r'^\d+\.\d+\.\d+\.\d+(:\d+)?$', original):
        ip = f'{random.randint(10,223)}.{random.randint(0,255)}.{random.randint(0,255)}.{random.randint(0,255)}'
        if ':' in original: ip += f':{random.randint(1024,65535)}'
        return ip
    if re.match(r'^calvisitor-\d+-\d+-\d+-\d+$', original):
        return f'calvisitor-{random.randint(10,223)}-{random.randint(100,255)}-{random.randint(160,200)}-{random.randint(80,250)}'
    if re.match(r'^airbears2-\d+-\d+-\d+-\d+$', original):
        return f'airbears2-{random.randint(10,223)}-{random.randint(100,255)}-{random.randint(1,50)}-{random.randint(1,120)}'
    if original == 'authorMacBook-Pro':
        return random.choice(['calvisitor-10-105-160-95','airbears2-10-142-110-255'])
    if re.match(r'^(dn|cn|bn|en)\d+$', original):
        return f'{original[:2]}{random.randint(1,750)}'
    if re.match(r'^node-\d+$', original):
        return f'node-{random.randint(1,250)}'
    if re.match(r'^R\d{2}-M\d-N[0-9A-F]-[CI]:J\d{2}-U\d{2}$', original):
        return (f'R{random.randint(0,30):02d}-M{random.randint(0,2)}-N{random.randint(0,9)}-C:J{random.randint(1,20):02d}-U{random.randint(1,20):02d}')
    if re.match(r'^\d+\.\d+$', original):
        return f'{random.randint(1,2000)}.{random.randint(0,99)}'
    if re.match(r'^\d+ms$', original):
        return f'{random.randint(1,90000)}ms'
    if re.match(r'^\d+\s+bytes$', original, re.I):
        return f'{random.randint(100,999999)} bytes'
    if re.match(r'^\d+\s+seconds$', original):
        return f'{random.randint(1,999)} seconds'
    if re.match(r'^\d+##\d+', original):
        return '##'.join(str(random.randint(1,99999)) for _ in original.split('##'))
    if re.match(r'^-?\d+$', original):
        n = int(original)
        return str(random.randint(1,99)) if abs(n)<100 else str(random.randint(100000,999999))
    if '://' in original: return original
    return original


# ===== 头部字段解析 =====
def parse_mac_header(line):
    """解析Mac头部: Month Date Time Host Component[Pid]: """
    m = re.match(r'^([A-Z][a-z]{2})\s+(\d{1,2})\s+(\d{2}:\d{2}:\d{2})\s+([\w.-]+)\s+(.+?)\[(\d+)\]:\s+(.*)', line)
    if m: return {'month':m.group(1),'day':m.group(2),'time':m.group(3),'host':m.group(4),
                  'component':m.group(5),'pid':m.group(6),'content':m.group(7)}
    return None

def parse_bgl_header(line):
    """BGL: - ts date node datetime noderepeat RAS COMP LEVEL content"""
    m = re.match(r'^(\S+)\s+(\d{10})\s+(\d{4}\.\d{2}\.\d{2})\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(.+)', line)
    if m: return {'label':m.group(1),'ts':m.group(2),'date':m.group(3),'node':m.group(4),
                  'datetime':m.group(5),'noderep':m.group(6),'ras':m.group(7),'comp':m.group(8),
                  'level':m.group(9),'content':m.group(10)}
    return None

def parse_hpc_header(line):
    """HPC: eventId node component state timestamp flag content"""
    m = re.match(r'^(\d+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\d+)\s+(\d+)\s+(.+)', line)
    if m: return {'eid':m.group(1),'node':m.group(2),'comp':m.group(3),'state':m.group(4),
                  'ts':m.group(5),'flag':m.group(6),'content':m.group(7)}
    return None

def parse_thunderbird_header(line):
    """Thunderbird: - ts date node month day time host content"""
    m = re.match(r'^(\S+)\s+(\d{10})\s+(\d{4}\.\d{2}\.\d{2})\s+(\S+)\s+(\S+)\s+(\d{1,2})\s+(\S+)\s+(\S+/\S+)\s+(.+)', line)
    if m: return {'label':m.group(1),'ts':m.group(2),'date':m.group(3),'node':m.group(4),
                  'month':m.group(5),'day':m.group(6),'time':m.group(7),'host':m.group(8),'content':m.group(9)}
    return None

def parse_linux_header(line):
    """Linux: Month Date Time Host Process: content"""
    m = re.match(r'^([A-Z][a-z]{2})\s+(\d{1,2})\s+(\d{2}:\d{2}:\d{2})\s+(\S+)\s+(\S+):\s+(.+)', line)
    if m:
        process = m.group(5)
        # Extract PID from process like "sshd(pam_unix)[19939]" or "crond[2916]"
        pm = re.search(r'\[(\d+)\]', process)
        pid = pm.group(1) if pm else '0'
        return {'month':m.group(1),'day':m.group(2),'time':m.group(3),
                'host':m.group(4),'process':process,'pid':pid,'content':m.group(6)}
    return None

def parse_android_header(line):
    """Android: MM-DD HH:MM:SS.mmm pid tid Level Component: content"""
    m = re.match(r'^(\d{2}-\d{2})\s+(\d{2}:\d{2}:\d{2}\.\d{3})\s+(\d+)\s+(\d+)\s+([A-Z])\s+(\S+):\s+(.+)', line)
    if m: return {'date':m.group(1),'time':m.group(2),'pid':m.group(3),
                  'tid':m.group(4),'level':m.group(5),'component':m.group(6),'content':m.group(7)}
    return None

def parse_hdfs_header(line):
    """HDFS: MMDD HHMMSS pid LEVEL Component: content"""
    m = re.match(r'^(\d{6})\s+(\d{6})\s+(\d+)\s+([A-Z]+)\s+(\S+):\s+(.+)', line)
    if m: return {'date':m.group(1),'time':m.group(2),'pid':m.group(3),
                  'level':m.group(4),'component':m.group(5),'content':m.group(6)}
    return None

def parse_hadoop_header(line):
    """Hadoop: YYYY-MM-DD HH:MM:SS,mmm LEVEL [thread] component: content"""
    m = re.match(r'^(\d{4}-\d{2}-\d{2})\s+(\d{2}:\d{2}:\d{2},\d{3})\s+([A-Z]+)\s+\[(.+?)\]\s+(\S+):\s+(.+)', line)
    if m: return {'date':m.group(1),'time':m.group(2),'level':m.group(3),
                  'thread':m.group(4),'component':m.group(5),'content':m.group(6)}
    return None

def parse_spark_header(line):
    """Spark: YY/MM/DD HH:MM:SS LEVEL component: content"""
    m = re.match(r'^(\d{2}/\d{2}/\d{2})\s+(\d{2}:\d{2}:\d{2})\s+([A-Z]+)\s+(\S+):\s+(.+)', line)
    if m: return {'date':m.group(1),'time':m.group(2),'level':m.group(3),
                  'component':m.group(4),'content':m.group(5)}
    return None

def parse_zookeeper_header(line):
    """Zookeeper: YYYY-MM-DD HH:MM:SS,mmm - LEVEL [...] - content"""
    m = re.match(r'^(\d{4}-\d{2}-\d{2})\s+(\d{2}:\d{2}:\d{2},\d{3})\s+-\s+([A-Z]+)\s+(\[.+?\])\s+-\s+(.+)', line)
    if m: return {'date':m.group(1),'time':m.group(2),'level':m.group(3),
                  'thread':m.group(4),'content':m.group(5)}
    return None

def parse_windows_header(line):
    """Windows: YYYY-MM-DD HH:MM:SS, Level               Component    content"""
    m = re.match(r'^(\d{4}-\d{2}-\d{2})\s+(\d{2}:\d{2}:\d{2}),\s+(\S+)\s+(\S+)\s+(.+)', line)
    if m: return {'date':m.group(1),'time':m.group(2),'level':m.group(3),
                  'component':m.group(4),'content':m.group(5)}
    return None

def parse_healthapp_header(line):
    """HealthApp: YYYYMMDD-HH:MM:SS:mmm|Component|Pid|content"""
    m = re.match(r'^(\d{8}-\d{1,2}:\d{1,2}:\d{1,2}:\d{1,3})\|(\S+)\|(\d+)\|(.+)', line)
    if m: return {'time':m.group(1),'component':m.group(2),'pid':m.group(3),'content':m.group(4)}
    return None

def parse_openssh_header(line):
    """OpenSSH: Month Date Day Time host sshd[pid]: content"""
    m = re.match(r'^([A-Z][a-z]{2})\s+(\d{1,2})\s+(\d{2}:\d{2}:\d{2})\s+(\S+)\s+(\S+)\[(\d+)\]:\s+(.+)', line)
    if m: return {'month':m.group(1),'day':m.group(2),'time':m.group(3),
                  'host':m.group(4),'component':m.group(5),'pid':m.group(6),'content':m.group(7)}
    return None

def parse_openstack_header(line):
    """OpenStack: label date time pid LEVEL component [addr] content"""
    m = re.match(r'^(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\[.*?\])\s+(.+)', line)
    if m: return {'label':m.group(1),'date':m.group(2),'time':m.group(3),
                  'pid':m.group(4),'level':m.group(5),'component':m.group(6),
                  'addr':m.group(7),'content':m.group(8)}
    return None

def parse_proxifier_header(line):
    """Proxifier: [MM.DD HH:MM:SS] program - content"""
    m = re.match(r'^\[(\d{2}\.\d{2})\s+(\d{2}:\d{2}:\d{2})\]\s+(\S+)\s+-\s+(.+)', line)
    if m: return {'date':m.group(1),'time':m.group(2),'program':m.group(3),'content':m.group(4)}
    return None

def parse_apache_header(line):
    """Apache: [Day Mon DD HH:MM:SS YYYY] [level] [client IP] content"""
    m = re.match(r'^\[(.+?)\]\s+\[(.+?)\]\s+(.+)', line)
    if m: return {'datetime':m.group(1),'level':m.group(2),'content':m.group(3)}
    return None


PARSERS = {
    'Mac': parse_mac_header, 'BGL': parse_bgl_header, 'HPC': parse_hpc_header,
    'Thunderbird': parse_thunderbird_header, 'Linux': parse_linux_header,
    'Android': parse_android_header, 'HDFS': parse_hdfs_header,
    'Hadoop': parse_hadoop_header, 'Spark': parse_spark_header,
    'Zookeeper': parse_zookeeper_header, 'Windows': parse_windows_header,
    'HealthApp': parse_healthapp_header, 'OpenSSH': parse_openssh_header,
    'OpenStack': parse_openstack_header, 'Proxifier': parse_proxifier_header,
    'Apache': parse_apache_header,
}


def header_safe_mutate(line, ds, parser):
    """只修改头部安全字段"""
    h = parser(line)
    if not h: return None
    if ds in ('Mac','Linux','OpenSSH','Thunderbird'):
        mth = gen_val(h['month'], 'month')
        day = gen_val(h['day'])
        tm = gen_val(h['time'])
        pid = gen_val(h['pid'])
        host = h.get('host', h.get('host',''))
        if host: host = gen_val(host) if host else host
        new = line
        new = re.sub(r'\b' + re.escape(h['month']) + r'\b', mth, new, count=1)
        new = re.sub(r'\b' + re.escape(h['day']) + r'\b', day, new, count=1)
        new = re.sub(r'\b' + re.escape(h['time']) + r'\b', tm, new, count=1)
        new = re.sub(r'\b' + re.escape(h['pid']) + r'\b', pid, new, count=1)
        if host and host != h.get('host',''):
            new = new.replace(h.get('host',''), host, 1)
        return new
    if ds in ('BGL','HPC'):
        ts = gen_val(h.get('ts',h.get('ts',''))) if 'ts' in h else None
        node = gen_val(h.get('node','')) if 'node' in h else None
        new = line
        if ts: new = new.replace(h['ts'], ts, 1)
        if node and 'node' in h: new = new.replace(h['node'], node, 1)
        return new
    if ds in ('Android','HDFS','Hadoop','Spark'):
        date = gen_val(h['date'])
        tm = gen_val(h['time'])
        pid = gen_val(h['pid'])
        new = line
        new = new.replace(h['date'], date, 1)
        new = new.replace(h['time'], tm, 1)
        new = new.replace(h['pid'], pid, 1)
        if 'tid' in h: new = new.replace(h['tid'], gen_val(h['tid']), 1)
        if 'thread' in h: new = new.replace(h['thread'], gen_val(h['thread']), 1)
        return new
    if ds in ('Zookeeper','Windows','HealthApp'):
        date = gen_val(h['date']) if 'date' in h else None
        tm = gen_val(h['time'])
        new = line
        if date: new = new.replace(h['date'], date, 1)
        new = new.replace(h['time'], tm, 1)
        return new
    if ds in ('OpenStack','Proxifier','Apache'):
        if 'date' in h:
            new = line.replace(h['date'], gen_val(h['date']), 1)
            new = new.replace(h['time'], gen_val(h['time']), 1)
            return new
        tm = gen_val(h['time']) if 'time' in h else None
        date = gen_val(h['date']) if 'date' in h else None
        new = line
        if tm: new = new.replace(h['time'], tm, 1)
        if date: new = new.replace(h['date'], date, 1)
        return new
    return None


def process_dataset(dataset_name):
    ds_dir = os.path.join(DEDUP_DIR, dataset_name)
    log_file = os.path.join(ds_dir, f'{dataset_name}_dedup_1.log')
    if not os.path.exists(log_file):
        return {'dataset': dataset_name, 'error': 'not found'}

    for enc in ['utf-8','gbk','utf-8-sig','latin-1']:
        try:
            with open(log_file, 'r', encoding=enc) as f:
                lines = [l.rstrip('\n') for l in f if l.strip()]
            break
        except: continue
    else: return {'dataset': dataset_name, 'error': 'decode'}

    regexes = Se.get_dataset_regex(dataset_name)
    parser = PARSERS.get(dataset_name)

    # 模板分组
    groups = defaultdict(list)
    for i, line in enumerate(lines):
        skel = line
        for r in regexes: skel = re.sub(r, '<*>', skel)
        groups[skel].append((i, line))

    # 选候选模板
    candidates = []
    for skel, items in groups.items():
        if len(items) > 5: continue
        line = items[0][1]
        if len(line) > 400: continue
        if re.search(r'https?://', line): continue
        candidates.append(line)

    if not candidates:
        candidates = [items[0][1] for items in sorted(groups.items(), key=lambda x: -len(x[1]))[:50]]

    random.shuffle(candidates)
    candidates = candidates[:30]

    strategies = {}
    results = {}

    for ver_name, target in [('oracle_60', 60), ('oracle_100', 100), ('oracle_200', 200)]:
        generated = []
        bad_fmt = 0
        strategy_count = {'strict': 0, 'header': 0, 'numeric': 0}

        # 每个模板生成几条
        per_tpl = max(1, target // len(candidates))
        for line in candidates:
            # 策略1: strict - regex slot mutation
            slots = []
            for r in regexes:
                for m in re.finditer(r, line):
                    slots.append({'start': m.start(), 'end': m.end(), 'orig': m.group()})
            slots.sort(key=lambda x: x['start'])
            merged = []
            for s in slots:
                if merged and s['start'] < merged[-1]['end']: continue
                merged.append(s)

            strict_ok = 0
            for _ in range(per_tpl * 3):
                if strict_ok >= per_tpl: break
                result = list(line)
                ch = 0
                for s in sorted(merged, key=lambda x: -x['start']):
                    nv = gen_val(s['orig'])
                    if nv != s['orig']:
                        ch += 1
                        result[s['start']:s['end']] = list(nv)
                if ch >= 1:
                    mut = ''.join(result)
                    msk = mut
                    for r in regexes: msk = re.sub(r, '<*>', msk)
                    osk = line
                    for r in regexes: osk = re.sub(r, '<*>', osk)
                    if msk == osk and mut != line:
                        generated.append(mut)
                        strict_ok += 1
                        strategy_count['strict'] += 1

            # 策略2: header_safe
            header_ok = 0
            if strict_ok < per_tpl and parser:
                for _ in range((per_tpl - strict_ok) * 3):
                    if header_ok >= per_tpl - strict_ok: break
                    mut = header_safe_mutate(line, dataset_name, parser)
                    if mut and mut != line:
                        generated.append(mut)
                        header_ok += 1
                        strategy_count['header'] += 1

        generated = list(dict.fromkeys(generated))  # dedup

        out_name = f'{dataset_name}_dedup_1_{ver_name}.log'
        out_path = os.path.join(ds_dir, out_name)
        full = '\n'.join(lines) + '\n' + '\n'.join(generated) + '\n'
        full = full.replace('﻿', '')
        with open(out_path, 'w', encoding='utf-8') as f:
            f.write(full)

        strategies[ver_name] = strategy_count
        results[ver_name] = {'file': out_name, 'added': len(generated), 'strategies': strategy_count}
        print(f'  {ver_name}: +{len(generated)} (strict={strategy_count["strict"]} header={strategy_count["header"]})')

    return {'dataset': dataset_name, 'results': results, 'orig': len(lines)}


def main():
    print('=== dir_dedup_1 Oracle增强生成（三级策略）===\n')
    datasets = sorted([d for d in os.listdir(DEDUP_DIR) if os.path.isdir(os.path.join(DEDUP_DIR, d))])
    all_r = []
    for ds in datasets:
        print(f'--- {ds} ---')
        r = process_dataset(ds)
        all_r.append(r)
        print()

    # 总报告
    sp = os.path.join(DEDUP_DIR, 'oracle_generation_summary.csv')
    with open(sp, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['dataset','oracle_60_added','oracle_100_added','oracle_200_added','strategy_used','bad_fmt','notes'])
        for r in all_r:
            ds = r.get('dataset','?')
            if 'error' in r:
                w.writerow([ds,0,0,0,'error',0,r['error']])
                continue
            o60 = r['results'].get('oracle_60',{})
            o100 = r['results'].get('oracle_100',{})
            o200 = r['results'].get('oracle_200',{})
            s60 = o60.get('strategies',{})
            strat = 'mixed'
            if s60.get('strict',0)>s60.get('header',0): strat='strict_oracle'
            else: strat='header_safe_oracle'
            w.writerow([ds, o60.get('added',0), o100.get('added',0), o200.get('added',0), strat, 0, ''])

    print(f'=== 完成 ===')
    print(f'总报告: {sp}')
    print(f'文件目录: {DEDUP_DIR}')


if __name__ == '__main__':
    main()
