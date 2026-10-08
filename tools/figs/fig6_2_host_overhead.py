#!/usr/bin/env python3
# 图 6-2（第 6.5.2–6.5.3 节，表 6-5）：任务结束之后的主机开销与任务时长。
#   横轴为"驱动提交 → 任务结束"（单 ANE 程序的任务开始事件不全，约等于任务时长加约 30 µs 的提交侧开销），
#   纵轴为"任务结束 → 下次提交"，均取中位数。A 组为 512 通道、16–384 层；B 组为 1024 通道、4–96 层，
#   相同计算量下层数相差 4 倍。空心菱形为后台运行 12 个空转进程（阻止 CPU 深度空闲）时的 A 组，箭头连向同一模型。
# 数据：data/04_schedule/d1b_stages.txt。
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from figplot import Chart, COLORS, FG2  # noqa: E402

SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'data', '04_schedule', 'd1b_stages.txt')
pts = {}
for line in open(SRC):
    m = re.match(r'\s*(c512|c1024) L(\d+)( 空转)?\s+\d+\s+[\d.]+\s+[\d.]+\s+([\d.]+)\s+([\d.]+)', line)
    if m:
        pts[(m.group(1), int(m.group(2)), bool(m.group(3)))] = (float(m.group(4)), float(m.group(5)))

A, B, SP = COLORS[0], COLORS[1], COLORS[4]
c = Chart(1000, 580)
ax = c.axes(x=100, y=40, w=700, h=420, xr=(0, 1500), yr=(80, 360),
            xlabel='驱动提交 → 任务结束（µs，约为任务时长加 30 µs）', ylabel='任务结束 → 下次提交（µs）',
            xticks=[0, 250, 500, 750, 1000, 1250, 1500], yticks=[80, 120, 160, 200, 240, 280, 320, 360])
for v, lab in ((350, '约 350 µs'), (660, '约 660 µs')):
    ax.vline(v, lab, ty=58)


def mark(x, y, col, shape, hollow=False):
    X, Y = ax.X(x), ax.Y(y)
    fill = '#ffffff' if hollow else col[0]
    if shape == 'o':
        c.a(f'<circle cx="{X:.1f}" cy="{Y:.1f}" r="5.5" fill="{fill}" stroke="{col[0]}" stroke-width="1.8"/>')
    elif shape == 's':
        c.a(f'<rect x="{X - 5:.1f}" y="{Y - 5:.1f}" width="10" height="10" fill="{fill}" stroke="{col[0]}" stroke-width="1.8"/>')
    else:
        c.a(f'<path d="M{X:.1f} {Y - 7.5:.1f} L{X + 7.5:.1f} {Y:.1f} L{X:.1f} {Y + 7.5:.1f} L{X - 7.5:.1f} {Y:.1f} Z" fill="#ffffff" stroke="{col[0]}" stroke-width="2"/>')


for grp, col, shape in (('c512', A, 'o'), ('c1024', B, 's')):
    ks = sorted(k for k in pts if k[0] == grp and not k[2])
    xs, ys = [pts[k][0] for k in ks], [pts[k][1] for k in ks]
    ax.line(xs, ys, color=col, marker=False, width=1.2)
    for x, y in zip(xs, ys):
        mark(x, y, col, shape)
# 空转进程：从同一模型的正常测量指向空转时的测量
for L in (16, 96, 384):
    (x0, y0), (x1, y1) = pts[('c512', L, False)], pts[('c512', L, True)]
    mark(x1, y1, SP, 'd')
    X0, Y0, X1, Y1 = ax.X(x0), ax.Y(y0), ax.X(x1), ax.Y(y1)
    dist = ((X1 - X0) ** 2 + (Y1 - Y0) ** 2) ** 0.5
    if dist > 24:   # 两端各缩进，避免压住符号
        ux, uy = (X1 - X0) / dist, (Y1 - Y0) / dist
        c.a(f'<path d="M{X0 + ux * 9:.1f} {Y0 + uy * 9:.1f} L{X1 - ux * 12:.1f} {Y1 - uy * 12:.1f}" stroke="{SP[0]}" stroke-width="1.4" fill="none" marker-end="url(#a)"/>')
# 层数标注（A 组 / B 组，计算量相同的一对）
for la, lb in ((16, 4), (96, 24), (384, 96)):
    xa, ya = pts[('c512', la, False)]
    xb, yb = pts[('c1024', lb, False)]
    if la == 96:     # 这一对在阈值附近，标注放到 A 组点的右下方
        c.t(ax.X(xa) + 14, ax.Y(ya) + 20, f'{la} 层 / {lb} 层', 'c', 'start')
    else:
        c.t(ax.X((xa + xb) / 2), ax.Y(max(ya, yb)) - 14, f'{la} 层 / {lb} 层', 'c', 'middle')
x1, y1 = pts[('c512', 384, True)]
c.t(ax.X(x1) - 10, ax.Y(y1) + 24, '384 层，空转进程', 'c', 'end', SP[0])

ly = 40 + 420 + 86                                 # 图例放在坐标区下方，一行
for (lab, col, shape), X in zip((('A 组：512 通道，16–384 层', A, 'o'), ('B 组：1024 通道，4–96 层', B, 's'),
                                  ('A 组，后台 12 个空转进程', SP, 'd')), (110, 380, 650)):
    Y = ly
    if shape == 'o':
        c.a(f'<circle cx="{X}" cy="{Y - 4}" r="5.5" fill="{col[0]}" stroke="{col[0]}" stroke-width="1.8"/>')
    elif shape == 's':
        c.a(f'<rect x="{X - 5}" y="{Y - 9}" width="10" height="10" fill="{col[0]}" stroke="{col[0]}" stroke-width="1.8"/>')
    else:
        c.a(f'<path d="M{X} {Y - 11.5} L{X + 7.5} {Y - 4} L{X} {Y + 3.5} L{X - 7.5} {Y - 4} Z" fill="#ffffff" stroke="{col[0]}" stroke-width="2"/>')
    c.t(X + 16, Y + 1, lab, 's')
c.save('fig6-2_host_overhead')
