#!/usr/bin/env python3
# 图 4-1：M6 ANE 的硬件结构（画法参考 Eyeriss、Gemmini、SCNN 等体系结构论文的结构图）。
#   填色只分三类：计算 = 浅绿，存储 = 浅蓝，数据搬运与控制 = 白；方框加深灰细描边，灰色只作分区底色（不描边）。
#   连线颜色区分数据：激活 = 橙，权重 = 深红，控制 = 黑色虚线。
#   (a) ANE0 整体，16 个 NE 画成叠放的副本；最前面的 NE 用虚线投影放大为右侧 (b)。
#   (b) 上半为一个 NE 的乘加阵列：激活切片（最前一片 = 本周期的 1 个输入通道）沿列广播，
#       权重缓冲中本周期的一列沿行广播；8 行（输出通道）× 32 列（像素，画 4 列 + 省略号）。
#       下半把一个单元放大成数据通路：乘 → 加 → 累加寄存器，寄存器回送形成累加环。
#   具体数值（带宽、时钟、累加器格式等）写在图注和正文中，图中不写。
import os
from archfig import legend_html

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'figs', 'zh', 'light')
SK, SW = '#2b2b2b', 0.8          # 描边颜色与线宽
K = '#111111'
GREEN, BLUE, GREY, LIGHT = '#d5e3b8', '#b6c9e6', '#d9d9d9', '#ffffff'
ACT, WT = '#e07b22', '#a5302e'
W, H = 800, 560

o = []
a = o.append


def text(x, y, s, size=17, col=K, anchor='middle', w=600):
    a(f'<text x="{x}" y="{y}" text-anchor="{anchor}" style="font-size:{size}px;fill:{col};font-weight:{w}">{s}</text>')


