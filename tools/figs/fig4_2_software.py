#!/usr/bin/env python3
# 图 4-2：从软件调用到硬件执行（样式见 archfig.py）。
# 图契约：
#   核心结论：一次推理从应用进入内核驱动，再进入 ANE 内的固件队列，由硬件按编译好的 TD 序列执行；
#             编译只在加载时经过 aned，推理不经过 aned；时钟档位由主机内核中的 CLPC 决定。
#   图原型：从左到右三个特权域（用户空间 → 内核 → ANE），上一行是加载（每个模型一次），下一行是推理（每次调用）。
#   用图形代替文字：TD 序列画成一排程序块；固件的 6 级优先级画成 6 条 FIFO 加仲裁器；硬件任务队列画成 2 项 FIFO。
#   能不能更少：驱动的职责、提交与完成的耗时（30 µs、130–325 µs、空闲 384 µs）写进图注。
from archfig import Fig, K, GREEN, BLUE, WHITE, PANEL

LOAD = '#2f5f98'
CLKC = '#7b4ea3'                       # 时钟档位：用颜色而不是线型区分
DONE = '6 4'
f = Fig(800, 400)
T, B, L, R = f.text, f.box, f.line, f.rect

# ---- 三个特权域 ----
UX, UW = 4, 232
KX, KW = 252, 224
AX, AW = 492, 290
PY, PH = 8, 346
f.panel(UX, PY, UW, PH)
f.panel(KX, PY, KW, PH)
R(AX + 10, PY - 6, AW, PH, '#e2e2e2', stroke=False, rx=10)      # 后一层：另一个 ANE
f.panel(AX, PY, AW, PH)
T(UX + 14, PY + 26, '用户空间', 16, K, 'start', 600)
T(KX + 14, PY + 26, '内核', 16, K, 'start', 600)
T(AX + 14, PY + 26, 'ANE × 2', 16, K, 'start', 600)

YL, YI, YC = 78, 204, 304          # 加载行、推理行、时钟行的中心
BH = 48

# ---- 用户空间 ----
B(UX + 36, YL - BH / 2, 160, BH, 'aned')
B(UX + 36, YI - BH / 2, 160, BH, 'Core ML')
L([(UX + 116, YI - BH / 2), (UX + 116, YL + BH / 2 + 1)], LOAD, 2.4)          # 加载时交给 aned 编译

# ---- 内核 ----
B(KX + 30, YI - BH / 2, 164, BH, 'ANE 驱动')
B(KX + 30, YC - BH / 2, 164, BH, 'CLPC')
L([(UX + 196, YI), (KX + 29, YI)], K, 2.4)                                    # 推理请求（不经过 aned）
L([(KX + 112, YI + BH / 2), (KX + 112, YC - BH / 2 - 1)], K, 2.4)              # 向 CLPC 报告作业

# ---- ANE ----
# 程序：编译好的 TD 序列
TX0, TN, TCW, TG = AX + 26, 7, 30, 5
for i in range(TN):
    B(TX0 + i * (TCW + TG), YL - 18, TCW, 36, '', BLUE)
L([(UX + 196, YL), (TX0 - 1, YL)], LOAD, 2.4)
# 固件：6 条 FIFO（6 级优先级），格子从右端出队；仲裁器（梯形）选出一个任务放入硬件的 2 项 FIFO
NC, CWq, QH, QG = 6, 19, 13, 4
QX, QW = AX + 26, NC * CWq
QH6 = 6 * QH + 5 * QG
QY = YI - QH6 / 2
fill = [1, 3, 0, 2, 0, 4]                                                      # 各队列中排队的任务（示意）
for j in range(6):
    y = QY + j * (QH + QG)
    for c in range(NC):
        R(QX + c * CWq, y, CWq, QH, '#7a7a7a' if c >= NC - fill[j] else WHITE, sw=0.6)
L([(KX + 194, YI), (QX - 1, YI)], K, 2.4)
MX, MW, MO = QX + QW + 10, 24, 36                                              # 仲裁器
for j in range(6):
    y = QY + j * (QH + QG) + QH / 2
    f.raw(f'<line x1="{QX + QW}" y1="{y}" x2="{MX}" y2="{y}" stroke="{K}" stroke-width="1.2"/>')
f.raw(f'<path d="M{MX} {QY - 6} L{MX + MW} {YI - MO / 2} L{MX + MW} {YI + MO / 2} L{MX} {QY + QH6 + 6} Z" '
      f'fill="{WHITE}" stroke="#2b2b2b" stroke-width="0.8"/>')
SX, SCW = MX + MW + 22, 19                                                     # 硬件的 2 项 FIFO
for c in range(2):
    R(SX + c * SCW, YI - QH / 2, SCW, QH, '#7a7a7a' if c == 1 else WHITE, sw=0.6)
L([(MX + MW, YI), (SX - 1, YI)], K, 2.4)
# 硬件
HX, HW = AX + 26, 244
B(HX, YC - BH / 2, HW, BH, '硬件', GREEN)
L([(SX + 1.5 * SCW, YI + QH / 2), (SX + 1.5 * SCW, YC - BH / 2 - 1)], K, 2.4)              # 取出任务执行
TXe = TX0 + TN * (TCW + TG) - TG
L([(TXe - TCW / 2, YL + 18), (TXe - TCW / 2, YC - BH / 2 - 1)], K, 2.4)        # 推理时硬件按 TD 序列执行（直线，不折弯）
# 时钟档位
L([(KX + 194, YC), (HX - 1, YC)], CLKC, 2.4)
# 完成中断：硬件 → 应用
L([(HX + 40, YC + BH / 2), (HX + 40, 340), (UX + 116, 340), (UX + 116, YI + BH / 2 + 1)], K, 1.8, DONE)

f.legend([('line', K, None, '推理'), ('line', LOAD, None, '加载'), ('line', K, DONE, '完成中断'),
          ('line', CLKC, None, '时钟档位'), ('swatch', GREEN, '硬件'), ('swatch', BLUE, 'TD 序列')], 388, x0=4, step=132)
print(f.save('fig4-2_software'))
