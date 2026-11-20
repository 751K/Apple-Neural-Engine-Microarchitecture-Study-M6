#!/usr/bin/env python3
# 图 5-1：权重的切分（样式见 archfig.py）。
# 图契约：
#   核心结论：一个 TD 中每个 NE 的权重超过权重缓冲（64 KiB）时，编译器按输出通道把它切成几个 TD，每个都放得下。
#   图原型：只画切割本身。上：原始 TD（一个 NE 分到的权重，长度与 KiB 成正比），虚线为切开处，上方标尺为 64 KiB；
#           下：切开后的 TD0、TD1、TD2，各自都不超过标尺。
#   能不能更少：NE、Kernel DMA、执行顺序等都不画；形状与字节数（1×9 卷积 256 通道、每 NE 154 KiB、
#               64/96/96 个输出通道、输入较小时不拆）写进图注。
from archfig import Fig, K

TINT = ['#dfe8f5', '#c3d4ec', '#a6bfe3']    # 三段权重
f = Fig(580, 204)
T, L, R = f.text, f.line, f.rect

SC = 112 / 64                      # 每 KiB 的像素数（64 KiB = 112 px）
share = [38.5, 57.75, 57.75]       # 每段在每个 NE 上的权重（KiB）：154 KiB 按 64、96、96 个输出通道拆开
X0, BH = 124, 36
Y1, Y2 = 58, 150                   # 原始 TD 与切开后的 TD 所在的高度
GAPS = 40                          # 切开后段与段之间的空隙


def bar(x, y, k, label=''):
    w = share[k] * SC
    R(x, y, w, BH, TINT[k])
    if label:
        T(x + w / 2, y + BH / 2 + 6, label, 16, K, 'middle', 600)
    return w


# 上：原始 TD
x = X0
starts = []
for k in range(3):
    starts.append(x)
    x += bar(x, Y1, k)
for xb in starts[1:]:              # 切开处
    f.raw(f'<line x1="{xb}" y1="{Y1}" x2="{xb}" y2="{Y1 + BH}" stroke="#ffffff" stroke-width="2"/>')
    f.raw(f'<line x1="{xb}" y1="{Y1 - 10}" x2="{xb}" y2="{Y1 + BH + 10}" stroke="{K}" stroke-width="1.4" stroke-dasharray="4 3"/>')
T(X0 - 16, Y1 + BH / 2 + 6, '原始 TD', 16, K, 'end', 600)
# 64 KiB 标尺
yb = Y1 - 18                       # 标尺放在原始 TD 上方，不挡下方的箭头
f.raw(f'<path d="M{X0} {yb + 6} v-6 H{X0 + 64 * SC} v6" fill="none" stroke="{K}" stroke-width="1.4"/>')
T(X0 + 32 * SC, yb - 8, '64 KiB', 16, K, 'middle', 600)

# 下：切开后的三个 TD
for k in range(3):
    xs = starts[k]
    xd = starts[k] + k * GAPS
    w = share[k] * SC
    bar(xd, Y2, k, f'TD{k}')
# 切开的方向：每段向下落到自己的位置
for k in range(3):
    w = share[k] * SC
    xs, xd = starts[k] + w / 2, starts[k] + k * GAPS + w / 2
    y0 = Y1 + BH + 2
    L([(xs, y0), (xd, Y2 - 2)], '#555555', 1.6)
print(f.save('fig5-1_weight_split'))