def box(x, y, w, h, title='', fill=LIGHT, dash=False, sw=1.6, size=17, frame=False):
    # 实线方框填色并加细描边；dash 为虚线框，frame 为浅灰细框（本图未用）
    if dash:
        a(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="#ffffff" stroke="{K}" stroke-width="{sw}" stroke-dasharray="6 4"/>')
    elif frame:
        a(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="#ffffff" stroke="#9a9a9a" stroke-width="1.2"/>')
    else:
        a(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="{fill}" stroke="{SK}" stroke-width="{SW}"/>')
    if title:
        text(x + w / 2, y + h / 2 + 6, title, size)


MK = {ACT: 'ma', WT: 'mw', K: 'mk'}


def arrow(pts, col=K, sw=2.2, dash=False, head=True, both=False):
    d = ' '.join(f'{x},{y}' for x, y in pts)
    m = MK[col]
    a(f'<polyline points="{d}" fill="none" stroke="{col}" stroke-width="{sw}" stroke-linejoin="miter"'
      + (' stroke-dasharray="5 4"' if dash else '') + (f' marker-end="url(#{m})"' if head else '')
      + (f' marker-start="url(#{m})"' if both else '') + '/>')


def dot(x, y, col=K):
    a(f'<circle cx="{x}" cy="{y}" r="3.6" fill="{col}"/>')


def grid(x, y, nx, ny, cw, ch, fill, line='#ffffff', sw=1, outline=K, osw=2):
    a(f'<rect x="{x}" y="{y}" width="{nx * cw}" height="{ny * ch}" fill="{fill}"/>')
    for i in range(1, nx):
        a(f'<line x1="{x + i * cw:.2f}" y1="{y}" x2="{x + i * cw:.2f}" y2="{y + ny * ch}" stroke="{line}" stroke-width="{sw}"/>')
    for j in range(1, ny):
        a(f'<line x1="{x}" y1="{y + j * ch:.2f}" x2="{x + nx * cw}" y2="{y + j * ch:.2f}" stroke="{line}" stroke-width="{sw}"/>')
    if outline:
        a(f'<rect x="{x}" y="{y}" width="{nx * cw}" height="{ny * ch}" fill="none" stroke="{outline}" stroke-width="{osw}"/>')


a(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}">')
a('<defs>' + ''.join(
    f'<marker id="{m}" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="4.5" markerHeight="4.5" orient="auto-start-reverse">'
    f'<path d="M0,0 L10,5 L0,10 z" fill="{c}"/></marker>' for c, m in MK.items())
  + '</defs>')
a(f'<rect width="{W}" height="{H}" fill="#ffffff"/>')

# ======================= (a) =======================
box(4, 8, 466, 40, 'DRAM', fill=BLUE)
# ANE0 区域：灰色底
a(f'<rect x="4" y="76" width="466" height="436" rx="10" fill="#efefef"/>')
text(20, 500, 'ANE0', 17, anchor='start')
NX0, NY0, NW0, NH0 = 170, 340, 190, 116
# NE → (b)：虚线投影
BX, BY, BW, BH = 498, 8, 298, 504
a(f'<path d="M{NX0 + NW0} {NY0} L{BX} {BY} M{NX0 + NW0} {NY0 + NH0} L{BX} {BY + BH}" stroke="#8c8c8c" '
  f'stroke-width="1.4" stroke-dasharray="5 4" fill="none"/>')


C1, C2, C3, C4, CW = 18, 133, 248, 363, 103
mid = lambda c: c + CW / 2
R1 = 96
box(C1, R1, CW, 46, 'Kernel DMA', size=16)
box(C2, R1, CW, 46, 'Tile DMA', size=16)
box(C3, R1, CW, 46, 'Tile DMA', size=16)
box(C4, R1, CW, 46, '任务控制', size=16)

arrow([(mid(C1), 48), (mid(C1), R1 - 1)], WT, 3.4)
arrow([(mid(C2) - 12, 48), (mid(C2) - 12, R1 - 1)], ACT, 2.6)
arrow([(mid(C2) + 12, 48), (mid(C2) + 12, R1 - 1)], ACT, 2.6)
arrow([(mid(C3), R1), (mid(C3), 49)], ACT, 2.6)
arrow([(mid(C4), 48), (mid(C4), R1 - 1)], K, 1.6, dash=True)

R2 = 166
box(C2, R2, CW, 42, '纹理采样', size=16)
arrow([(mid(C2), R1 + 46), (mid(C2), R2 - 1)], ACT, 2.6)

R3 = 232
box(C2, R3, C4 - C2 - 30, 56, 'L2', fill=BLUE)
box(C4, R3, CW, 56, 'PE', fill=GREEN)
arrow([(mid(C2), R2 + 42), (mid(C2), R3 - 1)], ACT, 2.6)
arrow([(mid(C3), R3), (mid(C3), R1 + 47)], ACT, 2.6)
arrow([(C4 - 29, R3 + 28), (C4 - 1, R3 + 28)], ACT, 2.6, both=True)
arrow([(mid(C4), R1 + 46), (mid(C4), R3 - 1)], K, 1.6, dash=True)

# NE：叠放的副本表示 16 个；每个 NE 内含权重缓冲
NX, NY, NW, NH = 170, 340, 190, 116
for k in (3, 2, 1):
    a(f'<rect x="{NX + 8 * k}" y="{NY - 8 * k}" width="{NW}" height="{NH}" fill="#d5e3b8" stroke="{SK}" stroke-width="{SW}"/>')
box(NX, NY, NW, NH, fill=GREEN)
text(NX + NW / 2, NY + 34, 'NE', 18)
box(NX + 14, NY + 56, NW - 28, 44, '权重缓冲', fill=BLUE, size=16)
text(NX + NW + 52, NY + NH / 2 + 8, '× 16', 20)

# 激活 / 结果：L2 ↔ NE
arrow([(C2 + 60, R3 + 56), (C2 + 60, NY - 1)], ACT, 2.6)
arrow([(C3 + 40, NY - 24), (C3 + 40, R3 + 57)], ACT, 2.6)
# 权重：Kernel DMA → 权重缓冲（不经过 L2）
arrow([(mid(C1), R1 + 46), (mid(C1), NY + 78), (NX + 13, NY + 78)], WT, 3.4)

# ======================= (b) =======================
# 一个 NE 内部（论文画法）：上半是乘加阵列，下半把其中一个单元放大成数据通路。
#   阵列：上方激活切片（最前一片橙 = 本周期的输入通道）沿列广播；左侧权重缓冲（红列 = 本周期）沿行广播；
#         8 行（输出通道）× 32 列（像素，画 4 列 + 省略号），绿色单元底部蓝条为累加器。
#   放大：⊗ 乘 → ⊕ 加 → 累加寄存器，寄存器回送 ⊕ 形成累加环；结果送出。
a(f'<rect x="{BX}" y="{BY}" width="{BW}" height="{BH}" rx="10" fill="#efefef"/>')

CX = [576, 618, 660, None, 742]
cols = [c for c in CX if c is not None]
RY = [80 + 27 * i for i in range(8)]
CWm, CHm = 30, 21

# 放大投影（先画，被单元盖住）
ZX, ZY, ZW, ZH = 526, 322, 262, 168
zc, zr = 660, RY[-1]
a(f'<path d="M{zc} {zr + CHm} L{ZX} {ZY} M{zc + CWm} {zr + CHm} L{ZX + ZW} {ZY}" stroke="#8c8c8c" '
  f'stroke-width="1.4" stroke-dasharray="5 4" fill="none"/>')

# 激活切片
SY = 42
X0, X1 = CX[0], CX[-1] + CWm
for k in (3, 2, 1):
    a(f'<rect x="{X0 - 7 * k}" y="{SY - 7 * k}" width="{X1 - X0}" height="14" fill="{BLUE}" stroke="{SK}" stroke-width="{SW}"/>')
a(f'<rect x="{X0}" y="{SY}" width="{X1 - X0}" height="14" fill="{ACT}" stroke="{SK}" stroke-width="{SW}"/>')

# 权重缓冲
WX, WC = 512, 10
for j in range(4):
    a(f'<rect x="{WX + j * (WC + 3)}" y="{RY[0]}" width="{WC}" height="{RY[-1] + CHm - RY[0]}" fill="{WT if j == 3 else BLUE}" stroke="{SK}" stroke-width="{SW}"/>')

# 广播线（单元背后）
for c in cols:
    a(f'<line x1="{c + CWm / 2}" y1="{SY + 14}" x2="{c + CWm / 2}" y2="{RY[-1] + 4}" stroke="{ACT}" stroke-width="2.2"/>')
for r in RY:
    a(f'<line x1="{WX + 4 * (WC + 3) - 3}" y1="{r + 9}" x2="{CX[-1] + 4}" y2="{r + 9}" stroke="{WT}" stroke-width="2.2"/>')

for r in RY:
    for c in cols:
        a(f'<rect x="{c}" y="{r}" width="{CWm}" height="{CHm}" fill="{GREEN}"/>')
        a(f'<rect x="{c}" y="{r + CHm - 6}" width="{CWm}" height="6" fill="{BLUE}"/>')
        a(f'<line x1="{c}" y1="{r + CHm - 6}" x2="{c + CWm}" y2="{r + CHm - 6}" stroke="{SK}" stroke-width="0.5"/>')
        a(f'<rect x="{c}" y="{r}" width="{CWm}" height="{CHm}" fill="none" stroke="{SK}" stroke-width="0.7"/>')
    text(716, r + CHm / 2 + 6, '⋯', 20, K, 'middle', 400)
# 被放大的单元加深一点
a(f'<rect x="{zc}" y="{zr}" width="{CWm}" height="{CHm}" fill="none" stroke="#5a5a5a" stroke-width="1.6"/>')

# 放大后的单元：数据通路
a(f'<rect x="{ZX}" y="{ZY}" width="{ZW}" height="{ZH}" fill="{GREEN}" stroke="{SK}" stroke-width="{SW}"/>')
MX, MY, R = 612, 384, 23          # ⊗
AX = 706                          # ⊕
def op(cx, cy, kind):
    a(f'<circle cx="{cx}" cy="{cy}" r="{R}" fill="#ffffff" stroke="{K}" stroke-width="1.8"/>')
    d = R * 0.5
    if kind == 'x':
        a(f'<path d="M{cx - d} {cy - d} L{cx + d} {cy + d} M{cx - d} {cy + d} L{cx + d} {cy - d}" stroke="{K}" stroke-width="2.2"/>')
    else:
        a(f'<path d="M{cx - d * 1.2} {cy} H{cx + d * 1.2} M{cx} {cy - d * 1.2} V{cy + d * 1.2}" stroke="{K}" stroke-width="2.2"/>')
arrow([(MX, ZY + 2), (MX, MY - R - 1)], ACT, 2.6)                 # 激活从上方进入
arrow([(ZX + 2, MY), (MX - R - 1, MY)], WT, 2.6)                  # 权重从左侧进入
arrow([(MX + R, MY), (AX - R - 1, MY)], K, 2.0)                   # 乘积 → 加法
RGX, RGY, RGW, RGH = AX - 28, 432, 56, 24                         # 累加寄存器
arrow([(AX + R, MY), (AX + 50, MY), (AX + 50, RGY + RGH / 2), (RGX + RGW + 1, RGY + RGH / 2)], K, 2.0)
arrow([(AX, RGY), (AX, MY + R + 1)], K, 2.0)                      # 回送形成累加环
a(f'<rect x="{RGX}" y="{RGY}" width="{RGW}" height="{RGH}" fill="{BLUE}" stroke="{SK}" stroke-width="{SW}"/>')
arrow([(AX, RGY + RGH), (AX, ZY + ZH - 2)], ACT, 2.6)             # 结果送出
op(MX, MY, 'x')
op(AX, MY, '+')

# 图例（各项均匀分布，见 archfig.legend_html）
a(legend_html([('line', ACT, None, '激活'), ('line', WT, None, '权重'), ('line', K, '5 4', '控制'),
               ('swatch', GREEN, '计算'), ('swatch', BLUE, '存储'), ('swatch', '#ffffff', '搬运与控制')], H - 22, W))

a('</svg>')
font = 'text{font-family:Arial,"Helvetica Neue","PingFang SC",sans-serif}'
svg = '\n'.join(o).replace('<defs>', f'<style>{font}</style><defs>', 1)
open(os.path.join(OUT, 'fig4-1_hardware.svg'), 'w').write(svg)

