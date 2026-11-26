#!/usr/bin/env python3
# 图 5-2：TD 的结构（样式见 archfig.py，部件名与图 4-1 相同）。
# 图契约：
#   核心结论：一个 TD 是一串寄存器写入包：12 字任务头之后，写入包按寄存器组排列，顺序与数据在硬件中的流向一致，
#             每组写入包配置一个部件；末尾是地址包。
#   图原型：三层由上到下逐级展开（虚线投影，同图 4-1）：
#           ① 一个 ANE 的 TD 序列；② 其中一个 TD 按字展开（每格一个 32 位字，深色格 = 包头）；
#           ③ 各组写入包向下连到它所配置的部件（部件填色与图 4-1 相同）。
#   能不能更少：包头的位格式与示例字（表 5-7）、字段（表 5-6、5-8）不在图中画出。
from archfig import Fig, K, GREEN, BLUE, WHITE, GREY

HDR = '#5a5a5a'                    # 包头字
TASK = '#d9d9d9'                   # 任务头
ADDR = '#e7d9b8'                   # 地址包（缓冲区地址）
f = Fig(800, 322)
T, B, L, R = f.text, f.box, f.line, f.rect

# ① TD 序列
SY, SH = 18, 34
R(16, SY, 40, SH, TASK)                                     # 序列头
tdx = [64 + i * 112 for i in range(5)]
for i, x in enumerate(tdx):
    B(x, SY, 104, SH, f'TD{i}' if i < 4 else '⋯', WHITE, 16)
Z = 1                                                       # 展开 TD1

# ② 一个 TD 按字展开
CW = 9.6                                                      # 每个字的宽度
RY, RH = 112, 30
groups = [  # (名称, 填色, [每个写入包的数据字数])
    ('任务头', TASK, None),
    ('公共', WHITE, [3, 6]),
    ('Tile DMA', WHITE, [4, 2]),
    ('纹理采样', WHITE, [3]),
    ('L2', BLUE, [4, 2]),
    ('PE', GREEN, [3]),
    ('NE', GREEN, [5, 7]),
    ('Tile DMA', WHITE, [4]),
    ('地址包', ADDR, [1, 1, 1, 1]),
]
x = 16
spans = []
for name, fill, pk in groups:
    x0 = x
    if pk is None:                                           # 12 字任务头
        for i in range(12):
            R(x, RY, CW, RH, fill, sw=0.6)
            x += CW
    else:
        for n in pk:
            R(x, RY, CW, RH, HDR, sw=0.6)                    # 包头
            x += CW
            for i in range(n):
                R(x, RY, CW, RH, fill, sw=0.6)
                x += CW
    spans.append((x0, x))
    x += 6
RX1 = x - 6
# 投影：TD1 → 展开的 TD
f.raw(f'<path d="M{tdx[Z]} {SY + SH} L16 {RY} M{tdx[Z] + 104} {SY + SH} L{RX1} {RY}" stroke="{GREY}" '
      f'stroke-width="1.2" stroke-dasharray="5 4" fill="none"/>')
# 不对应单个部件的三组（任务头、公共字段、地址包）：名称写在字串下方
for gi in (0, 1, 8):
    a, b = spans[gi]
    T((a + b) / 2, RY + RH + 22, groups[gi][0], 15, K, 'middle', 600)

# ③ 各组写入包配置的部件（按数据流向从左到右，与图 4-1 的部件相同）
UY, UH, UW = 228, 42, 92
units = list(range(2, 8))
ux0 = RX1 - (len(units) * UW + (len(units) - 1) * 10)          # 右端与展开的 TD 对齐
for j, gi in enumerate(units):
    name, fill, _ = groups[gi]
    a, b = spans[gi]
    ux = ux0 + j * (UW + 10)
    B(ux, UY, UW, UH, name, fill, 15)
    L([((a + b) / 2, RY + RH + 2), (ux + UW / 2, UY - 1)], K, 1.4)

f.legend([('swatch', HDR, '包头'), ('swatch', TASK, '任务头'), ('swatch', ADDR, '地址包'),
          ('swatch', GREEN, '计算'), ('swatch', BLUE, '存储'), ('swatch', WHITE, '搬运')], 304)
print(f.save('fig5-2_td_format'))
