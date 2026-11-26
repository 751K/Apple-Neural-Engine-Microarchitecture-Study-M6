#!/usr/bin/env python3
# 图 8-1：FP16 乘加路径的数据格式与三条运算路径对比（样式见 archfig.py）。
# 图契约：
#   核心结论：FP16 卷积/矩阵乘沿直通数据流完成解码、乘法、对齐至 2⁻¹⁶、以偏置为初值的 Q15.16 定点累加与
#             远离零舍入输出；|值| ≥ 32768 溢出为 inf，与 INT8（32 位整数）和 PE（FP16 浮点）不同。
#   图原型：(a) 单行从左到右硬件数据通路 + 虚线投影展开 32 位 Q15.16 位域（同图 4-1、图 5-2）；
#           (b) 三条运算路径的极简对比表。
#   能不能更少：特殊值解码、负偏置抵消与舍入示例留在第 8.2 节正文，不在图中堆砌长句。
from archfig import Fig, K, GREY, GREEN, BLUE, WHITE, ACT, WT

SIGN = '#f0c4bc'                   # 符号位（浅珊瑚红，darken.py 亮度 > 0.75 自动转暗底）
SUB = '#444444'

f = Fig(800, 450)
T, B, L, R = f.text, f.box, f.line, f.rect


def box2(x, y, w, h, title, sub, fill=WHITE, ts=15, ss=12.5):
    R(x, y, w, h, fill)
    T(x + w / 2, y + h / 2 - 4, title, ts, K, 'middle', 600)
    T(x + w / 2, y + h / 2 + 15, sub, ss, SUB, 'middle', 400)


# ======================== (a) FP16 乘加路径 ========================
f.panel(4, 8, 792, 266)
T(18, 32, '(a) FP16 乘加路径', 16, K, 'start', 600)

# 偏置 b 从正上方进入 Q15.16 累加器
QX, QW = 516, 122
B(QX, 20, QW, 26, '偏置 b（初值）', WHITE, 13.5)
L([(QX + QW / 2, 46), (QX + QW / 2, 67)], K, 2.0)

# 单行从左到右数据通路（x = 18 .. 782 满幅均匀排布）
PY, PH = 68, 54
YM = PY + PH / 2                   # 95

B(18, PY, 72, 24, 'x (FP16)', WHITE, 13)
B(18, PY + 30, 72, 24, 'w (FP16)', WHITE, 13)
L([(90, PY + 12), (111, PY + 12)], ACT, 2.2)
L([(90, PY + 42), (111, PY + 42)], WT, 2.2)

B(112, PY, 72, PH, '解码', WHITE, 15)
L([(184, YM), (205, YM)], K, 2.0)

box2(206, PY, 136, PH, '乘法', '尾数积 · 指数和 e', GREEN)
L([(342, YM), (363, YM)], K, 2.0)

box2(364, PY, 130, PH, '对齐至 2⁻¹⁶', 'e ≤ −17 丢弃', GREEN)
L([(494, YM), (QX - 1, YM)], K, 2.0)

box2(QX, PY, QW, PH, 'Q15.16', '32 位定点累加', BLUE)
L([(QX + QW, YM), (659, YM)], ACT, 2.2)

box2(660, PY, 122, PH, 'FP16 输出', '远离零舍入', GREEN)

# 虚线投影：Q15.16 累加器 → 下方 32 位位域图（同图 4-1、图 5-2 投影画法）
CW, CH, GAP = 15, 28, 8
TOT_W = 32 * CW + 2 * GAP          # 496 px
BX0, BY0 = (800 - TOT_W) / 2, 174  # 152 .. 648

f.raw(f'<path d="M{QX} {PY + PH} L{BX0} {BY0} M{QX + QW} {PY + PH} L{BX0 + TOT_W} {BY0}" '
      f'stroke="{GREY}" stroke-width="1.3" stroke-dasharray="5 4" fill="none"/>')

# 三段分组的 32 位位域：符号 [31]、整数 [30..16]、小数 [15..0]
xs = BX0
R(xs, BY0, CW, CH, SIGN, sw=0.6)
xi = xs + CW + GAP
for i in range(15):
    R(xi + i * CW, BY0, CW, CH, BLUE, sw=0.6)
xf = xi + 15 * CW + GAP
for i in range(16):
    R(xf + i * CW, BY0, CW, CH, GREEN, sw=0.6)

# 位号
ny = BY0 + CH + 16
T(xs + CW / 2, ny, '31', 12, SUB, 'middle', 400)
T(xi + 1, ny, '30', 12, SUB, 'start', 400)
T(xi + 15 * CW - 1, ny, '16', 12, SUB, 'end', 400)
T(xf + 1, ny, '15', 12, SUB, 'start', 400)
T(xf + 16 * CW - 1, ny, '0', 12, SUB, 'end', 400)

# 三段位域标签
ly = BY0 + CH + 39
T(xs + CW / 2, ly, '符号', 13, K, 'middle', 600)
T(xi + 7.5 * CW, ly, '整数 15 位（|值| &lt; 32768）', 13, K, 'middle', 600)
T(xf + 8.0 * CW, ly, '小数 16 位（2⁻¹⁶）', 13, K, 'middle', 600)

# ======================== (b) 三条运算路径对比 ========================
f.panel(4, 286, 792, 156)
T(18, 310, '(b) 三条运算路径对比', 16, K, 'start', 600)

HY = 334
T(26, HY, '路径', 13, SUB, 'start', 600)
T(250, HY, '累加 / 运算格式', 13, SUB, 'start', 600)
T(560, HY, '溢出行为', 13, SUB, 'start', 600)
f.raw(f'<line x1="20" y1="{HY + 8}" x2="780" y2="{HY + 8}" stroke="#c8c8cc" stroke-width="1"/>')

rows = [
    ('FP16 卷积 / 矩阵乘', GREEN, '32 位定点 Q15.16', '|值| ≥ 32768 → inf'),
    ('INT8 卷积 (W8A8)', GREEN, '32 位整数（累加后缩放）', '|S| ≥ 2³¹ → inf'),
    ('逐元素运算 (PE)', WHITE, 'FP16 浮点（保留非规格化数）', '&gt; 65504 → inf'),
]
for i, (path, fill, fmt, ovf) in enumerate(rows):
    ry = 350 + i * 30
    B(20, ry, 198, 24, path, fill, 13.5)
    T(250, ry + 17, fmt, 13.5, K, 'start', 400)
    T(560, ry + 17, ovf, 13.5, K, 'start', 400)
    if i < 2:
        f.raw(f'<line x1="20" y1="{ry + 27}" x2="780" y2="{ry + 27}" stroke="#e0e0e4" stroke-width="0.8"/>')

print(f.save('fig8-1_accumulator'))
