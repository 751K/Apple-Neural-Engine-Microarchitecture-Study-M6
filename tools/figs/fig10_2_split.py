#!/usr/bin/env python3
# 图 10-2：双 ANE 程序的切块与分配（正式科研论文对称对比样式，对齐 archfig.py 配色）。
# 图契约：
#   核心结论：双 ANE 沿用单 ANE 的切块网格、按整块分给两个引擎；块数为奇数（5、7 块）时，
#             多出的一块总是分给 ANE1（占 59%、56%），偶数（8 块）时才完全均衡（50% / 50%）。
#   图原型：以 ANE0 / ANE1 分界竖虚线为中心对称展开（左 ANE0、右 ANE1），方块宽与列数严格成正比，
#           右侧直接给出 ANE0 / ANE1 的列数占比。
#   能不能更少：去掉重复标题、整句说明与冗余底部图例，将色块标识直接整合进顶部的 ANE0 / ANE1 栏头。
# 数据：表 10-3、表 10-4（256 通道 1×1 卷积链）。
from archfig import Fig, K, SK, GREEN, BLUE, WT

SUB = '#555555'
SEP = '#e2e2e6'

f = Fig(800, 232)
T, B, R = f.text, f.box, f.rect

rows = [
    ('宽 8192', '5 块', [1664, 1664], [1536, 1664, 1664], True),
    ('宽 12288', '7 块', [1792, 1792, 1792], [1664, 1664, 1792, 1792], True),
    ('宽 14336', '8 块', [1792, 1792, 1792, 1792], [1792, 1792, 1792, 1792], False),
]

XC = 410                           # ANE0 / ANE1 对称中轴
GAP_C = 10                         # 中轴两侧留白
TILE_G = 4                         # 块间缝隙
SC = 268.0 / 7168.0                # 列数 → 像素（4 × 1792 = 7168 列严格占 268 px）
BH = 34

# 顶部栏头（整合色块图例，免去冗余底部图例）
R(XC - 80, 14, 16, 14, BLUE)
T(XC - 14, 26, 'ANE0', 15, K, 'end', 600)
T(XC + 14, 26, 'ANE1', 15, K, 'start', 600)
R(XC + 64, 14, 16, 14, GREEN)
T(784, 26, 'ANE0 / ANE1', 12.5, SUB, 'end', 600)

# 顶部分隔细线与中轴竖虚线
f.raw(f'<line x1="12" y1="38" x2="788" y2="38" stroke="#c8c8cc" stroke-width="1"/>')
f.raw(f'<line x1="{XC}" y1="38" x2="{XC}" y2="218" stroke="#666666" stroke-width="1.2" stroke-dasharray="4 3"/>')

for idx, (wlab, tlab, b0, b1, imb) in enumerate(rows):
    y = 52 + idx * 56
    # 左侧宽度与块数
    T(102, y + 15, wlab, 14.5, K, 'end', 600)
    T(102, y + 32, tlab, 12.5, SUB, 'end', 400)

    # ANE0：从中轴向左排布
    x = XC - GAP_C
    for w in reversed(b0):
        pw = w * SC
        x -= pw
        B(x, y, pw, BH, str(w), BLUE, 13)
        x -= TILE_G

    # ANE1：从中轴向右排布
    x = XC + GAP_C
    for w in b1:
        pw = w * SC
        B(x, y, pw, BH, str(w), GREEN, 13)
        x += pw + TILE_G

    # 右侧列数占比（奇数块不均衡用深红突出）
    s0, s1 = sum(b0), sum(b1)
    p0, p1 = round(100 * s0 / (s0 + s1)), round(100 * s1 / (s0 + s1))
    T(784, y + 22, f'{p0}% / {p1}%', 13.5, WT if imb else SUB, 'end', 600)

    if idx < 2:
        f.raw(f'<line x1="12" y1="{y + 45}" x2="788" y2="{y + 45}" stroke="{SEP}" stroke-width="0.8"/>')

print(f.save('fig10-2_split'))
