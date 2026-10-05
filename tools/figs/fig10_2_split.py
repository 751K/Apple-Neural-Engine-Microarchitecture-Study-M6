#!/usr/bin/env python3
# 第 10.5 节示意图：双 ANE 程序沿用单 ANE 的切块网格，按整块把块列表分给两个 ANE。
# 块宽与分配取自表 10-3、表 10-4（256 通道 1×1 卷积链）；块在张量中的先后位置为示意。
import os
o = []
a = o.append
W, H = 1000, 470
a(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" font-family="PingFang SC, Helvetica Neue, Arial, sans-serif">')
a('<style>text{fill:#1d1d1f} .h{font-size:18px;font-weight:600} .h2{font-size:15.5px;font-weight:600} .b{font-size:14.5px;fill:#3a3a3c}'
  ' .c{font-size:13px;fill:#6e6e73} .s{font-size:12px;fill:#3a3a3c} .mid{text-anchor:middle} .end{text-anchor:end}</style>')


def t(x, y, s, c='b', anc=''):
    a(f'<text class="{c}{" " + anc if anc else ""}" x="{x}" y="{y}">{s}</text>')


def rect(x, y, w, h, f, s, rx=3):
    a(f'<rect x="{x:.1f}" y="{y}" width="{w:.1f}" height="{h}" rx="{rx}" fill="{f}" stroke="{s}" stroke-width="1.3"/>')


A0 = ('#e7eaf3', '#3c5488'); A1 = ('#e3f4f0', '#00a087')
rows = [('宽 8192', '1536 + 4 × 1664，5 块', [1664, 1664], [1536, 1664, 1664], '1.41–1.47'),
        ('宽 12288', '2 × 1664 + 5 × 1792，7 块', [1792, 1792, 1792], [1664, 1664, 1792, 1792], '1.28–1.29'),
        ('宽 14336', '8 × 1792，8 块', [1792] * 4, [1792] * 4, '—（两边 TD 数相同）')]
SC = 0.046
X0 = 240
t(40, 32, '双 ANE 程序沿用单 ANE 的切块网格，按整块分配', 'h')
t(40, 54, '块数为奇数时，多出的一块总是分给 ANE1', 'c')
t(X0, 80, '每层的切块与分配（256 通道 1×1 卷积链）', 'c')
TX = 950
y = 100
for name, desc, b0, b1, meas in rows:
    t(40, y + 26, name, 'h2'); t(40, y + 46, desc, 'c')
    x = X0
    for w in b0:
        rect(x, y + 8, w * SC - 3, 34, *A0); t(x + (w * SC - 3) / 2, y + 30, str(w), 's', 'mid'); x += w * SC
    x += 10
    for w in b1:
        rect(x, y + 8, w * SC - 3, 34, *A1); t(x + (w * SC - 3) / 2, y + 30, str(w), 's', 'mid'); x += w * SC
    s0, s1 = sum(b0), sum(b1)
    tot = s0 + s1
    y += 90
a(f'<rect x="{X0}" y="{y + 14}" width="14" height="14" rx="2" fill="{A0[0]}" stroke="{A0[1]}"/>')
t(X0 + 22, y + 26, 'ANE0', 's')
a(f'<rect x="{X0 + 80}" y="{y + 14}" width="14" height="14" rx="2" fill="{A1[0]}" stroke="{A1[1]}"/>')
t(X0 + 102, y + 26, 'ANE1', 's')
t(X0 + 160, y + 26, '方块中的数字为块宽（列）；块在张量中的先后位置为示意', 'c')
t(40, y + 62, '整条链的耗时由分到较多列的 ANE1 决定（缺陷 B8）。', 'c')
a('</svg>')
open(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'figs', 'fig10-2_split.svg'), 'w').write('\n'.join(o))
