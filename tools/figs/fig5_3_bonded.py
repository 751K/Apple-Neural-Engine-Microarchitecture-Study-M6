#!/usr/bin/env python3
# 第 5.7 节示意图：双 ANE 程序的两种切分方式、跨 ANE 的数据交换与同步、切分判据。
import os
o = []
a = o.append
W, H = 1440, 730
a(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" font-family="PingFang SC, Helvetica Neue, Arial, sans-serif">')
a('<style>text{fill:#1d1d1f} .h{font-size:18px;font-weight:600} .h2{font-size:16px;font-weight:600} .b{font-size:14.5px;fill:#3a3a3c}'
  ' .c{font-size:13px;fill:#6e6e73} .m{font-size:12.5px;font-family:Menlo,SF Mono,monospace;fill:#3a3a3c} .mid{text-anchor:middle} .end{text-anchor:end}</style>')
a('<defs>'
  '<marker id="ar" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="#48484a"/></marker>'
  '<marker id="ac" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="#7e6148"/></marker>'
  '<pattern id="hatch" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)"><line x1="0" y1="0" x2="0" y2="6" stroke="#7e6148" stroke-width="1.5"/></pattern>'
  '</defs>')

A0 = ('#e7eaf3', '#3c5488')      # ANE0
A1 = ('#e3f4f0', '#00a087')      # ANE1
WT = ('#e1f3f8', '#2f9ab5')      # 权重
NEU = ('#ffffff', '#8e8e93')


def box(x, y, w, h, c, rx=8, dash=False):
    a(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{c[0]}" stroke="{c[1]}" stroke-width="1.4"' + (' stroke-dasharray="5 4"' if dash else '') + '/>')


def t(x, y, s, c='b', anc=''):
    a(f'<text class="{c}{" " + anc if anc else ""}" x="{x}" y="{y}">{s}</text>')


def arr(d, col='#48484a', m='ar', w=1.5, dash=False):
    a(f'<path d="{d}" stroke="{col}" stroke-width="{w}" fill="none" marker-end="url(#{m})"' + (' stroke-dasharray="5 4"' if dash else '') + '/>')


# ======== ① 按行切分 ========
t(40, 32, '① 按行切分（基准模型：1×1 卷积链，高 64）', 'h')
box(70, 60, 180, 110, A0, rx=2); box(70, 170, 180, 110, A1, rx=2)
a('<rect x="70" y="158" width="180" height="24" fill="url(#hatch)" opacity="0.55"/>')
t(160, 112, '行 0–31', 'b', 'mid'); t(160, 232, '行 32–63', 'b', 'mid')
t(160, 302, '激活张量', 'c', 'mid')
box(320, 82, 130, 64, A0); t(385, 120, 'ANE0', 'h2', 'mid')
box(320, 194, 130, 64, A1); t(385, 232, 'ANE1', 'h2', 'mid')
arr('M250 114 H316'); arr('M250 226 H316')
box(540, 128, 130, 84, WT); t(605, 162, '权重', 'h2', 'mid'); t(605, 186, '（完整一份）', 'c', 'mid')
a('<path d="M540 170 H495" stroke="#48484a" stroke-width="1.5" fill="none"/>'); arr('M495 170 V114 H454'); arr('M495 170 V226 H454')
t(605, 236, '两个 ANE 各读一份', 'c', 'mid')
t(70, 330, '两个 ANE 用同一份权重，各自用满 16 个 NE，最后合并结果。', 'c')
t(70, 350, '纵向尺寸大于 1 的卷积核还要读相邻的重叠行（斜线），层数越多重叠越多。', 'c')
t(70, 370, 'TD 中：高度 64 → 32；ANE1 的地址包偏移 32 行；PublishBit 置 1。', 'c')

# ======== ② 按输出通道切分 ========
X = 760
t(X, 32, '② 按输出通道切分（例：8×32 的 5×5 卷积，每层 4 趟 × 64 通道）', 'h')
for i in range(4):
    c = A0 if i < 2 else A1
    box(X + 10, 60 + i * 54, 170, 46, c, rx=4)
    t(X + 95, 89 + i * 54, f'第 {i + 1} 趟：64 个输出通道', 'c', 'mid')
t(X + 95, 302, '权重的 4 趟', 'c', 'mid')
box(X + 270, 82, 130, 64, A0); t(X + 335, 120, 'ANE0', 'h2', 'mid')
box(X + 270, 194, 130, 64, A1); t(X + 335, 232, 'ANE1', 'h2', 'mid')
arr(f'M{X + 180} 83 H{X + 222} V114 H{X + 266}'); a(f'<path d="M{X + 180} 137 H{X + 222} V114" stroke="#48484a" stroke-width="1.5" fill="none"/>')
arr(f'M{X + 180} 191 H{X + 222} V226 H{X + 266}'); a(f'<path d="M{X + 180} 245 H{X + 222} V226" stroke="#48484a" stroke-width="1.5" fill="none"/>')
box(X + 490, 128, 140, 84, NEU); t(X + 560, 162, '输入', 'h2', 'mid'); t(X + 560, 186, '（完整一份）', 'c', 'mid')
a(f'<path d="M{X + 490} 170 H{X + 445}" stroke="#48484a" stroke-width="1.5" fill="none"/>'); arr(f'M{X + 445} 170 V114 H{X + 404}'); arr(f'M{X + 445} 170 V226 H{X + 404}')
t(X, 330, '把单 ANE 程序中已有的各趟平均分给两个 ANE，每个 ANE 只读一半权重，', 'c')
t(X, 350, '不需要拷贝与合并。只在各趟大小相同时可用（如 3×3 的 32 + 224 通道就不行）。', 'c')

# ======== ③ 数据交换与同步 ========
y0 = 420
t(40, y0, '③ 需要交换数据时：共享暂存区与同步记录（3 层 3×3 卷积，按行切分）', 'h')
r0, r1 = y0 + 30, y0 + 170
t(92, r0 + 26, 'ANE0', 'h2', 'end'); t(92, r1 + 26, 'ANE1', 'h2', 'end')
L = [(110, 300), (370, 560), (630, 820)]
for k, (x1, x2) in enumerate(L):
    box(x1, r0, x2 - x1, 40, A0, rx=4); t((x1 + x2) / 2, r0 + 26, f'第 {k + 1} 层', 'b', 'mid')
    box(x1, r1, x2 - x1, 40, A1, rx=4); t((x1 + x2) / 2, r1 + 26, f'第 {k + 1} 层', 'b', 'mid')
box(110, r0 + 66, 710, 38, ('#f5f0eb', '#7e6148'), rx=6)
t(465, r0 + 91, '共享暂存区：两个 ANE 都映射；推测经系统级缓存交换（DSID 标签）', 'c', 'mid')
for k, xs in enumerate([335, 595]):
    a(f'<path d="M{xs} {r0 + 40} V{r1}" stroke="#7e6148" stroke-width="1.6" stroke-dasharray="4 3" fill="none"/>')
    for yy in (r0 + 20, r1 + 20):
        a(f'<path d="M{xs} {yy - 9} l9 9 l-9 9 l-9 -9 z" fill="#7e6148"/>')
    t(xs, r1 + 64, f'同步 {k + 1}', 'c', 'mid')
t(110, r1 + 90, '◆ 同步记录 f0003281：第 2、3 层开始前各一次，获取对方计算的边界行；第 1 层直接从 DRAM 读取带重叠行的输入。', 'c')
t(110, r1 + 110, '1×1 卷积链两半互不依赖，没有同步记录；softmax（沿宽度）1 次；reduce_sum（沿高度）以分阶段结束的方式等待。', 'c')

# ======== ④ 切分判据 ========
X = 900
t(X, y0, '④ 是否切分：编译器比较两种延迟估计', 'h')
GR = ('#ececee', '#8e8e93'); OR = ('#f5f0eb', '#7e6148')
px = 1.0
# 单 ANE
L0 = X + 100
t(X, y0 + 44, '单 ANE', 'h2')
box(L0, y0 + 26, 240, 28, GR, rx=3); t(L0 + 120, y0 + 45, 'Σ 切分前延迟', 'c', 'mid')
# 双 ANE：各块 + 拷贝合并，再乘 0.5
t(X, y0 + 98, '双 ANE', 'h2')
box(L0, y0 + 80, 260, 28, A0, rx=3); t(L0 + 130, y0 + 99, 'Σ 切分后各块的延迟', 'c', 'mid')
box(L0 + 260, y0 + 80, 64, 28, OR, rx=3); t(L0 + 292, y0 + 99, '拷贝合并', 'c', 'mid')
arr(f'M{L0 + 162} {y0 + 110} V{y0 + 132}')
t(L0 + 172, y0 + 126, '× 0.5', 'b')
box(L0, y0 + 134, 162, 28, A0, rx=3); t(L0 + 81, y0 + 153, '切分后的估计', 'c', 'mid')
# 比较两条横条的末端
for xx in (L0 + 240, L0 + 162):
    a(f'<line x1="{xx}" y1="{y0 + 54}" x2="{xx}" y2="{y0 + 190}" stroke="#aeaeb2" stroke-width="1.2" stroke-dasharray="3 3"/>')
a(f'<path d="M{L0 + 166} {y0 + 182} H{L0 + 236}" stroke="#dc3a26" stroke-width="1.6" fill="none" marker-end="url(#ar)" marker-start="url(#ar)"/>')
t(L0 + 250, y0 + 187, '切分后的估计更短 → 切分', 'b')
t(X, y0 + 216, '0.5 意味着假设两个 ANE 完全并行、互不干扰。', 'c')
# 说明
t(X, y0 + 240, '模型没有考虑两个 ANE 对 DRAM 带宽的争用，读权重受限的层', 'c')
t(X, y0 + 260, '因此被切分却不加速（缺陷 B9）。拷贝合并一项只在每块 ≤ 128', 'c')
t(X, y0 + 280, '个像素时显著；每块过小、没有可用切法或输入只有一行时不切分。', 'c')
a('</svg>')
open(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'figs', 'fig5-3_bonded.svg'), 'w').write('\n'.join(o))
