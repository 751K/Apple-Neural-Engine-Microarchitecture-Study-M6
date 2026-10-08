#!/usr/bin/env python3
# 逐节核对英文译稿与中文定稿：final_report/zh.md ↔ final_report/en.md（或指定的译稿片段）。
# 按 ## / ### 标题把两边切成节并按顺序对齐，每节比较：
#   标题编号、数字（多重集合）、章节 / 图 / 表 / 附录引用、参考文献编号、证据标签、
#   表格行列数、图片路径、代码片段与链接目标；另报告英文中残留的中日韩字符。
# 用法：python3 tools/check_en.py [英文文件] [--zh 起始行-结束行]
#   不带参数时核对整篇；核对片段时用 --zh 给出对应的中文行号范围。
import argparse
import collections
import os
import re
import sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
ap = argparse.ArgumentParser()
ap.add_argument('en', nargs='?', default=os.path.join(ROOT, 'final_report', 'en.md'))
ap.add_argument('--zh', help='中文行号范围，如 1-207')
args = ap.parse_args()

zh_lines = open(os.path.join(ROOT, 'final_report', 'zh.md')).read().split('\n')
if args.zh:
    a, b = map(int, args.zh.split('-'))
    zh_lines = zh_lines[a - 1:b]
zh = '\n'.join(zh_lines)
en = open(args.en).read()

CJK = re.compile(r'[　-〿㐀-鿿＀-￯]')
TAG_ZH = {'计时': 'timing', '推断': 'inferred', '内核': 'kernel', '固件': 'firmware', '编译器': 'compiler', '数值': 'numerical'}


def sections(text):
    out, cur, head = [], [], None
    for line in text.split('\n'):
        if re.match(r'#{1,3} ', line):
            if head is not None or cur:
                out.append((head, '\n'.join(cur)))
            head, cur = line, []
        else:
            cur.append(line)
    out.append((head, '\n'.join(cur)))
    return out


def strip_code(t):
    return re.sub(r'`[^`]*`', ' ', re.sub(r'\]\([^)]*\)', '] ', t))


WORDS = {w: str(i) for i, w in enumerate('zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen twenty'.split())}
WORDS.update(single='1', double='2', twice='2', once='1', half='2', first='1', second='2', third='3', fourth='4', fifth='5', sixth='6', seventh='7', eighth='8', ninth='9', tenth='10')


def numbers(t, lang='zh'):
    t = strip_code(t)
    if lang == 'en':
        t = re.sub(r'\b[A-Za-z]+\b', lambda m: f' {WORDS[m.group(0).lower()]} ' if m.group(0).lower() in WORDS else m.group(0), t)
    t = re.sub(r'〔[^〕]*〕', ' ', t)
    return collections.Counter(re.findall(r'\d+(?:\.\d+)?', t))


def xrefs_zh(t):
    r = collections.Counter()
    for m in re.finditer(r'第 ([\d.]+(?:\s*[–—、和与及至]\s*[\d.]+)*) ([节章])', t):
        for n in re.findall(r'[\d.]+', m.group(1)):
            r[('S' if m.group(2) == '节' else 'C') + n.rstrip('.')] += 1
    for m in re.finditer(r'([图表]) ((?:[A-Z]|\d+)-\d+(?:\s*[–、和与及至]\s*(?:[图表] )?(?:(?:[A-Z]|\d+)-)?\d+)*)', t):
        k = 'F' if m.group(1) == '图' else 'T'
        pre = None
        for n in re.findall(r'(?:(?:[A-Z]|\d+)-)?\d+', m.group(2)):
            if '-' in n:
                pre = n.split('-')[0]
            else:
                n = f'{pre}-{n}'
            r[k + n] += 1
    for m in re.finditer(r'附录 ([A-E](?:[、和与–][A-E])*)', t):
        for n in re.findall(r'[A-E]', m.group(1)):
            r['A' + n] += 1
    return r


