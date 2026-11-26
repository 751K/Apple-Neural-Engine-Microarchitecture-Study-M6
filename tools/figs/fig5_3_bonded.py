#!/usr/bin/env python3
# 图 5-3：双 ANE 程序的切分、同步与切分决策（样式见 archfig.py）。
# 图契约：
#   核心结论：双 ANE 有按行切分（权重各读一份）和按输出通道切分（权重各读一半）两种方式；
#             存在空间依赖的层经共享暂存区交换边界行并以同步记录等待；
#             编译器以（切分后延迟 + 合并）× 0.5 与单 ANE 比较，未计入带宽争用。
#   图原型：2×2 分区——(a) 按行切分、(b) 按输出通道切分、(c) 跨引擎同步、(d) 切分判据。
#   能不能更少：具体形状、TD 字段偏移、同步记录十六进制码与缺陷说明写进图注和正文。
from archfig import Fig, K, SK, SW, GREEN, BLUE, WHITE, ACT, WT

BLUE2 = '#cddbf0'
BLUE3 = '#9fb9e0'
MERGE = '#e7d9b8'
f = Fig(800, 560)
T, B, L, R = f.text, f.box, f.line, f.rect

# 斜线图案（按行切分时的重叠行）
f.raw('<defs><pattern id="hatch" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">'
      f'<line x1="0" y1="0" x2="0" y2="6" stroke="{ACT}" stroke-width="1.6"/></pattern></defs>')


def dot(x, y, col):
    f.raw(f'<circle cx="{x}" cy="{y}" r="3" fill="{col}"/>')


def diamond(x, y, r=7, col=K):
    f.raw(f'<path d="M{x} {y - r} L{x + r} {y} L{x} {y + r} L{x - r} {y} Z" fill="{col}"/>')


# ======================== (a) 按行切分 ========================
f.panel(4, 8, 390, 240)
T(18, 32, '(a) 按行切分', 16, K, 'start', 600)

# 左侧：激活张量分为上下两半，中间带斜线重叠带
R(18, 52, 98, 78, BLUE2)
R(18, 130, 98, 78, BLUE)
f.raw('<rect x="18" y="121" width="98" height="18" fill="url(#hatch)" opacity="0.55"/>')
f.raw(f'<line x1="18" y1="130" x2="116" y2="130" stroke="{SK}" stroke-width="1" stroke-dasharray="4 3"/>')
T(67, 94, '行 0–31', 15, K, 'middle', 600)
T(67, 174, '行 32–63', 15, K, 'middle', 600)
T(67, 232, '激活', 15, K, 'middle', 600)

# 中间：ANE0 / ANE1
B(156, 66, 88, 50, 'ANE0', GREEN, 16)
B(156, 144, 88, 50, 'ANE1', GREEN, 16)
L([(116, 91), (155, 91)], ACT, 2.4)
L([(116, 169), (155, 169)], ACT, 2.4)

# 右侧：完整一份权重 → 两个 ANE 各读一份
R(286, 90, 94, 80, BLUE)
T(333, 124, '权重', 16, K, 'middle', 600)
T(333, 148, '完整一份', 14, '#3a3a3c', 'middle', 400)
L([(286, 130), (266, 130)], WT, 2.8, head=False)
L([(266, 130), (266, 91), (245, 91)], WT, 2.8)
L([(266, 130), (266, 169), (245, 169)], WT, 2.8)
dot(266, 130, WT)

# ======================== (b) 按输出通道切分 ========================
f.panel(406, 8, 390, 240)
T(420, 32, '(b) 按输出通道切分', 16, K, 'start', 600)

# 左侧：权重按输出通道拆成 4 份，平分给两个 ANE
ch_labels = ['通道 0–63', '通道 64–127', '通道 128–191', '通道 192–255']
for i, lab in enumerate(ch_labels):
    y = 52 + i * 40
    B(418, y, 104, 32, lab, BLUE2 if i < 2 else BLUE3, 14)
T(470, 232, '权重', 15, K, 'middle', 600)

# 中间：ANE0 / ANE1
B(558, 66, 84, 50, 'ANE0', GREEN, 16)
B(558, 144, 84, 50, 'ANE1', GREEN, 16)

