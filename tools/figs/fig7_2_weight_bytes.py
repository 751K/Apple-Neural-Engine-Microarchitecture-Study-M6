#!/usr/bin/env python3
# 图 7-2（第 7.5 节）：读权重受限层的每层耗时与每层权重字节数（统一样式见 plotfig.py）。
# 数据：data/05_compute/wfmt/wfmt.txt、data/05_compute/sparse/sparse.txt。
import os
import re
from plotfig import Plot, K, SUB, C_BLUE, C_GREEN, C_RED

D = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'data', '05_compute')

wf = {}
for line in open(os.path.join(D, 'wfmt', 'wfmt.txt')):
    f = line.split()
    if len(f) == 6 and re.match(r'(m2048|k1x9)_\w+$', f[0]) and f[1] != 'nan':
        wf[f[0]] = (float(f[1]), float(f[2]))

sp = {'m6_v1': {}, 'm4_v1': {}}
sec = None
for line in open(os.path.join(D, 'sparse', 'sparse.txt')):
    m = re.match(r'######## (\S+)$', line.strip())
    if m:
        sec = m.group(1)
        continue
    f = line.split()
    if sec in sp and len(f) >= 5 and f[0].startswith('m2048_') and f[1] == '16→32':
        sp[sec][f[0].split('@')[0].replace('m2048_', '')] = (float(f[2]), float(f[3]))

p = Plot(800, 436)
# 两个独立浅灰圆角分区 + 白底绘图区 + 底部白底图例（与图 9-1 完全一致）
p.panel(4, 8, 514, 384)
p.panel(530, 8, 266, 384)

# ---------- (a) m2048：各种权重格式（双对数坐标） ----------
ax = p.axes(x=80, y=50, w=422, h=280, xr=(0.78, 12.0), yr=(5, 210),
            xlog=True, ylog=True, xgrid=True, ygrid=True, yminor=True,
            xlabel='每层权重 (MB)', ylabel='每层耗时 (µs)',
            xticks=[1, 2, 4, 8], yticks=[5, 10, 20, 50, 100, 200],
            title='(a) 1×1 卷积（2048 通道）', title_x=18)

for bw, col in ((150, C_BLUE), (67, C_GREEN)):
    ax.line([0.78, 11.5], [0.78 / bw * 1000, 11.5 / bw * 1000], color=col, marker=None, dash='5 4', width=1.5)

ax.text(11.6, 11.6 / 67 * 1000, '67 GB/s', 12.5, C_GREEN[0], 'end', 600, dx=-2, dy=40)
ax.text(11.6, 11.6 / 150 * 1000, '150 GB/s', 12.5, C_BLUE[0], 'end', 600, dx=-2, dy=40)

for k, lab, dx, dy, anc in (
    ('fp16', 'FP16', 0, 19, 'middle'),
    ('w8', 'W8', -4, -10, 'middle'),
    ('p6', '6b', -2, -10, 'middle'),
    ('p4', '4b', -2, -10, 'middle'),
    ('p3', '3b', 9, 5, 'start'),
    ('p2', '2b', 0, -10, 'middle'),
):
    mb, us = wf['m2048_' + k]
    ax.point(mb, us, color=C_BLUE, marker='o' if k in ('p2', 'p3') else 'O', r=4.6)
    ax.text(mb, us, lab, 12, SUB, anc, 400, dx=dx, dy=dy)

for k, lab, dx, dy, anc in (
    ('s50', '50%', 7, 15, 'start'),
    ('s75', '75%', 7, 15, 'start'),
    ('s90', '90%', 7, 15, 'start'),
    ('s50p4', '50%+4b', -8, 2, 'end'),
):
    mb, us = sp['m6_v1'][k]
    ax.point(mb, us, color=C_BLUE, marker='S', r=4.4)
    ax.text(mb, us, lab, 12, SUB, anc, 400, dx=dx, dy=dy)

