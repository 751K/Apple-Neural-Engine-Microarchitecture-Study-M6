#!/usr/bin/env python3
# 图 6-2（第 6.5.2–6.5.3 节，表 6-5）：任务结束之后的主机开销与任务时长（统一样式见 plotfig.py）。
# 数据：data/04_schedule/d1b_stages.txt。
import os
import re
from plotfig import Plot, SUB, C_BLUE, C_GREEN, C_RED

SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'data', '04_schedule', 'd1b_stages.txt')
pts = {}
for line in open(SRC):
    m = re.match(r'\s*(c512|c1024) L(\d+)( 空转)?\s+\d+\s+[\d.]+\s+[\d.]+\s+([\d.]+)\s+([\d.]+)', line)
    if m:
        pts[(m.group(1), int(m.group(2)), bool(m.group(3)))] = (float(m.group(4)), float(m.group(5)))

p = Plot(800, 424)
p.panel(4, 8, 792, 408)
ax = p.axes(x=92, y=30, w=680, h=322, xr=(0, 1520), yr=(80, 360),
            xlabel='提交 → 任务结束 (µs)', ylabel='任务结束 → 下次提交 (µs)',
            xticks=[0, 250, 500, 750, 1000, 1250, 1500],
            yticks=[80, 120, 160, 200, 240, 280, 320, 360])

for v in (350, 660):
    ax.vline(v, color='#888888', dash='4 3', sw=1.1)
    ax.text(v, 360, str(v), 12.5, SUB, 'start', 600, dx=5, dy=15)

for grp, col, mk, lab in (('c512', C_BLUE, 'O', 'A 组 (512 ch)'), ('c1024', C_GREEN, 'S', 'B 组 (1024 ch)')):
    ks = sorted(k for k in pts if k[0] == grp and not k[2])
    xs, ys = [pts[k][0] for k in ks], [pts[k][1] for k in ks]
    ax.line(xs, ys, color=col, marker=mk, width=1.8, r=4.6, label=lab)

for L in (16, 96, 384):
    p0, p1 = pts[('c512', L, False)], pts[('c512', L, True)]
    ax.arrow(p0, p1, color=C_RED, sw=1.6, pad0=8, pad1=10)
    ax.point(p1[0], p1[1], color=C_RED, marker='d', r=5.4)

for la, lb in ((16, 4), (96, 24), (384, 96)):
    xa, ya = pts[('c512', la, False)]
    xb, yb = pts[('c1024', lb, False)]
    if la == 96:
        ax.text(xa, ya, f'{la}/{lb}', 12.5, SUB, 'start', 400, dx=11, dy=15)
    else:
        ax.text((xa + xb) / 2, max(ya, yb), f'{la}/{lb}', 12.5, SUB, 'middle', 400, dy=-12)

p.leg.append(('dot', C_RED[0], None, 'd', '#ffffff', 'A 组 + 空转进程'))
p.legend_box(556, 272, dy=25)

print(p.save('fig6-2_host_overhead'))
