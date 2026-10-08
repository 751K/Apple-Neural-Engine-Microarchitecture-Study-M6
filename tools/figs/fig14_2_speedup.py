#!/usr/bin/env python3
# 图 14-2（第 14.6 节）：各项实际任务在 ANE 上的 M6 ÷ M4 加速比。
#   数值取自表 14-1、表 14-4（标准模型；ResNet-50 一次 1 张为复测范围），颜色对应第 14.2 节的预期。
#   两条竖线为参照值：单引擎 FP16 峰值之比约 1.1（21.1 ÷ 约 19 TFLOPS），双引擎峰值之比约 2.2（42.3 ÷ 约 19）。
# 数据：第 14 章的整机测评记录（表 14-1、表 14-4）。
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from figplot import Chart, COLORS, FG2  # noqa: E402

E1, E2, E3, E4 = COLORS[0], COLORS[2], COLORS[1], COLORS[5]
ROWS = [  # (任务, 加速比或 (下限, 上限), 颜色)
    ('文字检测（CRAFT）', 2.69, E1),
    ('ResNet-50，一次 16 张', 2.33, E1),
    ('大语言模型解码（标准模型）', 1.86, E3),
    ('大语言模型预填充（标准模型）', 1.83, E1),
    ('ResNet-50，一次 1 张', 1.42, E2),
    ('文字识别（含 CPU 上的 LSTM）', 1.41, E4),
]
c = Chart(1000, 470)
X0, AW, RH, BH, Y0 = 300, 560, 46, 22, 40
ax = c.axes(x=X0, y=Y0, w=AW, h=len(ROWS) * RH, xr=(0, 3), yr=(0, 1), xticks=[0, 0.5, 1, 1.5, 2, 2.5, 3],
            xticklabels=['0', '0.5', '1', '1.5', '2', '2.5', '3'], yticks=[], grid=False, xlabel='M6 ÷ M4（ANE 上的速度之比）')
for v, lab in ((1.1, '单引擎峰值之比约 1.1（参照）'), (2.2, '双引擎峰值之比约 2.2（参照）')):
    X = ax.X(v)
    c.a(f'<line x1="{X:.1f}" y1="{Y0 - 8}" x2="{X:.1f}" y2="{Y0 + len(ROWS) * RH}" stroke="{FG2}" stroke-width="1.2" stroke-dasharray="5 4"/>')
    c.t(X + (6 if v > 2 else -6), Y0 - 14, lab, 'c', 'start' if v > 2 else 'end')
for i, (lab, val, (s, f)) in enumerate(ROWS):
    yc = Y0 + i * RH + RH / 2
    c.t(X0 - 14, yc + 5, lab, 'b', 'end')
    if isinstance(val, tuple):
        lo, hi = val
        c.a(f'<rect x="{ax.X(0):.1f}" y="{yc - BH / 2:.1f}" width="{ax.X(lo) - ax.X(0):.1f}" height="{BH}" fill="{f}" stroke="{s}" stroke-width="1.3"/>')
        c.a(f'<rect x="{ax.X(lo):.1f}" y="{yc - BH / 2:.1f}" width="{ax.X(hi) - ax.X(lo):.1f}" height="{BH}" fill="{f}" stroke="{s}" stroke-width="1.3" stroke-dasharray="4 3"/>')
        c.t(ax.X(hi) + 8, yc + 5, f'{lo:.2f}–{hi:.2f}', 's')
    else:
        c.a(f'<rect x="{ax.X(0):.1f}" y="{yc - BH / 2:.1f}" width="{ax.X(val) - ax.X(0):.1f}" height="{BH}" fill="{f}" stroke="{s}" stroke-width="1.3"/>')
        c.t(ax.X(val) + 8, yc + 5, f'{val:.2f}', 's')
ly = Y0 + len(ROWS) * RH + 84
items = [(E1, '预期一：计算密集'), (E2, '预期二：每次调用工作量小'), (E3, '预期三：解码受读权重与调用次数限制'), (E4, '预期四：部分运算在 CPU 上')]
for ((s, f), lab), (lx, dy) in zip(items, ((60, 0), (420, 0), (60, 26), (420, 26))):
    c.a(f'<rect x="{lx}" y="{ly + dy - 11}" width="16" height="14" rx="2" fill="{f}" stroke="{s}" stroke-width="1.3"/>')
    c.t(lx + 24, ly + dy + 1, lab, 's')
c.save('fig14-2_speedup')
