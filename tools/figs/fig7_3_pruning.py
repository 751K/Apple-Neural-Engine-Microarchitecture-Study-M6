#!/usr/bin/env python3
# 图 7-3（第 7.5 节）：剪枝率与每层相对耗时（权重常驻片上的计算受限层）。
#   (a) 1×1 卷积链（512 通道，1×128）；(b) 3×3 卷积链（512 通道，16×16）。纵轴为每层耗时 ÷ 稠密 FP16，
#   取第二轮（m6_v2 / m4_v2）两遍的平均；圆点为非结构化剪枝，方块为结构化剪枝（2:4、1:4）。
#   虚线为"耗时按非零权重比例缩短"的理想情形。M6 用 kdebug 中提交到任务结束的时长求斜率，M4 用调用耗时。
# 数据：data/05_compute/sparse/sparse.txt。
import os
import re
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from figplot import Chart, COLORS, FG2  # noqa: E402

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

M6, M4 = COLORS[0], COLORS[1]
c = Chart(1080, 520)
PANELS = [('c1x1', '(a) 1×1 卷积（512 通道，1×128）'), ('c3x3', '(b) 3×3 卷积（512 通道，16×16）')]
X0s = (100, 600)
for (shape, title), x0 in zip(PANELS, X0s):
    ax = c.axes(x=x0, y=50, w=400, h=360, xr=(-5, 95), yr=(0, 1.3), xticks=[0, 50, 75, 90],
                xticklabels=['0', '50%', '75%', '90%'], yticks=[0, 0.25, 0.5, 0.75, 1, 1.25],
                yticklabels=['0', '0.25', '0.5', '0.75', '1', '1.25'], xlabel='剪枝率',
                ylabel='每层耗时（相对稠密）' if x0 == X0s[0] else None, title=title)
    ax.line([0, 90], [1, 0.1], color=(FG2, '#ffffff'), marker=False, dash=True, width=1.4)
    ax.hline(1, color='#c7c7cc', dash=False)
    for mach, col, dx in (('m6', M6, -2.2), ('m4', M4, 2.2)):
        xs = [0, 50, 75, 90]
        ys = [rel[(mach, shape, v)] for v in ('fp16', 's50', 's75', 's90')]
        ax.line([x + dx for x in xs], ys, color=col, marker=True, width=2.0, r=5)
        for v in ('nm24', 'nm34'):
            X, Y = ax.X(RATE[v] + dx), ax.Y(rel[(mach, shape, v)])
            c.a(f'<rect x="{X - 4.5:.1f}" y="{Y - 4.5:.1f}" width="9" height="9" fill="{col[0]}" stroke="{col[0]}" stroke-width="1.4"/>')
    c.t(ax.X(88), ax.Y(0.1) + 22, '按非零比例', 'c', 'end')
    if shape == 'c3x3':
        y = rel[('m6', 'c3x3', 's50')]
        c.t(ax.X(50), ax.Y(1.2), 'M6 剪枝后不再使用 Winograd', 's', 'middle', M6[0])

ly = 50 + 360 + 84
items = [('line', M6, 'M6'), ('line', M4, 'M4'), ('sq', FG2, '结构化剪枝（2:4、1:4）'), ('dash', FG2, '耗时按非零比例缩短（理想）')]
for (kind, col, lab), lx in zip(items, (100, 200, 300, 540)):
    cc = col[0] if isinstance(col, tuple) else col
    if kind == 'line':
        c.a(f'<line x1="{lx}" y1="{ly - 4}" x2="{lx + 26}" y2="{ly - 4}" stroke="{cc}" stroke-width="2"/>'
            f'<circle cx="{lx + 13}" cy="{ly - 4}" r="5" fill="#ffffff" stroke="{cc}" stroke-width="1.8"/>')
    elif kind == 'sq':
        c.a(f'<rect x="{lx + 8}" y="{ly - 9}" width="9" height="9" fill="{cc}"/>')
    else:
        c.a(f'<line x1="{lx}" y1="{ly - 4}" x2="{lx + 26}" y2="{ly - 4}" stroke="{cc}" stroke-width="1.4" stroke-dasharray="6 4"/>')
    c.t(lx + 34, ly + 1, lab, 's')
c.save('fig7-3_pruning')
