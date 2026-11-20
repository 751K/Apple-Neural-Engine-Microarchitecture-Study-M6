#!/usr/bin/env python3
# 把报告导出为 A4 的 PDF：final_report/zh.md → final_report/zh_preview.pdf（--lang en 时为 en.md → en_preview.pdf）。
#   - 用与网页相同的 markdown-it 渲染，套一份打印样式（正文衬线、标题苹方、二级标题下划线、图表标题居中），
#     再由本机 Chrome 无头模式打印，版式仿照 2026-10-08 的预览 PDF；
#   - 正文中的 ../tools/…、../data/… 链接改写为 GitHub 上的地址，图用 figs/<语言>/light/ 的 PNG；
#   - 中间的 HTML 写在临时目录，不留在仓库里。
# 用法：python3 tools/site/pdf.py [--lang zh|en] [--out PDF] [--keep-html]
# 依赖：markdown-it-py；Google Chrome（/Applications/Google Chrome.app）
import argparse
import os
import re
import subprocess
import tempfile

from markdown_it import MarkdownIt

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
REPO = 'https://github.com/751K/Apple-Neural-Engine-Microarchitecture-Study-M6'
CHROME = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'

ap = argparse.ArgumentParser()
ap.add_argument('--lang', default='zh', choices=('zh', 'en'))
ap.add_argument('--out')
ap.add_argument('--keep-html', action='store_true', help='保留中间 HTML（打印前检查版式用）')
args = ap.parse_args()
src = os.path.join(ROOT, 'final_report', f'{args.lang}.md')
out = args.out or os.path.join(ROOT, 'final_report', f'{args.lang}_preview.pdf')

md = MarkdownIt('commonmark', {'html': True}).enable('table')
body = md.render(open(src, encoding='utf-8').read())


def link(m):
    """../tools/x、../data/x → GitHub；目录（以 / 结尾）用 tree，文件用 blob。"""
    path = m.group(2)
    kind = 'tree' if path.endswith('/') else 'blob'
    return f'{m.group(1)}="{REPO}/{kind}/main/{path}"'


body = re.sub(r'(href)="\.\./((?:tools|data|notes)/[^"]*)"', link, body)
body = re.sub(r'src="\.\./(figs/[^"]*)"', lambda m: f'src="file://{os.path.join(ROOT, m.group(1))}"', body)
# 只含一个 <em>表 …</em> / <em>图 …</em>（英文 Table / Figure）的段落是图表标题
body = re.sub(r'<p><em>((?:表|图|Table|Figure) [^<]*(?:<[^>]+>[^<]*)*?)</em></p>',
              r'<p class="cap">\1</p>', body)

CSS = '''
@page { size: A4; margin: 16mm 15mm 16mm 15mm; }
html { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
body { font-family: "Times New Roman", "Songti SC", serif; font-size: 9.6pt; line-height: 1.62; color: #111; margin: 0; }
h1, h2, h3, h4, .cap, th { font-family: "PingFang SC", "Helvetica Neue", sans-serif; font-weight: 600; }
h1 { font-size: 17pt; text-align: center; line-height: 1.35; margin: 10mm 0 8mm; }
h2 { font-size: 13pt; border-bottom: 0.6pt solid #999; padding-bottom: 2pt; margin: 9mm 0 4mm; }
h3 { font-size: 11pt; margin: 6mm 0 3mm; }
h4 { font-size: 10pt; margin: 5mm 0 2.5mm; }
h2, h3, h4 { break-after: avoid; page-break-after: avoid; }
p { margin: 0 0 2.6mm; text-align: justify; }
a { color: #2a5db0; text-decoration: none; }
code { font-family: Menlo, "PingFang SC", monospace; font-size: 8.6pt; }
pre { background: #f5f5f5; padding: 2.5mm 3mm; font-size: 8.2pt; line-height: 1.45; white-space: pre-wrap; break-inside: avoid; }
pre code { font-size: inherit; }
.cap { text-align: center; font-size: 8.8pt; font-weight: 500; margin: 4mm 0 1.5mm; break-after: avoid; page-break-after: avoid; }
img + .cap, p:has(> img) + .cap { margin-top: 1.5mm; font-weight: 400; color: #333; }
table { border-collapse: collapse; margin: 0 auto 4mm; font-size: 8.4pt; line-height: 1.45; max-width: 100%; }
th, td { border: 0.5pt solid #bbb; padding: 1.2mm 1.8mm; vertical-align: top; }
th { background: #eee; font-size: 8.4pt; }
tr { break-inside: avoid; }
img { display: block; max-width: 100%; max-height: 120mm; margin: 2mm auto; }
p:has(> img) { text-align: center; break-inside: avoid; }
ul, ol { margin: 0 0 2.6mm; padding-left: 6mm; }
li { margin-bottom: 1mm; }
blockquote { margin: 0 0 2.6mm; padding-left: 4mm; border-left: 2pt solid #ccc; color: #444; }
'''
html = f'''<!doctype html><html lang="{args.lang}"><head><meta charset="utf-8">
<title>M6 ANE report</title><style>{CSS}</style></head><body>{body}</body></html>'''

tmp = tempfile.mkdtemp(prefix='anepdf.')
hp = os.path.join(tmp, f'{args.lang}.html')
open(hp, 'w', encoding='utf-8').write(html)
subprocess.run([CHROME, '--headless=new', '--disable-gpu', f'--user-data-dir={os.path.join(tmp, "chrome")}',
                '--no-pdf-header-footer', '--virtual-time-budget=20000', f'--print-to-pdf={out}', 'file://' + hp],
               check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
print(out, f'（中间 HTML：{hp}）' if args.keep_html else '')
if not args.keep_html:
    subprocess.run(['rm', '-rf', tmp])
