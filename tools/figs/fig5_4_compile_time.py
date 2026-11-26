#!/usr/bin/env python3
# 图 5-4（第 5.9 节）：编译时间随层数的变化（双对数坐标，统一样式见 plotfig.py）。
# 数据：data/03_compile/h7_compile_time.txt（表 5-17、表 5-18）。
import os
import re
from plotfig import Plot, C_BLUE, C_GREEN, C_RED

SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'data', '03_compile', 'h7_compile_time.txt')
ew = {'h18': {}, 'h18g': {}}
conv = {}
for line in open(SRC):
    m = re.match(r'ovl_B(\d+) (h18g?) (?:返回 0 用时 )?([\d.]+)s', line)
    if m:
        ew[m.group(2)][2 * int(m.group(1))] = float(m.group(3))
    m = re.match(r'k1_c64_h1w1024_L256 (h18g?) 返回 0 用时 ([\d.]+)s', line)
    if m:
        conv[m.group(1)] = float(m.group(2))

p = Plot(800, 424)
p.panel(4, 8, 792, 408)
ax = p.axes(x=92, y=30, w=680, h=322, xr=(48, 860), yr=(0.025, 400),
            xlog=True, ylog=True, xgrid=True, ygrid=True, yminor=True,
            xlabel='层数', ylabel='编译时间 (s)',
            xticks=[64, 128, 256, 512],
            yticks=[0.1, 1, 10, 100], yticklabels=['0.1', '1', '10', '100'])

for name, col in (('h18g', C_BLUE), ('h18', C_GREEN)):
    xs = sorted(ew[name])
    ax.line(xs, [ew[name][x] for x in xs], color=col, marker='o', label=name)

for name, col in (('h18g', C_BLUE), ('h18', C_GREEN)):
    ax.point(256, conv[name], color=col, marker='s', r=5.2)

x512 = ax.X(512)
y0, y1 = ax.Y(ew['h18'][512]), ax.Y(ew['h18g'][512])
bx = x512 + 18
p.raw(f'<line x1="{bx:.1f}" y1="{y0:.1f}" x2="{bx:.1f}" y2="{y1:.1f}" stroke="{C_RED[0]}" stroke-width="1.5"/>')
for yy in (y0, y1):
    p.raw(f'<line x1="{bx - 5:.1f}" y1="{yy:.1f}" x2="{bx + 5:.1f}" y2="{yy:.1f}" stroke="{C_RED[0]}" stroke-width="1.5"/>')
p.text(bx + 12, (y0 + y1) / 2 + 5, f'{ew["h18g"][512] / ew["h18"][512]:.0f}×', 16, C_RED[0], 'start', 600)

p.leg.append(('squares', (C_BLUE[0], C_GREEN[0]), None, None, None, '1×1 卷积'))
p.legend_box(114, 58, dy=25)

print(p.save('fig5-4_compile_time'))
