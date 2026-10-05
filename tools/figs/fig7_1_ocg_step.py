#!/usr/bin/env python3
# 图 7-1（第 7.3.2 节，表 7-4）：160 层 1×1 卷积链（空间 1×128，单 ANE，各层共享权重）的调用耗时随通道数 C 的变化。
# 数据：data/05_compute/b2b_run.txt，每行“模型名 调用耗时 第二列 每次调用中断数 第四列”；只取 L160 的行，
#       调用耗时取第 1 个数值列（与表 7-4 相同），中断数取第 3 个数值列。
# 处理：按每次调用的中断数把测量点分为三类——约 3 次（≥ 2.9）、约 2 次（≤ 2.05）、介于两者之间（两种唤醒状态混合）。
#       左图为 C = 192–1024 全范围，右图放大 C = 192–352（表 7-4 的范围），标出 256 → 272 的增量。
import os
import re
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from figplot import Chart, COLORS, FG3, AXIS

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..')
pts = {}
for ln in open(os.path.join(ROOT, 'data', '05_compute', 'b2b_run.txt')):
    m = re.match(r'k1_c(\d+)_h1w128_L160\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)', ln)
    if m:
        pts[int(m.group(1))] = (float(m.group(2)), float(m.group(4)))
Cs = sorted(pts)


def cls(intr):
    return 3 if intr >= 2.9 else (2 if intr <= 2.05 else 1)


P3, P2, PM = COLORS[0][0], COLORS[1][0], COLORS[2][0]


def marker(c, x, y, k, r=4.6):
    if k == 3:
        c.a(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r}" fill="{P3}" stroke="{P3}" stroke-width="1.6"/>')
    elif k == 2:
        c.a(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r}" fill="#ffffff" stroke="{P2}" stroke-width="1.8"/>')
    else:
        d = r + 1.4
        c.a(f'<path d="M{x:.1f} {y - d:.1f} L{x + d:.1f} {y:.1f} L{x:.1f} {y + d:.1f} L{x - d:.1f} {y:.1f} Z" fill="#ffffff" stroke="{PM}" stroke-width="1.8"/>')


def series(c, ax, cs, r=4.6):
    xy = [(ax.X(C), ax.Y(pts[C][0])) for C in cs]
    c.a('<path d="M' + ' L'.join(f'{x:.1f} {y:.1f}' for x, y in xy) + f'" fill="none" stroke="{AXIS}" stroke-width="1.2"/>')
    for C, (x, y) in zip(cs, xy):
        marker(c, x, y, cls(pts[C][1]), r)


W, H = 1160, 560
c = Chart(W, H)
# 左：全范围
axL = c.axes(x=86, y=40, w=520, h=400, xr=(160, 1056), yr=(0, 2700), xlabel='通道数 C', ylabel='调用耗时（µs）',
             xticks=[192, 256, 384, 512, 640, 768, 896, 1024], yticks=[0, 500, 1000, 1500, 2000, 2500],
             title='（a）C = 192–1024')
# 放大区域示意
zx0, zx1, zy0, zy1 = axL.X(180), axL.X(364), axL.Y(470), axL.Y(170)
c.a(f'<rect x="{zx0:.1f}" y="{zy0:.1f}" width="{zx1 - zx0:.1f}" height="{zy1 - zy0:.1f}" fill="none" stroke="{FG3}" stroke-width="1" stroke-dasharray="3 3"/>')
c.t(zx0 + 2, zy0 - 6, '见（b）', 'c')
series(c, axL, Cs, r=3.6)
for C0, C1 in [(512, 528), (768, 784)]:
    d = pts[C1][0] - pts[C0][0]
    axL.text(C1, pts[C1][0], f'{C0} → {C1}：+{d:.1f} µs', 'c', 'end', dx=-12, dy=-14)
c.t(axL.X(176), axL.Y(2560), '◇ 处 L160 模型的唤醒状态发生切换，', 'c')
c.t(axL.X(176), axL.Y(2560) + 18, '　 其增量无法确认为真实的台阶', 'c')
axL.text(960, pts[960][0], 'C = 960', 'c', 'start', dx=12, dy=14)

# 右：放大 192–400
axR = c.axes(x=700, y=40, w=430, h=400, xr=(184, 360), yr=(180, 460), xlabel='通道数 C', ylabel='调用耗时（µs）',
             xticks=[192, 224, 256, 288, 320, 352], yticks=[200, 250, 300, 350, 400, 450],
             title='（b）C = 192–352（表 7-4 的范围）')
axR.vline(264, '每轮至多 256 个输出通道（16 NE × 16）', ty=axR.y + 16)
series(c, axR, [C for C in Cs if C <= 352])
d = pts[272][0] - pts[256][0]
xm = axR.X(272) + 8
c.a(f'<line x1="{axR.X(256):.1f}" y1="{axR.Y(pts[256][0]):.1f}" x2="{xm:.1f}" y2="{axR.Y(pts[256][0]):.1f}" stroke="{P3}" stroke-width="1" stroke-dasharray="2 2"/>')
c.a(f'<line x1="{xm:.1f}" y1="{axR.Y(pts[256][0]):.1f}" x2="{xm:.1f}" y2="{axR.Y(pts[272][0]):.1f}" stroke="{P3}" stroke-width="1.4"/>')
c.t(xm + 6, (axR.Y(pts[256][0]) + axR.Y(pts[272][0])) / 2 + 5, f'256 → 272：+{d:.1f} µs', 's', col=P3)
for C, dx, dy, an in ((192, 0, -12, 'middle'), (256, -10, -12, 'end'), (272, -8, -6, 'end'), (352, -8, -10, 'end')):
    axR.text(C, pts[C][0], f'{pts[C][0]:.1f}', 'c', an, dx=dx, dy=dy)

# 图例
ly = 518
c.a(f'<circle cx="{100}" cy="{ly - 4}" r="4.6" fill="{P3}" stroke="{P3}"/>')
c.t(112, ly + 1, '每次调用约 3 次中断（≥ 2.9）', 's')
c.a(f'<circle cx="{360}" cy="{ly - 4}" r="4.6" fill="#ffffff" stroke="{P2}" stroke-width="1.8"/>')
c.t(372, ly + 1, '约 2 次中断（≤ 2.05）', 's')
c.a(f'<path d="M580 {ly - 10} L586 {ly - 4} L580 {ly + 2} L574 {ly - 4} Z" fill="#ffffff" stroke="{PM}" stroke-width="1.8"/>')
c.t(594, ly + 1, '介于两者之间（两种唤醒状态混合）', 's')
c.t(860, ly + 1, '160 层，空间 1×128，单 ANE', 'c')
c.save('fig7-1_ocg_step')
