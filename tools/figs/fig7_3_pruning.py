#!/usr/bin/env python3
# 图 7-3（第 7.5 节）：剪枝率与每层相对耗时（权重常驻片上的计算受限层，统一样式见 plotfig.py）。
# 数据：data/05_compute/sparse/sparse.txt。
import os
import re
from collections import defaultdict
from plotfig import Plot, K, SUB, C_BLUE, C_GREEN

SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'data', '05_compute', 'sparse', 'sparse.txt')
RATE = {'fp16': 0, 's50': 50, 'nm24': 50, 's75': 75, 'nm34': 75, 's90': 90}
acc = defaultdict(list)
sec = None
for line in open(SRC):
    m = re.match(r'######## (m[46]_v2)\s*$', line.strip())
    if m:
        sec = m.group(1)
        continue
    if line.startswith('######## '):
        sec = None
        continue
    f = line.split()
    if sec and len(f) >= 6 and re.match(r'c(1x1|3x3)_\w+@rand#\d$', f[0]):
        shape, ver = f[0].split('@')[0].split('_', 1)
        if ver in RATE:
            acc[(sec[:2], shape, ver)].append(float(f[5]))
rel = {k: sum(v) / len(v) for k, v in acc.items()}

p = Plot(800, 412)
p.panel(4, 8, 390, 360)
p.panel(406, 8, 390, 360)

PANELS = [('c1x1', '(a) 1×1 卷积', 76, 18), ('c3x3', '(b) 3×3 卷积', 474, 420)]
for shape, title, ax_x, tx in PANELS:
    ax = p.axes(x=ax_x, y=50, w=302, h=256, xr=(-6, 96), yr=(0, 1.3),
                xticks=[0, 50, 75, 90], xticklabels=['0', '50%', '75%', '90%'],
                yticks=[0, 0.25, 0.5, 0.75, 1, 1.25], yticklabels=['0', '0.25', '0.5', '0.75', '1', '1.25'],
                xlabel='剪枝率', ylabel='相对耗时' if shape == 'c1x1' else None,
                title=title, title_x=tx)
    ax.hline(1, color='#c0c0c4', dash=None, sw=1.0)
    ax.line([0, 90], [1, 0.1], color=('#555555', '#ffffff'), marker=None, dash='5 4', width=1.4)
    for mach, col, dx in (('m6', C_BLUE, -2.0), ('m4', C_GREEN, 2.0)):
        xs = [0, 50, 75, 90]
        ys = [rel[(mach, shape, v)] for v in ('fp16', 's50', 's75', 's90')]
        ax.line([x + dx for x in xs], ys, color=col, marker='o', width=2.2, r=4.4)
        for v in ('nm24', 'nm34'):
            ax.point(RATE[v] + dx, rel[(mach, shape, v)], color=col, marker='S', r=4.2)
    if shape == 'c3x3':
        ax.text(48, 1.2, '失去 Winograd', 13, C_BLUE[0], 'middle', 600)

ly = 392
items = [
    (f'<svg xmlns="http://www.w3.org/2000/svg" width="26" height="14" viewBox="0 0 26 14"><line x1="0" y1="7" x2="26" y2="7" stroke="{C_BLUE[0]}" stroke-width="2.2"/><circle cx="13" cy="7" r="4" fill="#ffffff" stroke="{C_BLUE[0]}" stroke-width="2"/></svg>', 'M6'),
    (f'<svg xmlns="http://www.w3.org/2000/svg" width="26" height="14" viewBox="0 0 26 14"><line x1="0" y1="7" x2="26" y2="7" stroke="{C_GREEN[0]}" stroke-width="2.2"/><circle cx="13" cy="7" r="4" fill="#ffffff" stroke="{C_GREEN[0]}" stroke-width="2"/></svg>', 'M4'),
    (f'<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 14 14"><rect x="2.5" y="2.5" width="9" height="9" fill="#444444"/></svg>', '结构化剪枝'),
    (f'<svg xmlns="http://www.w3.org/2000/svg" width="26" height="14" viewBox="0 0 26 14"><line x1="0" y1="7" x2="26" y2="7" stroke="#555555" stroke-width="1.5" stroke-dasharray="5 4"/></svg>', '非零比例'),
]
parts = [f'<span style="display:flex;align-items:center;gap:7px">{ic}<span>{lb}</span></span>' for ic, lb in items]
p.raw(f'<foreignObject x="0" y="{ly - 14}" width="800" height="28"><div xmlns="http://www.w3.org/1999/xhtml" '
      f'style="display:flex;justify-content:center;gap:42px;align-items:center;height:28px;'
      f'font-family:Arial,\'Helvetica Neue\',\'PingFang SC\',sans-serif;font-size:13.5px;color:{K}">'
      + ''.join(parts) + '</div></foreignObject>')

print(p.save('fig7-3_pruning'))
