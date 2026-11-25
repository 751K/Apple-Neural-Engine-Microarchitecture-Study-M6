#!/usr/bin/env python3
# 把报告正文（第 4–17 章）按章拆成 Substack 文章：final_report/zh.md → substack/zh/
#   - 正文不改写；每篇开头加一行出处，结尾附本篇引用到的参考文献；
#   - Substack 编辑器不支持表格，表格由本机 Chrome 无头模式渲染成 PNG（substack/zh/img/）；
#   - ../tools/…、../data/… 链接改写为 GitHub 地址，报告用图改用 GitHub Pages 上的 PNG；
#   - 每篇出两份：preview/ 用本地图片，便于检查；paste/ 用线上图片地址，用于复制粘贴到 Substack
#     （表格图片要先推送到 GitHub 才能显示，地址见 TABLE_BASE）。
# 用法：python3 tools/substack/build.py [--lang zh|en] [--no-tables]
# 依赖：markdown-it-py；Google Chrome（/Applications/Google Chrome.app）
import argparse
import html
import json
import os
import re
import shutil
import subprocess
import tempfile

from markdown_it import MarkdownIt

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
REPO = 'https://github.com/751K/Apple-Neural-Engine-Microarchitecture-Study-M6'
PAGES = 'https://751k.github.io/Apple-Neural-Engine-Microarchitecture-Study-M6'
RAW = 'https://raw.githubusercontent.com/751K/Apple-Neural-Engine-Microarchitecture-Study-M6/main'
CHROME = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
WIDTH = 728          # Substack 正文宽度（CSS px）
MAXW = 980           # 表格最大宽度，超过时单元格换行
SCALE = 2            # 表格图片按 2 倍像素渲染

ap = argparse.ArgumentParser()
ap.add_argument('--lang', default='zh', choices=('zh', 'en'))
ap.add_argument('--no-tables', action='store_true', help='不重新渲染表格图片')
args = ap.parse_args()
zh = args.lang == 'zh'
OUT = os.path.join(ROOT, 'substack', args.lang)
# 表格图片托管在 substack/export 分支上（粘贴时 Substack 会转存到自己的 CDN）
TABLE_BASE = f'https://raw.githubusercontent.com/751K/Apple-Neural-Engine-Microarchitecture-Study-M6/refs/heads/substack/export/substack/{args.lang}/img'

# 每篇的范围：(章节标题行的前缀, 起始小节, 结束小节)；小节为 None 表示整章
POSTS = [
    ('4', None, None),
    ('5', '5.1', '5.6'),
    ('5', '5.7', '5.12'),
    ('6', None, None),
    ('7', '7.1', '7.5'),
    ('7', '7.6', '7.10'),
    ('8', None, None),
    ('9', None, None),
    ('10', None, None),
    ('11', None, None), ('12', None, None),      # 合为一篇
    ('13', None, None),
    ('14', None, None),
    ('15', None, None), ('16', None, None), ('17', None, None),   # 合为一篇
]
GROUPS = [[0], [1], [2], [3], [4], [5], [6], [7], [8], [9, 10], [11], [12], [13, 14, 15]]

src = open(os.path.join(ROOT, 'final_report', f'{args.lang}.md'), encoding='utf-8').read()
lines = src.split('\n')
report_title = lines[0].lstrip('# ').strip()


# ---------- 切出各章、各小节 ----------
def chapter(num):
    """返回 (章标题, 章内各行)；章以 '## <num>. ' 开头，到下一个 '## ' 为止。"""
    start = next(i for i, l in enumerate(lines) if re.match(rf'## {num}\. ', l))
    end = next(i for i in range(start + 1, len(lines)) if lines[i].startswith('## '))
    return lines[start][3:].strip(), lines[start + 1:end]


def section_slice(body, first, last):
    """从 '### first ' 到 '### last ' 所在小节末尾。"""
    idx = [i for i, l in enumerate(body) if l.startswith('### ')]
    s = next(i for i in idx if body[i].startswith(f'### {first} '))
    e_head = next(i for i in idx if body[i].startswith(f'### {last} '))
    after = [i for i in idx if i > e_head]
    return body[s:after[0] if after else len(body)]


# ---------- 参考文献 ----------
refs = {}
ri = next(i for i, l in enumerate(lines) if re.match(r'## (参考文献|References)', l))
for l in lines[ri + 1:]:
    if l.startswith('## '):
        break
    m = re.match(r'\[(\d+)\]\s*(.*)', l)
    if m:
        refs[int(m.group(1))] = m.group(2)


def cited(text):
    nums = set()
    for m in re.finditer(r'\[(\d+(?:\s*[,，–-]\s*\d+)*)\](?!\()', text):
        for part in re.split(r'\s*[,，]\s*', m.group(1)):
            if re.match(r'\d+\s*[–-]\s*\d+', part):
                a, b = map(int, re.split(r'\s*[–-]\s*', part))
                nums.update(range(a, b + 1))
            else:
                nums.add(int(part))
    return sorted(n for n in nums if n in refs)


