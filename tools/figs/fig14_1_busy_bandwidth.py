#!/usr/bin/env python3
# 图 14-1（第 14.3 节）：Qwen3.5-4B 在 ANE 上运行时的忙碌比例与读内存速率（统一样式见 plotfig.py）。
# 数据：data/12_apps/ane_curve/。
import csv
import os
from plotfig import Plot, K, TICK, C_BLUE, C_GREEN

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'data', '12_apps', 'ane_curve')
M6, M4 = C_BLUE, C_GREEN
BOUND = {'M6': 150, 'M4': 67}


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


COLS = [
    ('(a) 标准模型（9 次/词元）', 'standard', 33, [0, 10, 20, 30], 80, 18),
    ('(b) 定制模型（5 次/词元）', 'custom', 27, [0, 5, 10, 15, 20, 25], 478, 420),
]

p = Plot(800, 562)
p.panel(4, 8, 390, 512)
p.panel(406, 8, 390, 512)

PW = 298
H_SUB = 170

for j, (title, key, xmax, xticks, x0, tx) in enumerate(COLS):
    runs = {'M6': load('m6_' + key), 'M4': load('m4_' + key)}
    p.text(tx, 34, title, 15.5, K, 'start', 600)

    # 顶部的预填充 / 解码阶段色条
    sx = lambda v: x0 + (v + 2) / (xmax + 2) * PW
    for k, (name, col) in enumerate((('M6', M6), ('M4', M4))):
        yb = 45 + k * 14
        for pname, op in (('prefill', 0.92), ('decode', 0.35)):
            a, b = runs[name]['ph'][pname]
            p.raw(f'<rect x="{sx(a):.1f}" y="{yb}" width="{sx(b) - sx(a):.1f}" height="8" rx="1.5" fill="{col[0]}" opacity="{op}"/>')
        p.text(x0 - 8, yb + 8, name, 13, TICK, 'end', 600)

    # 上：ANE 忙碌比例；下：读内存速率
    specs = [
        (78, 'busy', '忙碌比例 (%)' if j == 0 else None, None, (0, 100), [0, 20, 40, 60, 80, 100]),
        (290, 'read', '读内存 (GB/s)' if j == 0 else None, '时间 (s)', (0, 160), [0, 40, 80, 120, 160]),
    ]
    for y0, field, ylabel, xlabel, yr, yt in specs:
        ax = p.axes(x=x0, y=y0, w=PW, h=H_SUB, xr=(-2, xmax), yr=yr,
                    xticks=xticks, yticks=yt, xlabel=xlabel, ylabel=ylabel)
        if field == 'read':
            for name, col in (('M6', M6), ('M4', M4)):
                ax.hline(BOUND[name], color=col[0], dash='4 3', sw=1.1)
                ax.text(xmax - 0.5, BOUND[name], f'{BOUND[name]} GB/s', 13, col[0], 'end', 600, dy=-5)
        for name, col in (('M4', M4), ('M6', M6)):
            r = runs[name]
            sel = [k for k, tt in enumerate(r['t']) if -2 <= tt <= xmax]
            ax.line([r['t'][k] for k in sel], [r[field][k] for k in sel], color=col, marker=None, width=2.0)
            if field == 'read':
                for k in sel:
                    if r['clip'][k] > 0:
                        ax.point(r['t'][k], r['read'][k], color=col, marker='o', r=3.2)

# 底部白底居中图例
ly = 542
items = [
    (f'<svg xmlns="http://www.w3.org/2000/svg" width="24" height="14" viewBox="0 0 24 14"><line x1="0" y1="7" x2="24" y2="7" stroke="{M6[0]}" stroke-width="2.4"/></svg>', 'M6'),
    (f'<svg xmlns="http://www.w3.org/2000/svg" width="24" height="14" viewBox="0 0 24 14"><line x1="0" y1="7" x2="24" y2="7" stroke="{M4[0]}" stroke-width="2.4"/></svg>', 'M4'),
    (f'<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 14 14"><circle cx="7" cy="7" r="3.8" fill="#ffffff" stroke="{M6[0]}" stroke-width="1.8"/></svg>', '截顶下限'),
    (f'<svg xmlns="http://www.w3.org/2000/svg" width="20" height="12" viewBox="0 0 20 12"><rect x="0" y="2" width="20" height="8" rx="1.5" fill="{M6[0]}" opacity="0.92"/></svg>', '预填充'),
    (f'<svg xmlns="http://www.w3.org/2000/svg" width="20" height="12" viewBox="0 0 20 12"><rect x="0" y="2" width="20" height="8" rx="1.5" fill="{M6[0]}" opacity="0.35"/></svg>', '解码'),
]
parts = [f'<span style="display:flex;align-items:center;gap:6px">{ic}<span>{lb}</span></span>' for ic, lb in items]
p.raw(f'<foreignObject x="0" y="{ly - 14}" width="800" height="28"><div xmlns="http://www.w3.org/1999/xhtml" '
      f'style="display:flex;justify-content:center;gap:30px;align-items:center;height:28px;'
      f'font-family:Arial,\'Helvetica Neue\',\'PingFang SC\',sans-serif;font-size:13.5px;color:{K}">'
      + ''.join(parts) + '</div></foreignObject>')

print(p.save('fig14-1_busy_bandwidth'))
