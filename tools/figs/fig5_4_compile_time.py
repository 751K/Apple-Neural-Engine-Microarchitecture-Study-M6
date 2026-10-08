#!/usr/bin/env python3
# 图 5-4（第 5.9 节）：编译时间随层数的变化（双对数坐标）。
#   逐元素运算链 y ← y·u + u（每步一个乘法和一个加法）分别编译为 h18（单引擎）与 h18g（双引擎）；
#   另以 256 层 1×1 卷积链（64 通道，宽 1024）作对照。
# 数据：data/03_compile/h7_compile_time.txt（表 5-17、表 5-18）。
import math
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from figplot import Chart, COLORS, FG2  # noqa: E402

SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'data', '03_compile', 'h7_compile_time.txt')
ew = {'h18': {}, 'h18g': {}}
conv = {}
for line in open(SRC):
    m = re.match(r'ovl_B(\d+) (h18g?) (?:返回 0 用时 )?([\d.]+)s', line)
    if m:
        ew[m.group(2)][2 * int(m.group(1))] = float(m.group(3))   # 每步两个逐元素层
    m = re.match(r'k1_c64_h1w1024_L256 (h18g?) 返回 0 用时 ([\d.]+)s', line)
    if m:
        conv[m.group(1)] = float(m.group(2))

SINGLE, DUAL = COLORS[1], COLORS[0]
c = Chart(940, 540)
ax = c.axes(x=110, y=40, w=640, h=420, xr=(48, 680), yr=(0.02, 400), xlog=True, ylog=True,
            xlabel='层数（对数坐标）', ylabel='编译时间（s，对数坐标）',
            xticks=[64, 128, 256, 512], yticks=[0.1, 1, 10, 100], yticklabels=['0.1', '1', '10', '100'])
for v in (64, 128, 256, 512):
    c.a(f'<line x1="{ax.X(v):.1f}" y1="40" x2="{ax.X(v):.1f}" y2="460" stroke="#e5e5ea" stroke-width="1"/>')
for name, col, lab in (('h18', SINGLE, 'h18（单引擎），逐元素运算链'), ('h18g', DUAL, 'h18g（双引擎），逐元素运算链')):
    xs = sorted(ew[name])
    ax.line(xs, [ew[name][x] for x in xs], color=col, label=lab)
# 卷积链对照（空心方块）
for name, col in (('h18', SINGLE), ('h18g', DUAL)):
    x, y = ax.X(256), ax.Y(conv[name])
    c.a(f'<rect x="{x - 6:.1f}" y="{y - 6:.1f}" width="12" height="12" fill="#ffffff" stroke="{col[0]}" stroke-width="2"/>')

# 斜率与倍数标注
s1 = math.log(ew['h18g'][256] / ew['h18g'][128]) / math.log(2)
s2 = math.log(ew['h18g'][512] / ew['h18g'][256]) / math.log(2)
k1 = math.log(ew['h18'][512] / ew['h18'][64]) / math.log(8)
c.t(ax.X(300), ax.Y(ew['h18g'][300 if 300 in ew['h18g'] else 256]) - 30, f'双对数斜率约 {min(s1, s2):.1f}–{max(s1, s2):.1f}', 's', 'end', DUAL[0])
c.t(ax.X(180), ax.Y(ew['h18'][192]) + 30, f'双对数斜率约 {k1:.1f}', 's', 'middle', SINGLE[0])
x512 = ax.X(512)
y0, y1 = ax.Y(ew['h18'][512]), ax.Y(ew['h18g'][512])
c.a(f'<line x1="{x512 + 16:.1f}" y1="{y0:.1f}" x2="{x512 + 16:.1f}" y2="{y1:.1f}" stroke="{FG2}" stroke-width="1.2"/>')
for yy in (y0, y1):
    c.a(f'<line x1="{x512 + 11:.1f}" y1="{yy:.1f}" x2="{x512 + 21:.1f}" y2="{yy:.1f}" stroke="{FG2}" stroke-width="1.2"/>')
c.t(x512 + 28, (y0 + y1) / 2 + 5, f'{ew["h18g"][512] / ew["h18"][512]:.0f} 倍', 'b')
c.t(x512 + 28, (y0 + y1) / 2 + 24, f'{ew["h18g"][512]:.0f} s 对 {ew["h18"][512]:.2f} s', 'c')

c.legend(130, 72)
for k, col in enumerate((SINGLE, DUAL)):     # 两个空心方块：h18、h18g
    c.a(f'<rect x="{130 + k * 16}" y="{109}" width="11" height="11" fill="#ffffff" stroke="{col[0]}" stroke-width="2"/>')
c.t(170, 120, '1×1 卷积链 256 层（对照，h18 / h18g）', 's')
c.save('fig5-4_compile_time')