# 前两份 → ANE0；后两份 → ANE1
L([(522, 68), (538, 68), (538, 108), (522, 108)], WT, 2.4, head=False)
L([(538, 91), (557, 91)], WT, 2.4)
dot(538, 91, WT)
L([(522, 148), (538, 148), (538, 188), (522, 188)], WT, 2.4, head=False)
L([(538, 169), (557, 169)], WT, 2.4)
dot(538, 169, WT)

# 右侧：完整一份激活 → 两个 ANE
R(686, 90, 96, 80, BLUE)
T(734, 124, '激活', 16, K, 'middle', 600)
T(734, 148, '完整一份', 14, '#3a3a3c', 'middle', 400)
L([(686, 130), (664, 130)], ACT, 2.4, head=False)
L([(664, 130), (664, 91), (643, 91)], ACT, 2.4)
L([(664, 130), (664, 169), (643, 169)], ACT, 2.4)
dot(664, 130, ACT)

# ======================== (c) 跨引擎同步 ========================
f.panel(4, 260, 440, 252)
T(18, 284, '(c) 跨引擎同步', 16, K, 'start', 600)

R0, R1 = 310, 434
LH = 38
T(20, R0 + 25, 'ANE0', 15, K, 'start', 600)
T(20, R1 + 25, 'ANE1', 15, K, 'start', 600)

LX = [82, 206, 330]
LW = 96
# 同步竖虚线（先画，被共享暂存区和菱形压住，避免穿过文字）
SX = [192, 316]
for idx, sx in enumerate(SX):
    f.raw(f'<line x1="{sx}" y1="{R0 + LH / 2}" x2="{sx}" y2="{R1 + LH / 2}" stroke="{K}" stroke-width="1.6" stroke-dasharray="4 3"/>')
    T(sx, 496, f'同步 {idx + 1}', 14, K, 'middle', 600)

# 共享暂存区放在两行之间
B(82, 372, 344, 38, '共享暂存区', BLUE, 15)

for i, lx in enumerate(LX):
    B(lx, R0, LW, LH, f'层 {i + 1}', GREEN, 15)
    B(lx, R1, LW, LH, f'层 {i + 1}', GREEN, 15)
    if i < 2:
        sx = SX[i]
        L([(lx + LW, R0 + LH / 2), (LX[i + 1] - 1, R0 + LH / 2)], K, 1.8)
        L([(lx + LW, R1 + LH / 2), (LX[i + 1] - 1, R1 + LH / 2)], K, 1.8)
        diamond(sx, R0 + LH / 2)
        diamond(sx, R1 + LH / 2)

# ======================== (d) 切分判据 ========================
f.panel(456, 260, 340, 252)
T(470, 284, '(d) 切分判据', 16, K, 'start', 600)

X0 = 516
# 双 ANE 总延迟：各块延迟 + 合并（总宽 208 px）
T(X0 - 8, 336, '双 ANE', 15, K, 'end', 600)
B(X0, 314, 152, 32, '各块延迟', GREEN, 14)
B(X0 + 152, 314, 56, 32, '合并', MERGE, 14)

# × 0.5 → 切分估计（总宽的一半 = 104 px）
L([(X0 + 52, 346), (X0 + 52, 391)], K, 1.8)
T(X0 + 64, 374, '× 0.5', 15, K, 'start', 600)
B(X0, 392, 104, 32, '切分估计', GREEN, 14)

# 单 ANE（紧贴切分估计下方，直接上下对齐比较，无穿线）
T(X0 - 8, 468, '单 ANE', 15, K, 'end', 600)
B(X0, 446, 156, 32, '切分前延迟', WHITE, 14)

# 右侧空白处对齐比较
x_est = X0 + 104
x_sng = X0 + 156
f.raw(f'<line x1="{x_sng}" y1="396" x2="{x_sng}" y2="446" stroke="#7a7a7a" stroke-width="1.2" stroke-dasharray="3 3"/>')
L([(x_est + 2, 408), (x_sng - 2, 408)], WT, 2.0, both=True)
T(x_sng + 8, 413, '更短 → 切分', 14, WT, 'start', 600)

# 图例
f.legend([('line', ACT, None, '激活'), ('line', WT, None, '权重'), ('line', K, '4 3', '同步'),
          ('swatch', GREEN, '计算'), ('swatch', BLUE, '存储')], 538)
print(f.save('fig5-3_bonded'))