def autolink(t):
    t = re.sub(r'arXiv:(\d{4}\.\d{4,5})', r'<a href="https://arxiv.org/abs/\1">arXiv:\1</a>', t)
    return re.sub(r'(?<!["=>])(https?://[^\s<，,）)]+?)(?=[.,，]?\s|[.,，]?$)',
                  lambda u: f'<a href="{u.group(1)}">{u.group(1)}</a>', t)


# ---------- Markdown → HTML ----------
md = MarkdownIt('commonmark', {'html': True}).enable('table')


def repo_link(m):
    path = m.group(1)
    kind = 'tree' if path.endswith('/') or os.path.isdir(os.path.join(ROOT, path)) else 'blob'
    return f'href="{REPO}/{kind}/main/{path}"'


TAB = '表' if zh else 'Table'
tables = []   # (id, table_html)


def render(text, post_no):
    body = md.render(text)
    body = re.sub(r'href="\.\./((?:tools|data|notes|figs)/[^"]*)"', repo_link, body)
    # 标题降一级：### → h2，#### → h3（章标题作为文章标题）
    for a, b in (('h3', 'h2'), ('h4', 'h3'), ('h5', 'h4')):
        body = body.replace(f'<{a}>', f'<{b}>').replace(f'</{a}>', f'</{b}>')

    # 表格：抽出来渲染成图，用表标题作为 alt
    def one_table(m):
        cap_html, tbl = m.group(1), m.group(2)
        cap_txt = html.unescape(re.sub(r'<[^>]+>', '', cap_html or '')).strip()
        tm = re.match(TAB + r'\s*([0-9A-Z]+-\d+)', cap_txt)
        tid = f't{tm.group(1)}' if tm else f't{post_no:02d}-{len(tables) + 1}'
        tables.append((tid, tbl))
        cap = f'<p><em>{cap_html}</em></p>\n' if cap_html else ''
        return f'{cap}<p><img src="@TABLE@/{tid}.png" alt="{html.escape(cap_txt or tid)}"></p>\n'

    body = re.sub(r'(?:<p><em>((?:' + TAB + r') [^\n]*?)</em></p>\s*)?(<table>.*?</table>)',
                  one_table, body, flags=re.S)
    return body


def page(title, body, preview):
    if preview:
        body = body.replace('@TABLE@', '../img')
        body = re.sub(r'src="\.\./figs/', 'src="../../../figs/', body)
    else:
        body = body.replace('@TABLE@', TABLE_BASE)
        body = re.sub(r'src="\.\./figs/', f'src="{RAW}/figs/', body)
    note = ('复制方法：在浏览器里打开本页，从标题下方的正文开始全选（⌘A 后取消选中这段说明亦可），'
            '复制，粘贴到 Substack 编辑器。标题单独填。') if zh else \
        'To paste: open this page, select the article body, copy, and paste into the Substack editor. Enter the title separately.'
    return f'''<!doctype html>
<html lang="{args.lang}"><head><meta charset="utf-8"><title>{html.escape(title)}</title>
<style>
body {{ max-width: {WIDTH}px; margin: 40px auto; font: 17px/1.7 -apple-system, "PingFang SC", sans-serif; color: #222; padding: 0 16px; }}
img {{ max-width: 100%; }}
.howto {{ background: #fff6d6; padding: 8px 12px; font-size: 14px; }}
h1 {{ font-size: 30px; line-height: 1.3; }}
code {{ font-family: Menlo, monospace; font-size: 0.88em; }}
pre {{ background: #f4f4f4; padding: 10px; overflow-x: auto; }}
</style></head><body>
<p class="howto">{note}</p>
<h1>{html.escape(title)}</h1>
<article>
{body}
</article>
</body></html>
'''


# ---------- 组装各篇 ----------
os.makedirs(os.path.join(OUT, 'preview'), exist_ok=True)
os.makedirs(os.path.join(OUT, 'paste'), exist_ok=True)
index = []
for n, group in enumerate(GROUPS, 1):
    parts, titles, nums, names, part = [], [], [], [], ''
    for gi in group:
        num, first, last = POSTS[gi]
        ctitle, body = chapter(num)
        nums.append(num)
        names.append(ctitle.split('. ', 1)[1])
        if first:
            body = section_slice(body, first, last)
            k = sum(1 for p in POSTS[:gi] if p[0] == num)   # 同一章的第几部分（0 起）
            part = ('（上）', '（下）')[k] if zh else f' (Part {k + 1})'
        titles.append(ctitle)
        if len(group) > 1:   # 多章合为一篇时保留章标题，作为二级标题
            body = [f'## {ctitle}', ''] + body
        parts.append('\n'.join(body))
    text = '\n\n'.join(parts)
    # 多章合并时 '## 章' → h2，原 '### 节' → h3：先把 ## 换成占位的 ###，统一降级后正好对齐
    if len(group) > 1:
        text = re.sub(r'^(#{2,4}) ', lambda m: '#' + m.group(1) + ' ', text, flags=re.M)

    # 标题用报告的章号：Ch. 5 (Part 1)、Ch. 11–12
    ch = nums[0] if len(nums) == 1 else f'{nums[0]}–{nums[-1]}'
    joined = '、'.join(names) if zh else '; '.join(names)
    title = f'Apple M6 ANE 微体系结构 · 第 {ch} 章{part}：{joined}' if zh else \
        f'Apple M6 ANE Microarchitecture, Ch. {ch}{part}: {joined}'
    lead = (f'<p><em>本文是技术报告《{report_title}》的第 {"、".join(t.split(".")[0] for t in titles)} 章，原文照录。'
            f'全文：<a href="{PAGES}/">网页版</a>；原始数据与工具：<a href="{REPO}">GitHub</a>。'
            f'文中的章节号、图表号与报告一致。</em></p>\n') if zh else \
        (f'<p><em>This post is chapter {", ".join(t.split(".")[0] for t in titles)} of the report '
         f'"{report_title}", reproduced unchanged. Full report: <a href="{PAGES}/en/">web</a>; '
         f'data and tools: <a href="{REPO}">GitHub</a>. Section, figure and table numbers follow the report.</em></p>\n')

    body = lead + render(text, n)
    cs = cited(text)
    if cs:
        body += f'<h2>{"参考文献" if zh else "References"}</h2>\n'
        body += ''.join(f'<p>[{c}] {autolink(html.escape(refs[c]))}</p>\n' for c in cs)

    name = f'{n:02d}.html'
    for kind in ('preview', 'paste'):
        with open(os.path.join(OUT, kind, name), 'w', encoding='utf-8') as f:
            f.write(page(title, body, kind == 'preview'))
    index.append((name, title, len(text)))

