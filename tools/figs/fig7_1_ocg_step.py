#!/usr/bin/env python3
# 图 7-1（第 7.3.2 节，表 7-4）：160 层 1×1 卷积链的调用耗时随通道数 C 的变化（统一样式见 plotfig.py）。
# 数据：data/05_compute/b2b_run.txt。
import os
import re
from plotfig import Plot, K, SUB, C_BLUE, C_GREEN, C_RED

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..')
pts = {}
for ln in open(os.path.join(ROOT, 'data', '05_compute', 'b2b_run.txt')):
    m = re.match(r'k1_c(\d+)_h1w128_L160\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)', ln)
    if m:
        pts[int(m.group(1))] = (float(m.group(2)), float(m.group(4)))
Cs = sorted(pts)


def cls(intr):
    return 3 if intr >= 2.9 else (2 if intr <= 2.05 else 1)


def draw_series(p, ax, cs, r=3.6):
    xy = [(ax.X(C), ax.Y(pts[C][0])) for C in cs]
    p.raw('<path d="M' + ' L'.join(f'{x:.1f} {y:.1f}' for x, y in xy) + '" fill="none" stroke="#666666" stroke-width="1.3"/>')
    for C, (x, y) in zip(cs, xy):
        k = cls(pts[C][1])
        if k == 3:
            ax._marker(x, y, 'O', C_BLUE[0], r)
        elif k == 2:
            ax._marker(x, y, 'o', C_GREEN[0], r)
        else:
            ax._marker(x, y, 'd', C_RED[0], r + 0.6)


p = Plot(800, 412)
# 两个独立浅灰圆角分区，底部图例在白底上（与图 9-1 完全一致）
p.panel(4, 8, 390, 360)
p.panel(406, 8, 390, 360)

axL = p.axes(x=80, y=50, w=298, h=256, xr=(160, 1056), yr=(0, 2700),
             xlabel='通道数 C', ylabel='调用耗时 (µs)',
             xticks=[256, 512, 768, 1024], yticks=[0, 500, 1000, 1500, 2000, 2500],
             title='(a) C = 192–1024', title_x=18)

zx0, zx1, zy0, zy1 = axL.X(180), axL.X(364), axL.Y(470), axL.Y(170)
p.raw(f'<rect x="{zx0:.1f}" y="{zy0:.1f}" width="{zx1 - zx0:.1f}" height="{zy1 - zy0:.1f}" '
      f'fill="none" stroke="#666666" stroke-width="1.1" stroke-dasharray="3 3"/>')
p.text(zx0 + 2, zy0 - 6, '(b)', 12.5, SUB, 'start', 600)
draw_series(p, axL, Cs, r=3.4)

axR = p.axes(x=482, y=50, w=298, h=256, xr=(182, 362), yr=(180, 455),
             xlabel='通道数 C', ylabel='调用耗时 (µs)',
             xticks=[192, 224, 256, 288, 320, 352], yticks=[200, 250, 300, 350, 400, 450],
             title='(b) C = 192–352', title_x=420)
axR.vline(264, color='#888888', dash='4 3', sw=1.1)
draw_series(p, axR, [C for C in Cs if C <= 352], r=4.2)

d = pts[272][0] - pts[256][0]
y256, y272 = axR.Y(pts[256][0]), axR.Y(pts[272][0])
xm = axR.X(272) + 12
p.raw(f'<line x1="{axR.X(256):.1f}" y1="{y256:.1f}" x2="{xm:.1f}" y2="{y256:.1f}" stroke="{C_RED[0]}" stroke-width="1.1" stroke-dasharray="2 2"/>')
p.raw(f'<line x1="{xm:.1f}" y1="{y256:.1f}" x2="{xm:.1f}" y2="{y272:.1f}" stroke="{C_RED[0]}" stroke-width="1.6"/>')
for yy in (y256, y272):
    p.raw(f'<line x1="{xm - 4:.1f}" y1="{yy:.1f}" x2="{xm + 4:.1f}" y2="{yy:.1f}" stroke="{C_RED[0]}" stroke-width="1.5"/>')
p.text(xm + 8, (y256 + y272) / 2 + 5, f'+{d:.1f} µs', 13.5, C_RED[0], 'start', 600)

ly = 392
items = [
    (f'<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 14 14"><circle cx="7" cy="7" r="4.5" fill="{C_BLUE[0]}"/></svg>', '≈3 次中断'),
    (f'<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 14 14"><circle cx="7" cy="7" r="4.5" fill="#ffffff" stroke="{C_GREEN[0]}" stroke-width="2"/></svg>', '≈2 次中断'),
    (f'<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 16 16"><path d="M8 2 L14 8 L8 14 L2 8 Z" fill="#ffffff" stroke="{C_RED[0]}" stroke-width="1.9"/></svg>', '混合状态'),
]
parts = [f'<span style="display:flex;align-items:center;gap:7px">{ic}<span>{lb}</span></span>' for ic, lb in items]
p.raw(f'<foreignObject x="0" y="{ly - 14}" width="800" height="28"><div xmlns="http://www.w3.org/1999/xhtml" '
      f'style="display:flex;justify-content:center;gap:56px;align-items:center;height:28px;'
      f'font-family:Arial,\'Helvetica Neue\',\'PingFang SC\',sans-serif;font-size:13.5px;color:{K}">'
      + ''.join(parts) + '</div></foreignObject>')

print(p.save('fig7-1_ocg_step'))
