#!/usr/bin/env python3
# 图 14-1（第 14.3 节）：Qwen3.5-4B 在 ANE 上运行时的资源曲线（预填充 3072 词元、解码 384 词元）。
#   左列为标准模型，右列为定制模型（关闭 MTP）；上行为 ANE 忙碌比例，下行为读内存速率。
#   M6 的忙碌比例为两个 ANE 的平均；M6 的读带宽来自 IOReport 直方图，解码时部分采样落在最高档，
#   读数只是下限（空心点）。上方色条标出两台机器各自的预填充与解码时段。
# 数据：data/12_apps/ane_curve/（由 tools/12_apps/ane_curve_extract.py 从测评记录中提取）。
import csv
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from figplot import Chart, COLORS  # noqa: E402

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'data', '12_apps', 'ane_curve')
M4, M6 = COLORS[1], COLORS[0]
BOUND = {'M4': 67, 'M6': 150}


def load(name):
    rows = list(csv.DictReader(l for l in open(os.path.join(DATA, name + '.csv')) if not l.startswith('#')))
    t = [float(r['t_s']) for r in rows]
    ph = {}
    for r, tt in zip(rows, t):
        if r['phase'] in ('prefill', 'decode'):
            a, b = ph.get(r['phase'], (tt, tt))
            ph[r['phase']] = (min(a, tt), max(b, tt))
    return dict(t=t, busy=[float(r['busy_pct']) for r in rows], read=[float(r['dram_read_gbs']) for r in rows],
                clip=[float(r['dram_clipped_pct'] or 0) for r in rows], ph=ph)


COLS = [('标准模型（每词元 9 次调用）', 'standard', 33), ('定制模型，关闭 MTP（每词元 5 次调用）', 'custom', 27)]
W, H = 1200, 712
c = Chart(W, H)
PX, PW, GAP = 100, 490, 80
TOP = 74
BH_, RH = 230, 310           # 每个坐标区的高度、行距

for j, (title, key, xmax) in enumerate(COLS):
    x0 = PX + j * (PW + GAP)
    runs = {'M4': load('m4_' + key), 'M6': load('m6_' + key)}
    c.t(x0, TOP - 44, title, 'h2')
    sx = lambda v: x0 + (v + 2) / (xmax + 2) * PW
    for k, name in enumerate(('M4', 'M6')):          # 两台机器的阶段色条
        s, _ = M4 if name == 'M4' else M6
        yb = TOP - 30 + k * 12
        for pname, op in (('prefill', 0.95), ('decode', 0.35)):
            a, b = runs[name]['ph'][pname]
            c.a(f'<rect x="{sx(a):.1f}" y="{yb}" width="{sx(b) - sx(a):.1f}" height="8" fill="{s}" opacity="{op}"/>')
        c.t(x0 - 8, yb + 8, name, 'tk', 'end')
    for i, (key2, ylabel, yr, yt) in enumerate([('busy', 'ANE 忙碌比例（%）', (0, 100), [0, 20, 40, 60, 80, 100]),
                                               ('read', '读内存速率（GB/s）', (0, 160), [0, 40, 80, 120, 160])]):
        y0 = TOP + i * RH
        ax = c.axes(x=x0, y=y0, w=PW, h=BH_, xr=(-2, xmax), yr=yr, xticks=list(range(0, xmax + 1, 5)),
                    yticks=yt, xlabel='时间（s，自预填充开始）' if i == 1 else None,
                    ylabel=ylabel if j == 0 else None)
        if key2 == 'read':
            for name in ('M4', 'M6'):
                s, _ = M4 if name == 'M4' else M6
                ax.hline(BOUND[name], color=s)
                c.t(x0 + PW - 6, ax.Y(BOUND[name]) - 6, f'{name} 读权重上限约 {BOUND[name]} GB/s', 'c', 'end')
        for name in ('M4', 'M6'):
            r = runs[name]
            sel = [k for k, tt in enumerate(r['t']) if -2 <= tt <= xmax]
            col = M4 if name == 'M4' else M6
            ax.line([r['t'][k] for k in sel], [r[key2][k] for k in sel], color=col, marker=False, width=2.0,
                    label=(name if (i == 0 and j == 0) else None))
            if key2 == 'read':
                for k in sel:
                    if r['clip'][k] > 0:
                        c.a(f'<circle cx="{ax.X(r["t"][k]):.1f}" cy="{ax.Y(r["read"][k]):.1f}" r="3.4" fill="#ffffff" stroke="{col[0]}" stroke-width="1.6"/>')

# 图例（一行，固定位置，中英文都不重叠）
ly = TOP + RH + BH_ + 78
c.legend(PX, ly, dx=100, cols=2)
lx = PX + 200
c.a(f'<circle cx="{lx + 13}" cy="{ly - 4}" r="3.4" fill="#ffffff" stroke="{M6[0]}" stroke-width="1.6"/>')
c.t(lx + 30, ly + 1, '读数为下限（直方图最高档截顶）', 's')
for lx, op, lab in ((PX + 540, 0.95, '预填充'), (PX + 660, 0.35, '解码')):
    c.a(f'<rect x="{lx + 2}" y="{ly - 8}" width="22" height="8" fill="{M6[0]}" opacity="{op}"/>')
    c.t(lx + 30, ly + 1, lab, 's')
c.save('fig14-1_busy_bandwidth')
