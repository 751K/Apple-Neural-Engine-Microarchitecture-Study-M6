#!/usr/bin/env python3
# 图 7-2（第 7.5 节）：读权重受限层的每层耗时与每层权重字节数。
#   形状为 1×1 卷积，2048 通道，32 像素，各层权重不同（m2048）；横轴为编译产物中每层的权重段大小（压缩后），
#   纵轴为每层耗时（16 与 32 层的斜率）。直线为按读权重上限（M6 约 150 GB/s，M4 约 67 GB/s）预测的耗时。
#   M6：量化与调色板来自 wfmt（kdebug 任务时间，表 7-9），剪枝来自 sparse 第一轮（kdebug 提交 → 任务结束）；
#   M4：剪枝来自 sparse 第一轮（Core ML 调用耗时）。2、3 位调色板被拆到两个 ANE，两个引擎各存一份完整权重，
#   横轴取单份大小（空心点）。另以 1×9 改写核（256 通道，4×32）作对照：W8 使字节数减半而耗时不变。
# 数据：data/05_compute/wfmt/wfmt.txt、data/05_compute/sparse/sparse.txt。
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from figplot import Chart, COLORS, FG2  # noqa: E402

D = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'data', '05_compute')
M6, M4, RW = COLORS[0], COLORS[1], COLORS[4]

wf = {}
for line in open(os.path.join(D, 'wfmt', 'wfmt.txt')):
    f = line.split()
    if len(f) == 6 and re.match(r'(m2048|k1x9)_\w+$', f[0]) and f[1] != 'nan':
        wf[f[0]] = (float(f[1]), float(f[2]))           # (每层 MB, 每层 µs)

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

c = Chart(1080, 600)
# ---------- (a) m2048：各种权重格式（双对数坐标） ----------
ax = c.axes(x=100, y=60, w=560, h=420, xr=(0.8, 11), yr=(5, 200), xlog=True, ylog=True,
            xlabel='每层权重（MB，编译产物中压缩后的大小，对数坐标）', ylabel='每层耗时（µs，对数坐标）',
            xticks=[1, 2, 4, 8], yticks=[5, 10, 20, 50, 100, 200], title='(a) 读权重受限的 1×1 卷积（2048 通道）')
for v in (1, 2, 4, 8):
    c.a(f'<line x1="{ax.X(v):.1f}" y1="60" x2="{ax.X(v):.1f}" y2="480" stroke="#e5e5ea" stroke-width="1"/>')
for name, bw, col in (('M6', 150, M6), ('M4', 67, M4)):
    x0, x1 = 0.8, 11
    ax.line([x0, x1], [x0 / bw * 1000, x1 / bw * 1000], color=col, marker=False, dash=True, width=1.4)
c.t(ax.X(9.5), ax.Y(9.5 / 67 * 1000) + 20, '67 GB/s', 's', 'start', M4[0])
c.t(ax.X(9.5), ax.Y(9.5 / 150 * 1000) + 20, '150 GB/s', 's', 'start', M6[0])


