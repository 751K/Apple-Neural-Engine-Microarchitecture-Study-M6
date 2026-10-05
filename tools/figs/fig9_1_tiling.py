#!/usr/bin/env python3
# 第 9.2.2 节示意图：中间张量超过 2 MiB 时的切块与执行顺序；右侧附表 9-2 的每千像素耗时。
import os
o = []
a = o.append
W, H = 1020, 560
a(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" font-family="PingFang SC, Helvetica Neue, Arial, sans-serif">')
a('<style>text{fill:#1d1d1f} .h{font-size:18px;font-weight:600} .h2{font-size:16px;font-weight:600} .b{font-size:14.5px;fill:#3a3a3c}'
  ' .c{font-size:13px;fill:#6e6e73} .s{font-size:12px;fill:#3a3a3c} .m{font-size:13px;font-family:Menlo,SF Mono,monospace;fill:#3a3a3c} .mid{text-anchor:middle} .end{text-anchor:end}</style>')
a('<defs><marker id="ar" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="#48484a"/></marker>'
  '<marker id="ao" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="#7e6148"/></marker></defs>')


def t(x, y, s, c='b', anc=''):
    a(f'<text class="{c}{" " + anc if anc else ""}" x="{x}" y="{y}">{s}</text>')


def rect(x, y, w, h, f, s, rx=4, sw=1.3, dash=False):
    a(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{f}" stroke="{s}" stroke-width="{sw}"' + (' stroke-dasharray="4 3"' if dash else '') + '/>')


# ---- ① 切块 ----
t(40, 32, '① 16 MB 的中间张量被切成 9 块，每块都小于 2 MiB', 'h')
x0, y0, bw = 60, 56, 88
for i in range(9):
    rect(x0 + i * bw, y0, bw - 4, 44, '#e3f4f0', '#00a087')
    t(x0 + i * bw + (bw - 4) / 2, y0 + 28, f'块 {i + 1}', 's', 'mid')
a(f'<path d="M{x0} {y0 + 52} v6 H{x0 + 9 * bw - 4} v-6" stroke="#48484a" stroke-width="1.2" fill="none"/>')
t(x0 + 9 * bw / 2, y0 + 78, '宽 32768 列，256 通道，16 MB；每块约 1.78 MB，块宽为 128 列的整数倍', 'c', 'mid')
t(x0, y0 + 112, '块数 = ⌊中间张量大小 ÷ 2 MiB⌋ + 1', 'm')
t(x0 + 330, y0 + 112, '2 MB → 2 块，4 MB → 3 块，16 MB → 9 块', 'c')

# ---- ② 执行顺序 ----
t(40, 222, '② 每一块连续执行完整条链，再处理下一块；中间结果始终留在 L2', 'h')
gx, gy, cw, rh = 150, 278, 120, 42
layers = ['第 1 层', '第 2 层', '⋮', '第 n 层']
cols = ['块 1', '块 2', '块 3', '⋯', '块 9']
for j, cname in enumerate(cols):
    t(gx + j * cw + 50, gy - 12, cname, 's', 'mid')
for i, lname in enumerate(layers):
    t(gx - 16, gy + i * rh + 26, lname, 's', 'end')
    for j in range(len(cols)):
        if lname == '⋮' or cols[j] == '⋯':
            t(gx + j * cw + 50, gy + i * rh + 26, '⋮' if lname == '⋮' else '⋯', 'c', 'mid')
            continue
        rect(gx + j * cw, gy + i * rh + 4, 100, 30, '#e7eaf3', '#3c5488')
# 执行路径：块内自上而下，再跳到下一块的顶部
for j in [0, 1, 2]:
    cx = gx + j * cw + 50
    a(f'<path d="M{cx} {gy + 34} V{gy + 3 * rh + 2}" stroke="#7e6148" stroke-width="2" fill="none" marker-end="url(#ao)" opacity="0.9"/>')
    if j < 2:
        gxg = gx + j * cw + 110
        a(f'<path d="M{cx} {gy + 3 * rh + 34} V{gy + 3 * rh + 46} H{gxg} V{gy - 2} H{cx + cw} V{gy + 2}" stroke="#7e6148" stroke-width="1.5" stroke-dasharray="4 3" fill="none" marker-end="url(#ao)"/>')
# DRAM 读写
t(gx + 2.5 * cw, gy + 4 * rh + 64, '每块只在第 1 层读入、在第 n 层写出 DRAM；层与层之间不经过 DRAM', 'c', 'mid')
# L2 示意
lx = 830
rect(lx, gy - 6, 150, 170, '#e3f4f0', '#00a087', rx=8)
t(lx + 75, gy + 20, 'L2', 'h2', 'mid')
t(lx + 75, gy + 42, '编译器按 2 MiB 使用', 'c', 'mid')
rect(lx + 20, gy + 60, 110, 80, '#e7eaf3', '#3c5488', rx=4)
t(lx + 75, gy + 96, '当前块的', 's', 'mid'); t(lx + 75, gy + 114, '中间结果', 's', 'mid')

a('</svg>')
open(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'figs', 'zh', 'light', 'fig9-1_tiling.svg'), 'w').write('\n'.join(o))
