#!/usr/bin/env python3
# 图 10-3（第 10.7 节，表 10-6）：单进程内不同提交方式的吞吐（相对同步调用，统一样式见 plotfig.py）。
# 数据：data/04_schedule/d2_async.txt。
import os
from plotfig import Plot, K, AXIS, GRID, C_BLUE, C_GREEN, C_ORANGE, C_GREY

SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'data', '04_schedule', 'd2_async.txt')
rows = {}
for line in open(SRC):
    f = line.split()
    if len(f) >= 10 and f[0].startswith(('k1x9_', 'k1x1_')) and f[2] in ('1', '2'):
        busy0, busy1 = float(f[7].rstrip('%')), float(f[8].rstrip('%'))
        rows.setdefault((f[0], f[1]), []).append((float(f[4]), busy0, busy1))

MODES = [
    ('sync', '同步', C_GREY),
    ('async_1', '异步（1 在途）', C_BLUE),
    ('async_2', '异步（2 在途）', C_BLUE),
    ('async_4', '异步（4 在途）', C_BLUE),
    ('batch_2', '批量（每批 2）', C_ORANGE),
    ('batch_8', '批量（每批 8）', C_ORANGE),
    ('2proc_async_2', '双进程（各 2）', C_GREEN),
]
PANELS = [
    ('k1x1_512_h1w128_L384', '(a) 权重常驻', 154, 18),
    ('k1x9_c256_h4w32_L80', '(b) 读权重受限', 490, 482),
]

RH, BH = 36, 20
H_PLOT = len(MODES) * RH  # 252

p = Plot(800, 376)
p.panel(4, 8, 452, 360)
p.panel(468, 8, 328, 360)

for j, (model, title, ax_x, tx) in enumerate(PANELS):
    ax = p.axes(x=ax_x, y=50, w=288, h=H_PLOT, xr=(0, 3.45), yr=(0, 1),
                xticks=[0, 1, 2, 3], xticklabels=['0', '1×', '2×', '3×'],
                yticks=[], xgrid=True, ygrid=False,
                xlabel='相对吞吐', title=title, title_x=tx)
    ax.vline(1, color='#999999', dash='4 3', sw=1.1)

    for i, (key, lab, col) in enumerate(MODES):
        yc = 50 + i * RH + RH / 2
        if j == 0:
            p.text(ax_x - 12, yc + 4.5, lab, 13, K, 'end', 400)
        r = rows[(model, key)]
        mean = sum(v[0] for v in r) / len(r)
        s, f = col
        bw = ax.X(mean) - ax.X(0)
        p.raw(f'<rect x="{ax.X(0):.1f}" y="{yc - BH / 2:.1f}" width="{bw:.1f}" height="{BH}" '
              f'fill="{f}" stroke="{AXIS}" stroke-width="0.9"/>')
        p.text(ax.X(mean) + 7, yc + 4.5, f'{mean:.2f}×', 13, s, 'start', 600)

print(p.save('fig10-3_submit_modes'))
