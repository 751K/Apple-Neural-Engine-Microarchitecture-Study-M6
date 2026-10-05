#!/usr/bin/env python3
# 图 10-1：单 ANE（宽 128）与双 ANE（宽 256）程序的耗时随层数的变化（第 10.3 节，表 10-1）。
# 数据：data/08_bonded/bond_ksweep_run.txt（512 通道 1×1 卷积链，高 1，共享权重；bondrun 每次调用耗时的中位数）。
# 处理：同一模型在文件中出现多次（两组扫描，各测两轮），取各次中位数的平均值作图（各次相差 ≤ 7 µs）；
#       边际耗时取 256 层与 384 层两点的斜率；每层计算量 = 2 × 512 × 512 × 宽 FLOP。
import os
import re
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from figplot import Chart, COLORS, FG3  # noqa: E402

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..')
pat = re.compile(r'k1x1_512_h1w(\d+)_L(\d+)\.mlmodelc\s+耗时 中位数 ([\d.]+) us')
runs = defaultdict(list)
for line in open(os.path.join(ROOT, 'data/08_bonded/bond_ksweep_run.txt')):
    m = pat.search(line)
    if m:
        runs[(int(m[1]), int(m[2]))].append(float(m[3]))
med = {k: sum(v) / len(v) for k, v in runs.items()}
LS = sorted({L for _, L in med})


def slope(w):
    return (med[(w, 384)] - med[(w, 256)]) / 128


s1, s2 = slope(128), slope(256)
tf1 = 2 * 512 * 512 * 128 / (s1 * 1e-6) / 1e12
tf2 = 2 * 512 * 512 * 256 / (s2 * 1e-6) / 1e12
sp = tf2 / tf1
print(f'单 ANE {s1:.3f} µs/层 {tf1:.1f} TFLOPS；双 ANE {s2:.3f} µs/层 {tf2:.1f} TFLOPS；加速比 {sp:.3f}')
for L in LS:
    print(L, f'{med[(128, L)]:.1f}', f'{med[(256, L)]:.1f}', runs[(128, L)], runs[(256, L)])

c = Chart(W=1000, H=540)
ax = c.axes(x=100, y=40, w=840, h=420, xr=(0, 400), yr=(0, 2000), xlabel='层数', ylabel='每次调用耗时（µs，中位数）',
            xticks=[0, 16, 48, 128, 256, 384], yticks=[0, 400, 800, 1200, 1600, 2000])
# 拟合区间
c.a(f'<rect x="{ax.X(256):.1f}" y="{ax.y}" width="{ax.X(384) - ax.X(256):.1f}" height="{ax.h}" fill="#f5f5f7"/>')
ax.text(320, 2000, '斜率拟合区间（256–384 层）', 'c', 'middle', dy=20)
# 斜率线（过 256、384 两点，向两侧延伸）
for w, s, col in ((128, s1, 0), (256, s2, 1)):
    y0 = med[(w, 256)]
    ax.line([100, 400], [y0 + (100 - 256) * s, y0 + (400 - 256) * s], color=COLORS[col], marker=False, dash=True, width=1.4)
ax.line(LS, [med[(256, L)] for L in LS], color=1, label='双 ANE 程序（宽 256）')
ax.line(LS, [med[(128, L)] for L in LS], color=0, label='单 ANE 程序（宽 128）')
# 标注


def ctext(vx, vy, s, col, anchor, dy):   # 带颜色的标注（figplot 的类样式会盖过 fill 属性，这里用 style）
    c.a(f'<text x="{ax.X(vx):.1f}" y="{ax.Y(vy) + dy:.1f}" text-anchor="{anchor}" style="font-size:13px;fill:{col}">{s}</text>')


ctext(300, med[(256, 256)] + 44 * s2, f'双 ANE：{s2:.2f} µs/层，{tf2:.1f} TFLOPS', COLORS[1][0], 'end', -16)
ctext(300, med[(128, 256)] + 44 * s1, f'单 ANE：{s1:.2f} µs/层，{tf1:.1f} TFLOPS', COLORS[0][0], 'start', 30)
ax.text(12, 1560, f'加速比（边际吞吐之比）{sp:.2f}', 'b')
ax.text(12, 1560, f'扩展效率 {sp / 2 * 100:.0f}%（加速比 ÷ 2）', 'c', dy=22)
ax.text(12, 1560, '双 ANE 每层的计算量为单 ANE 的 2 倍', 'c', dy=42)
c.legend(124, 72)
c.t(940, 528, '虚线：按 256 层与 384 层两点的斜率外推', 'c', 'end')
c.save('fig10-1_bonded_scaling')