def dot(a, mb, us, col, shape='o', hollow=False, lab=None, dy=0, anchor='middle'):
    x, y = a.X(mb), a.Y(us)
    fill = '#ffffff' if hollow else col[0]
    if shape == 'o':
        c.a(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="5.5" fill="{fill}" stroke="{col[0]}" stroke-width="1.8"/>')
    elif shape == 's':
        c.a(f'<rect x="{x - 5:.1f}" y="{y - 5:.1f}" width="10" height="10" fill="{fill}" stroke="{col[0]}" stroke-width="1.8"/>')
    else:
        c.a(f'<path d="M{x:.1f} {y - 7:.1f} L{x + 7:.1f} {y:.1f} L{x:.1f} {y + 7:.1f} L{x - 7:.1f} {y:.1f} Z" fill="#ffffff" stroke="{col[0]}" stroke-width="2"/>')
    if lab:
        c.t(x + (0 if anchor == 'middle' else (10 if anchor == 'start' else -10)), y + dy, lab, 'c', anchor)


# M6：量化与调色板（圆，标签在下），剪枝（方，标签在上）
for k, lab, dy, anc in (('fp16', 'FP16', 24, 'middle'), ('w8', 'W8', -12, 'middle'), ('p6', '6 位', -12, 'middle'),
                        ('p4', '4 位', -12, 'middle'), ('p3', '3 位', -6, 'start'), ('p2', '2 位', -12, 'middle')):
    mb, us = wf['m2048_' + k]
    dot(ax, mb, us, M6, 'o', hollow=k in ('p2', 'p3'), lab=lab, dy=dy, anchor=anc)
for k, lab, dy, anc in (('s50', '50%', 22, 'start'), ('s75', '75%', 22, 'start'), ('s90', '90%', 22, 'start'),
                        ('s50p4', '50%+4 位', 5, 'end')):
    mb, us = sp['m6_v1'][k]
    dot(ax, mb, us, M6, 's', lab=lab, dy=dy, anchor=anc)
# M4：FP16（圆）与剪枝（方）
for k, lab in (('fp16', 'FP16'), ('s50', '50%'), ('s75', '75%'), ('s90', '90%'), ('s50p4', '50%+4 位')):
    mb, us = sp['m4_v1'][k]
    dot(ax, mb, us, M4, 'o' if k == 'fp16' else 's', lab=lab, dy=-12, anchor='end' if k == 's50p4' else 'middle')

# ---------- (b) 1×9 改写核：W8 减少字节，但耗时不变 ----------
bx = c.axes(x=790, y=60, w=240, h=420, xr=(0, 3), yr=(0, 25), xlabel='每层权重（MB）', xticks=[0, 1, 2, 3],
            yticks=[0, 5, 10, 15, 20, 25], title='(b) 1×9 改写核（256 通道）')
bx.line([0, 3], [0, 3 / 150 * 1000], color=M6, marker=False, dash=True, width=1.4)
(a0, t0), (a1, t1) = wf['k1x9_fp16'], wf['k1x9_w8']
dot(bx, a0, t0, RW, 'd', lab='FP16', dy=26, anchor='start')
dot(bx, a1, t1, RW, 'd', lab=f'W8：实测 {t1:.1f} µs', dy=-14)
c.a(f'<path d="M{bx.X(a0) - 12:.1f} {bx.Y(t0):.1f} L{bx.X(a1) + 12:.1f} {bx.Y(t1):.1f}" stroke="{FG2}" stroke-width="1.3" fill="none" marker-end="url(#a)"/>')
pe = a1 / 150 * 1000
c.a(f'<circle cx="{bx.X(a1):.1f}" cy="{bx.Y(pe):.1f}" r="4" fill="#ffffff" stroke="{M6[0]}" stroke-width="1.6"/>')
c.a(f'<line x1="{bx.X(a1):.1f}" y1="{bx.Y(pe) - 6:.1f}" x2="{bx.X(a1):.1f}" y2="{bx.Y(t1) + 9:.1f}" stroke="{FG2}" stroke-width="1" stroke-dasharray="3 3"/>')
c.t(bx.X(a1) + 10, bx.Y(pe) + 18, f'按 150 GB/s 应为 {pe:.1f} µs', 'c', 'start')

# 图例
ly = 560
items = [('o', M6, False, 'M6，量化与调色板'), ('o', M6, True, 'M6，两个 ANE 各存一份'), ('s', M6, False, 'M6，剪枝'),
         ('o', M4, False, 'M4，FP16'), ('s', M4, False, 'M4，剪枝'), ('d', RW, True, '改写核')]
for (shape, col, hol, lab), lx in zip(items, (100, 300, 505, 620, 740, 860)):
    x, y = lx + 8, ly - 4
    fill = '#ffffff' if hol else col[0]
    if shape == 'o':
        c.a(f'<circle cx="{x}" cy="{y}" r="5.5" fill="{fill}" stroke="{col[0]}" stroke-width="1.8"/>')
    elif shape == 's':
        c.a(f'<rect x="{x - 5}" y="{y - 5}" width="10" height="10" fill="{fill}" stroke="{col[0]}" stroke-width="1.8"/>')
    else:
        c.a(f'<path d="M{x} {y - 7} L{x + 7} {y} L{x} {y + 7} L{x - 7} {y} Z" fill="#ffffff" stroke="{col[0]}" stroke-width="2"/>')
    c.t(lx + 22, ly + 1, lab, 's')
c.save('fig7-2_weight_bytes')