def xrefs_en(t):
    r = collections.Counter()
    for m in re.finditer(r'(Sections?|Chapters?) ([\d.]+(?:(?:–|, | and |, and | to )[\d.]+)*)', t):
        k = 'S' if m.group(1).startswith('S') else 'C'
        for n in re.findall(r'\d+(?:\.\d+)*', m.group(2)):
            r[k + n] += 1
    for m in re.finditer(r'(Figures?|Tables?) ((?:[A-Z]|\d+)-\d+(?:(?:–|, | and |, and )(?:(?:[A-Z]|\d+)-)?\d+)*)', t):
        k = 'F' if m.group(1).startswith('F') else 'T'
        pre = None
        for n in re.findall(r'(?:(?:[A-Z]|\d+)-)?\d+', m.group(2)):
            if '-' in n:
                pre = n.split('-')[0]
            else:
                n = f'{pre}-{n}'
            r[k + n] += 1
    for m in re.finditer(r'Appendi(?:x|ces) ([A-E](?:(?:, | and |, and |–)[A-E])*)\b', t):
        for n in re.findall(r'[A-E]', m.group(1)):
            r['A' + n] += 1
    return r


def tags(t, lang):
    out = collections.Counter()
    for m in re.findall(r'〔([^〕]*)〕', t):
        parts = re.split(r'[，,]\s*', m)
        if lang == 'zh':
            parts = [TAG_ZH.get(p, p) for p in parts]
        out[', '.join(parts)] += 1
    return out


def tables(t):
    shapes, rows = [], []
    for line in t.split('\n') + ['']:
        if line.startswith('|'):
            rows.append(line.count('|') - 1)
        elif rows:
            shapes.append((len(rows), max(rows)))
            rows = []
    return shapes


def feats(t, lang):
    return {
        'numbers': numbers(t, lang),
        'xrefs': xrefs_zh(t) if lang == 'zh' else xrefs_en(t),
        'cites': collections.Counter(re.findall(r'\[(\d+(?:[,，]\s*\d+)*)\]', t.replace('，', ', '))),
        'tags': tags(t, lang),
        'tables': tables(t),
        'images': [re.sub(r'/(zh|en)/', '/', p) for p in re.findall(r'!\[[^\]]*\]\(([^)]*)\)', t)],
        'code': collections.Counter(re.findall(r'`[^`]*`', t)),
        'links': collections.Counter(re.findall(r'\]\(([^)]*)\)', t)) - collections.Counter(re.findall(r'!\[[^\]]*\]\(([^)]*)\)', t)),
    }


def diff(a, b):
    if isinstance(a, collections.Counter):
        return dict(a - b), dict(b - a)
    return (a, b) if a != b else ({}, {})


def headnum(h):
    if h is None:
        return None
    m = re.match(r'(#+) (?:附录 |Appendix )?([A-Z]\b|\d+(?:\.\d+)*)', h)
    return m.group(1) + m.group(2) if m else h.split()[0]     # 无编号的标题只比较级别


zs, es = sections(zh), sections(en)
problems = 0
if len(zs) != len(es):
    print(f'节数不同：中文 {len(zs)}，英文 {len(es)}')
    problems += 1
for i, ((zh_h, zt), (en_h, et)) in enumerate(zip(zs, es)):
    label = en_h or zh_h or '(开头)'
    msgs = []
    if headnum(zh_h) != headnum(en_h):
        msgs.append(f'标题不对应：{zh_h!r} ↔ {en_h!r}')
    zf, ef = feats(zt, 'zh'), feats(et, 'en')
    ef['numbers_digits'] = numbers(et)          # 英文中按数字书写的数，用来判断"多出"
    for k in zf:
        miss, extra = diff(zf[k], ef[k])
        if k == 'numbers':                       # 缺：与含数词的英文比较；多出：只与按数字书写的部分比较
            extra = dict(ef['numbers_digits'] - zf[k])
        if miss or extra:
            msgs.append(f'{k}：中文有而英文缺 {miss}；英文多出 {extra}')
    zp = len([p for p in zt.split('\n\n') if p.strip()])
    ep = len([p for p in et.split('\n\n') if p.strip()])
    if zp != ep:
        msgs.append(f'段落数：中文 {zp}，英文 {ep}')
    left = sorted(set(CJK.findall(re.sub(r'[〔〕]', '', (en_h or '') + et))))
    if left:
        msgs.append(f'残留中文字符：{"".join(left)}')
    if msgs:
        problems += 1
        print(f'\n== {label}')
        for m in msgs:
            print('  ' + m)
print(f'\n共 {len(es)} 节，{problems} 节有差异。')
sys.exit(1 if problems else 0)