with open(os.path.join(OUT, 'index.md'), 'w', encoding='utf-8') as f:
    f.write(f'# Substack 分篇（{args.lang}）\n\n| 文件 | 标题 | 原文字符数 |\n|---|---|---|\n')
    for name, title, size in index:
        f.write(f'| {name} | {title} | {size} |\n')
print(f'{len(index)} 篇，{len(tables)} 张表')

# ---------- 表格渲染 ----------
if args.no_tables:
    raise SystemExit
TCSS = f'''
html, body {{ margin: 0; background: #fff; }}
.wrap {{ display: inline-block; padding: 6px; max-width: {MAXW}px; box-sizing: border-box; }}
table {{ border-collapse: collapse; font: 14px/1.5 -apple-system, "PingFang SC", sans-serif; color: #222; min-width: {WIDTH - 12}px; }}
th, td {{ border-top: 1px solid #ddd; border-bottom: 1px solid #ddd; padding: 6px 10px; text-align: left; vertical-align: top; }}
th {{ font-weight: 600; background: #f3f5f8; border-top: 2px solid #555; border-bottom: 1px solid #555; }}
tr:last-child td {{ border-bottom: 2px solid #555; }}
code {{ font-family: Menlo, monospace; font-size: 12.5px; }}
a {{ color: #2a5db0; text-decoration: none; }}
'''
img_dir = os.path.join(OUT, 'img')
os.makedirs(img_dir, exist_ok=True)
tmp = tempfile.mkdtemp()
chrome = [CHROME, '--headless=new', '--disable-gpu', '--hide-scrollbars', '--no-first-run',
          f'--user-data-dir={tmp}/profile']

# 第一遍：所有表放在一页，量出每张表的宽高
probe = os.path.join(tmp, 'probe.html')
with open(probe, 'w', encoding='utf-8') as f:
    f.write(f'<html><head><meta charset="utf-8"><style>{TCSS} .wrap{{display:block;width:max-content;max-width:{MAXW}px}}</style></head><body>')
    for tid, tbl in tables:
        f.write(f'<div class="wrap" id="{tid}">{tbl}</div>')
    f.write('<pre id="out"></pre><script>'
            'const r={};document.querySelectorAll(".wrap").forEach(e=>{const b=e.getBoundingClientRect();'
            'r[e.id]=[Math.ceil(b.width),Math.ceil(b.height)]});'
            'document.getElementById("out").textContent="SIZES"+JSON.stringify(r)+"END";</script></body></html>')
dom = subprocess.run(chrome + [f'--window-size={WIDTH},2000', '--dump-dom', f'file://{probe}'],
                     capture_output=True, text=True, timeout=120).stdout
sizes = json.loads(html.unescape(re.search(r'SIZES(.*?)END', dom).group(1)))

# 第二遍：每张表单独截图，窗口大小等于表的大小
for i, (tid, tbl) in enumerate(tables, 1):
    w, h = sizes[tid]
    w = max(w, WIDTH)
    p = os.path.join(tmp, f'{tid}.html')
    with open(p, 'w', encoding='utf-8') as f:
        f.write(f'<html><head><meta charset="utf-8"><style>{TCSS}</style></head><body><div class="wrap" style="width:{w}px">{tbl}</div></body></html>')
    subprocess.run(chrome + [f'--window-size={w},{h}', f'--force-device-scale-factor={SCALE}',
                             f'--screenshot={os.path.join(img_dir, tid + ".png")}', f'file://{p}'],
                   capture_output=True, timeout=60)
    print(f'\r表格 {i}/{len(tables)}', end='', flush=True)
print()
shutil.rmtree(tmp, ignore_errors=True)
