#!/usr/bin/env python3
# 图 8-1：FP16 乘加路径的数据格式（第 8.2 节）与三条运算路径的对比（8.3、8.4 节）。纯示意图。
import os
o = []
a = o.append
W, H = 1440, 640
a(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" font-family="PingFang SC, Helvetica Neue, Arial, sans-serif">')
a('<style>text{fill:#1d1d1f} .h{font-size:18px;font-weight:600} .b{font-size:14.5px;fill:#3a3a3c} .c{font-size:13px;fill:#6e6e73}'
  ' .m{font-size:13px;font-family:Menlo,SF Mono,monospace;fill:#3a3a3c} .mid{text-anchor:middle} .end{text-anchor:end}</style>')
a('<defs><marker id="ar" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">'
  '<path d="M0,0 L10,5 L0,10 z" fill="#48484a"/></marker></defs>')


def box(x, y, w, h, f, s, dash=False):
    a(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="10" fill="{f}" stroke="{s}" stroke-width="1.5"' + (' stroke-dasharray="5 4"' if dash else '') + '/>')


def t(x, y, s, c='b', anc=''):
    a(f'<text class="{c}{" " + anc if anc else ""}" x="{x}" y="{y}">{s}</text>')


def arr(d):
    a(f'<path d="{d}" stroke="#48484a" stroke-width="1.6" fill="none" marker-end="url(#ar)"/>')


IO = ('#ffffff', '#8e8e93'); DEC = ('#f5f5f7', '#8e8e93'); MUL = ('#e7eaf3', '#3c5488')
ACC = ('#f5f0eb', '#7e6148'); OUT = ('#e3f4f0', '#00a087')

t(40, 30, 'FP16 卷积与矩阵乘的计算过程', 'h')
# 第一行：输入 → 解码 → 乘法 → 对齐
box(40, 52, 130, 50, *IO); t(105, 83, 'x（FP16）', 'b', 'mid')
box(40, 118, 130, 50, *IO); t(105, 149, 'w（FP16）', 'b', 'mid')
box(220, 52, 300, 116, *DEC)
t(370, 80, '输入解码', 'h', 'mid')
t(370, 106, '指数全 1 的值按普通数解码：', 'c', 'mid')
t(370, 126, '+inf → 2¹⁶，NaN 0x7E00 → 1.5 × 2¹⁶', 'c', 'mid')
t(370, 148, '因超出累加器范围而得到 inf', 'c', 'mid')
arr('M170 77 H216'); arr('M170 143 H216')
box(570, 52, 260, 116, *MUL)
t(700, 80, '乘法', 'h', 'mid')
t(700, 108, '尾数之积 ∈ [1, 4)', 'b', 'mid')
t(700, 130, '指数之和 e', 'b', 'mid')
t(700, 152, '（推测的内部表示）', 'c', 'mid')
arr('M520 110 H566')
box(880, 52, 520, 116, *MUL)
t(1140, 80, '对齐到 2⁻¹⁶', 'h', 'mid')
t(900, 110, 'e ≥ −16：', 'b'); t(980, 110, '四舍五入（中间值远离零）后加入累加器', 'b')
t(900, 136, 'e ≤ −17：', 'b'); t(980, 136, '整个乘积被丢弃，即使其值接近 2 LSB', 'b')
t(900, 158, '非规格化数的指数按 −14 计', 'c')
arr('M830 110 H876')

# 第二行：偏置 → 累加器 → 输出转换
arr('M1000 168 V236')
box(40, 240, 260, 150, *DEC)
t(170, 268, '偏置 b（FP16）', 'h', 'mid')
t(170, 296, '舍入到 2⁻¹⁶（远离零）', 'b', 'mid')
t(170, 318, '作为累加器的初值', 'b', 'mid')
t(170, 346, '负的大偏置可抵消正的乘积，', 'c', 'mid')
t(170, 366, '使中间值不溢出', 'c', 'mid')
arr('M300 315 H346')
box(350, 240, 760, 150, *ACC)
t(370, 268, '累加器：32 位定点 Q15.16', 'h')
x0, cw = 390, 21
cols = [('#f6c3bb', 1), ('#c3cbe0', 15), ('#c8e9e1', 16)]
x = x0
for col, n in cols:
    for i in range(n):
        a(f'<rect x="{x}" y="286" width="{cw}" height="30" fill="{col}" stroke="#ffffff" stroke-width="1.5"/>')
        x += cw
t(x0 + cw / 2, 334, '31', 'm', 'mid'); t(x0 + cw * 1.5, 334, '30', 'm', 'mid'); t(x0 + cw * 15.5, 334, '16', 'm', 'mid')
t(x0 + cw * 16.5, 334, '15', 'm', 'mid'); t(x0 + cw * 31.5, 334, '0', 'm', 'mid')
t(x0 + cw / 2, 356, '符号', 'c', 'mid')
t(x0 + cw * 8.5, 356, '整数 15 位：|值| &lt; 2¹⁵ = 32768', 'c', 'mid')
t(x0 + cw * 24.5, 356, '小数 16 位：LSB = 2⁻¹⁶', 'c', 'mid')
t(370, 380, '任何时刻 |值| 达到 32768 即变为 inf，之后不再恢复；累加过程中没有 FP16 精度的部分和。', 'c')
arr('M1110 315 H1156')
box(1160, 240, 240, 150, *OUT)
t(1280, 268, '转换为 FP16 输出', 'h', 'mid')
t(1280, 298, '四舍五入，中间值远离零', 'b', 'mid')
t(1280, 320, '（不是 IEEE 的取偶）', 'c', 'mid')
t(1280, 346, '2049 → 2050', 'm', 'mid')
t(1280, 368, '−0 → +0', 'm', 'mid')

# 第三行：三条路径的对比
t(40, 446, '三条运算路径的对比', 'h')
cards = [('FP16 卷积 / 矩阵乘', MUL, ['32 位定点 Q15.16（上图）', '范围 |值| &lt; 32768，分辨率 2⁻¹⁶', '溢出 → inf', '8.2 节']),
         ('INT8 卷积（W8A8）', MUL, ['32 位整数累加，缩放在累加完成后进行', '可超过 32768（如 64512）', 'S ≥ 2³¹ 时溢出 → inf', '8.3 节']),
         ('逐元素运算（PE）', ('#f5f5f7', '#8e8e93'), ['FP16 浮点运算', '保留非规格化数（如 2⁻²⁴）', '超出 FP16 最大值时 → inf', '8.4 节'])]
for i, (title, col, lines) in enumerate(cards):
    x = 40 + i * 460
    box(x, 464, 440, 150, *col)
    t(x + 20, 496, title, 'h')
    for j, s in enumerate(lines[:-1]):
        t(x + 20, 528 + j * 28, s, 'b')
    t(x + 420, 600, lines[-1], 'c', 'end')
a('</svg>')
open(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'figs', 'fig8-1_accumulator.svg'), 'w').write('\n'.join(o))
