#!/usr/bin/env python3
# 图 9-1：中间张量的切块与执行顺序（样式见 archfig.py）。
# 图契约：
#   核心结论：超过 L2 单操作数上限（2 MiB）的中间张量沿宽度切成若干小于 2 MiB 的块；
#             每块连续执行完整条链（中间结果始终留在 L2 中），再处理下一块，仅首尾访问 DRAM。
#   图原型：(a) 16 MB 张量切成 9 块（上方标尺 < 2 MiB，呼应图 5-1）；
#           (b) 块 × 层执行网格，顶底为 DRAM，中间层间结果驻留右侧 L2，虚线标出跨块执行顺序。
#   能不能更少：具体维度、公式与每千像素耗时已在正文第 9.2.2 节与表 9-2 给出，图中不写长句。
from archfig import Fig, K, GREY, GREEN, BLUE, WHITE, ACT

f = Fig(800, 444)
T, B, L, R = f.text, f.box, f.line, f.rect

# ======================== (a) 切块 ========================
f.panel(4, 8, 792, 110)
T(18, 30, '(a) 切块（16 MB → 9 块）', 16, K, 'start', 600)

X0, TY, TW, TH = 31, 66, 82, 36
for i in range(9):
    B(X0 + i * TW, TY, TW, TH, f'块 {i + 1}', BLUE, 14)

# 块 1 上方标尺：< 2 MiB（呼应图 5-1 的 64 KiB 标尺）
yb = TY - 12
f.raw(f'<path d="M{X0} {yb + 5} v-5 H{X0 + TW} v5" fill="none" stroke="{K}" stroke-width="1.3"/>')
T(X0 + TW / 2, yb - 5, '&lt; 2 MiB', 13.5, K, 'middle', 600)

# ======================== (b) 按块深度优先执行 ========================
f.panel(4, 130, 792, 272)
T(18, 154, '(b) 按块深度优先执行', 16, K, 'start', 600)

# 网格几何：5 列（块 1、块 2、块 3、⋯、块 9）× 3 层（层 1、层 2、⋮、层 n）
BW, BH = 78, 24
COLS = [(92, '块 1'), (200, '块 2'), (308, '块 3'), (404, None), (476, '块 9')]
X_DRAM0, X_DRAM1 = 92, 476 + BW

Y_COL = 180
Y_DR1 = 190                        # 顶部 DRAM（读入）
Y_L1 = 234                         # 层 1
Y_L2 = 274                         # 层 2
Y_DOT = 311                        # ⋮
Y_LN = 324                         # 层 n
Y_DR2 = 366                        # 底部 DRAM（写出）

# 顶/底 DRAM 条
B(X_DRAM0, Y_DR1, X_DRAM1 - X_DRAM0, 24, 'DRAM', BLUE, 14)
B(X_DRAM0, Y_DR2, X_DRAM1 - X_DRAM0, 24, 'DRAM', BLUE, 14)

# 左侧层标签
T(80, Y_L1 + 17, '层 1', 14, K, 'end', 600)
T(80, Y_L2 + 17, '层 2', 14, K, 'end', 600)
T(68, Y_DOT + 3, '⋮', 16, K, 'middle', 600)
T(80, Y_LN + 17, '层 n', 14, K, 'end', 600)

# 各块列与层内橙色数据流
for cx, label in COLS:
    if label is None:
        for yy in (Y_L1 + 17, Y_L2 + 17, Y_LN + 17):
            T(cx + 32, yy, '⋯', 18, K, 'middle', 600)
        continue
    xm = cx + BW / 2
    T(xm, Y_COL, label, 14, K, 'middle', 600)
    # 顶 DRAM → 层 1
    L([(xm, Y_DR1 + 24), (xm, Y_L1 - 1)], ACT, 2.0)
    B(cx, Y_L1, BW, BH, '', GREEN)
    # 层 1 → 层 2
    L([(xm, Y_L1 + BH), (xm, Y_L2 - 1)], ACT, 2.0)
    B(cx, Y_L2, BW, BH, '', GREEN)
    # 层 2 → ⋮ → 层 n
    T(xm, Y_DOT + 3, '⋮', 15, ACT, 'middle', 600)
    B(cx, Y_LN, BW, BH, '', GREEN)
    # 层 n → 底 DRAM
    L([(xm, Y_LN + BH), (xm, Y_DR2 - 1)], ACT, 2.0)

# 跨块执行顺序（块 1 末端 → 块 2 起点，块 2 末端 → 块 3 起点）
for i in (0, 1):
    x1 = COLS[i][0]
    x2 = COLS[i + 1][0]
    xg = (x1 + BW + x2) / 2
    L([(x1 + BW, Y_LN + BH / 2), (xg, Y_LN + BH / 2), (xg, Y_L1 + BH / 2), (x2 - 1, Y_L1 + BH / 2)],
      K, 1.5, dash='4 3')

# 右侧 L2 驻留示意：用花括号/方括号对应 层 1..层 n 整个区间，表明层间不经过 DRAM
BX_R = X_DRAM1 + 16
f.raw(f'<path d="M{BX_R} {Y_L1} h8 V{Y_LN + BH} h-8" fill="none" stroke="{GREY}" stroke-width="1.5"/>')
L([(BX_R + 9, (Y_L1 + Y_LN + BH) / 2), (627, (Y_L1 + Y_LN + BH) / 2)], ACT, 2.2, both=True)

LX, LY, LW, LH = 628, Y_L1, 146, Y_LN + BH - Y_L1
R(LX, LY, LW, LH, BLUE)
T(LX + LW / 2, LY + 28, 'L2', 16, K, 'middle', 600)
T(LX + LW / 2, LY + 48, '2 MiB', 13.5, '#3a3a3c', 'middle', 400)
B(LX + 16, LY + 62, LW - 32, 38, '当前块', WHITE, 14)

# 图例
f.legend([('line', ACT, None, '激活数据'), ('line', K, '4 3', '执行顺序'),
          ('swatch', GREEN, '计算'), ('swatch', BLUE, '存储')], 426)
print(f.save('fig9-1_tiling'))