for k, lab, dx, dy, anc in (
    ('fp16', 'FP16', 0, -10, 'middle'),
    ('s50', '50%', 0, -10, 'middle'),
    ('s75', '75%', 0, -10, 'middle'),
    ('s90', '90%', -8, 12, 'end'),
    ('s50p4', '50%+4b', -2, -12, 'end'),
):
    mb, us = sp['m4_v1'][k]
    ax.point(mb, us, color=C_GREEN, marker='O' if k == 'fp16' else 'S', r=4.5)
    ax.text(mb, us, lab, 12, SUB, anc, 400, dx=dx, dy=dy)

# ---------- (b) 1×9 改写核 ----------
bx = p.axes(x=582, y=50, w=196, h=280, xr=(0, 3.0), yr=(0, 25),
            xlabel='每层权重 (MB)', xticks=[0, 1, 2, 3], yticks=[0, 5, 10, 15, 20, 25],
            title='(b) 1×9 改写核（256 通道）', title_x=544)
bx.line([0, 3.0], [0, 3.0 / 150 * 1000], color=C_BLUE, marker=None, dash='5 4', width=1.5)
(a0, t0), (a1, t1) = wf['k1x9_fp16'], wf['k1x9_w8']
bx.arrow((a0, t0), (a1, t1), color=C_RED, sw=1.5, pad0=9, pad1=10)
bx.point(a0, t0, color=C_RED, marker='d', r=5.2)
bx.point(a1, t1, color=C_RED, marker='d', r=5.2)
bx.text(a0, t0, 'FP16', 12.5, SUB, 'start', 600, dx=2, dy=20)
bx.text(a1, t1, f'W8 ({t1:.1f} µs)', 12.5, C_RED[0], 'middle', 600, dy=-14)

pe = a1 / 150 * 1000
p.raw(f'<line x1="{bx.X(a1):.1f}" y1="{bx.Y(pe) - 5:.1f}" x2="{bx.X(a1):.1f}" y2="{bx.Y(t1) + 8:.1f}" '
      f'stroke="#777777" stroke-width="1.1" stroke-dasharray="3 3"/>')
bx.point(a1, pe, color=C_BLUE, marker='o', r=4.0)
bx.text(a1, pe, f'{pe:.1f} µs', 12.5, C_BLUE[0], 'start', 600, dx=8, dy=5)

ly = 416
items = [
    (f'<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 14 14"><circle cx="7" cy="7" r="4.5" fill="{C_BLUE[0]}"/></svg>', 'M6 量化/调色板'),
    (f'<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 14 14"><circle cx="7" cy="7" r="4.5" fill="#ffffff" stroke="{C_BLUE[0]}" stroke-width="2"/></svg>', '双份权重'),
    (f'<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 14 14"><rect x="2.5" y="2.5" width="9" height="9" fill="{C_BLUE[0]}"/></svg>', 'M6 剪枝'),
    (f'<svg xmlns="http://www.w3.org/2000/svg" width="26" height="14" viewBox="0 0 26 14"><circle cx="6.5" cy="7" r="4.5" fill="{C_GREEN[0]}"/><rect x="15" y="2.5" width="9" height="9" fill="{C_GREEN[0]}"/></svg>', 'M4'),
    (f'<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 16 16"><path d="M8 2 L14 8 L8 14 L2 8 Z" fill="#ffffff" stroke="{C_RED[0]}" stroke-width="1.9"/></svg>', '改写核'),
]
parts = [f'<span style="display:flex;align-items:center;gap:6px">{ic}<span>{lb}</span></span>' for ic, lb in items]
p.raw(f'<foreignObject x="0" y="{ly - 14}" width="800" height="28"><div xmlns="http://www.w3.org/1999/xhtml" '
      f'style="display:flex;justify-content:center;gap:28px;align-items:center;height:28px;'
      f'font-family:Arial,\'Helvetica Neue\',\'PingFang SC\',sans-serif;font-size:13px;color:{K}">'
      + ''.join(parts) + '</div></foreignObject>')

print(p.save('fig7-2_weight_bytes'))
