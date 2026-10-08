#!/usr/bin/env python3
# 图 10-3（第 10.7 节，表 10-6）：单进程内不同提交方式的吞吐（相对同步调用）。
#   左：权重常驻的 1×1 卷积链（512 通道，1×128，384 层）；右：读权重受限的 1×9 改写核（256 通道，4×32，80 层）。
#   条为两轮的平均（两轮之差不超过 0.05 倍）；右侧注出两个引擎的忙碌比例（两轮平均）。
# 数据：data/04_schedule/d2_async.txt（tools/04_schedule/d2_async_fit.py 的汇总表）。
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from figplot import Chart, COLORS, FG2  # noqa: E402

SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'data', '04_schedule', 'd2_async.txt')
rows = {}
for line in open(SRC):
    f = line.split()
    if len(f) >= 10 and f[0].startswith(('k1x9_', 'k1x1_')) and f[2] in ('1', '2'):
        busy0, busy1 = float(f[7].rstrip('%')), float(f[8].rstrip('%'))
        rows.setdefault((f[0], f[1]), []).append((float(f[4]), busy0, busy1))

MODES = [('sync', '同步', 5), ('async_1', '异步，1 个在途', 0), ('async_2', '异步，2 个在途', 0), ('async_4', '异步，4 个在途', 0),
         ('batch_2', '批量，每批 2 个', 2), ('batch_8', '批量，每批 8 个', 2), ('2proc_async_2', '两个进程，各异步 2 个', 1)]
PANELS = [('k1x1_512_h1w128_L384', '(a) 权重常驻：1×1 卷积，512 通道，384 层'),
          ('k1x9_c256_h4w32_L80', '(b) 读权重受限：1×9 改写核，256 通道，80 层')]

W, H = 1180, 460
c = Chart(W, H)
LX, PW, GAP = 240, 340, 160
RH, BH, Y0 = 46, 22, 70
for j, (model, title) in enumerate(PANELS):
    x0 = LX + j * (PW + GAP)
    ax = c.axes(x=x0, y=Y0, w=PW, h=len(MODES) * RH, xr=(0, 3), yr=(0, 1), xticks=[0, 1, 2, 3],
                xticklabels=['0', '1×', '2×', '3×'], yticks=[], grid=False, title=title,
                xlabel='吞吐（相对同步调用）')
    for v in (1, 2, 3):
        c.a(f'<line x1="{ax.X(v):.1f}" y1="{Y0}" x2="{ax.X(v):.1f}" y2="{Y0 + len(MODES) * RH}" stroke="#e5e5ea" stroke-width="1"/>')
    for i, (key, lab, ci) in enumerate(MODES):
        yc = Y0 + i * RH + RH / 2
        if j == 0:
            c.t(LX - 14, yc + 5, lab, 'b', 'end')
        r = rows[(model, key)]
        mult = [v[0] for v in r]
        mean = sum(mult) / len(mult)
        s, f = COLORS[ci]
        c.a(f'<rect x="{ax.X(0):.1f}" y="{yc - BH / 2:.1f}" width="{ax.X(mean) - ax.X(0):.1f}" height="{BH}" fill="{f}" stroke="{s}" stroke-width="1.3"/>')
        b0 = sum(v[1] for v in r) / len(r)
        b1 = sum(v[2] for v in r) / len(r)
        c.t(ax.X(mean) + 8, yc - 1, f'{mean:.2f}×', 's')
        c.t(ax.X(mean) + 8, yc + 14, f'忙碌 {b0:.0f}% / {b1:.0f}%', 'c')
c.save('fig10-3_submit_modes')
