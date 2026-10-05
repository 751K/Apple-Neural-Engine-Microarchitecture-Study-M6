#!/usr/bin/env python3
# 由中文浅色 SVG 生成英文浅色 SVG：figs/zh/light/<名>.svg → figs/en/light/<名>.svg。
# 译文在 tools/figs/i18n/<名>.en.json（键为 SVG 中的中文文字，原样匹配）。
# 每个含中文的文字节点都必须在对照表中有译文，否则报错退出，保证英文版里不残留中文。
# 用法：python3 tools/figs/translate.py [名 ...]（缺省为 figs/zh/light/ 下全部 SVG）
import glob
import json
import os
import re
import sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..')
SRC, DST = os.path.join(ROOT, 'figs', 'zh', 'light'), os.path.join(ROOT, 'figs', 'en', 'light')
I18N = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'i18n')
CJK = re.compile(r'[　-鿿＀-￯]')


def translate(name):
    s = open(os.path.join(SRC, name + '.svg')).read()
    table = json.load(open(os.path.join(I18N, name + '.en.json')))
    missing = []

    def sub(m):
        t = m.group(1)
        if not CJK.search(t):
            return m.group(0)
        en = table.get(t)
        if not en:
            missing.append(t)
            return m.group(0)
        en = re.sub(r'&(?!(?:amp|lt|gt|quot|apos|#\d+);)', '&amp;', en).replace('<', '&lt;').replace('>', '&gt;')
        return '>' + en + '<'

    out = re.sub(r'>([^<>]+)<', sub, s)
    if missing:
        sys.exit(f'{name}: 缺少 {len(missing)} 条译文，例如 {missing[:3]}')
    out = out.replace('PingFang SC, Helvetica Neue', 'Helvetica Neue, PingFang SC')   # 英文版优先用西文字体
    os.makedirs(DST, exist_ok=True)
    open(os.path.join(DST, name + '.svg'), 'w').write(out)
    print(os.path.join('figs', 'en', 'light', name + '.svg'))


names = sys.argv[1:] or sorted(os.path.basename(f)[:-4] for f in glob.glob(os.path.join(SRC, '*.svg')))
for n in names:
    translate(n)
