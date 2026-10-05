#!/usr/bin/env python3
# 第 5.5 节示意图：权重按输出通道分给 16 个 NE；每 NE 超过 64 KiB 时拆成多个 TD。
# 左：基准模型（64 → 64 通道，1×1）的 __KERN_0 切分；右：256 通道 1×9 卷积（16×32 输入）的 3 个 TD（64 + 96 + 96）。
# 每 NE 权重按"权重段字节数 ÷ 输出通道数 × 每 NE 通道数"估算：256 × 19.27 × 2 B ≈ 9.6 KiB / 输出通道。
import os
o = []
a = o.append
W, H = 1440, 600
a(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" font-family="PingFang SC, Helvetica Neue, Arial, sans-serif">')
a('<style>text{fill:#1d1d1f} .h{font-size:18px;font-weight:600} .b{font-size:14.5px;fill:#3a3a3c} .c{font-size:13px;fill:#6e6e73}'
  ' .s{font-size:12px;fill:#3a3a3c} .m{font-size:12.5px;font-family:Menlo,SF Mono,monospace;fill:#3a3a3c} .mid{text-anchor:middle} .end{text-anchor:end}</style>')
a('<defs><marker id="ar" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">'
  '<path d="M0,0 L10,5 L0,10 z" fill="#48484a"/></marker></defs>')


def t(x, y, s, c='b', anc=''):
    a(f'<text class="{c}{" " + anc if anc else ""}" x="{x}" y="{y}">{s}</text>')


C1, C2 = '#c3cbe0', '#c8e9e1'
# ---------------- 左：按输出通道分给 16 个 NE ----------------
t(40, 34, '① 一层的权重按输出通道均分给 16 个 NE', 'h')
t(40, 58, '基准模型：1×1 卷积，64 个输入通道 → 64 个输出通道（FP16）', 'c')
y0, bh = 96, 28.5                     # 16 行铺满到 552，与右栏底部对齐
t(180, y0 - 12, '权重（每行 = 一个输出通道）', 'c', 'mid')
for i in range(16):
    y = y0 + i * bh
    col = C1 if i % 2 == 0 else C2
    a(f'<rect x="120" y="{y}" width="120" height="{bh}" fill="{col}" stroke="#ffffff" stroke-width="1"/>')
    for r in range(1, 4):
        a(f'<line x1="120" y1="{y + r * bh / 4}" x2="240" y2="{y + r * bh / 4}" stroke="#ffffff" stroke-width="0.6"/>')
    a(f'<path d="M240 {y + bh / 2} H296" stroke="#48484a" stroke-width="1.2" fill="none" marker-end="url(#ar)"/>')
    a(f'<rect x="300" y="{y + 2}" width="200" height="{bh - 4}" rx="4" fill="#e7eaf3" stroke="#3c5488" stroke-width="1.1"/>')
    t(312, y + bh / 2 + 4.5, f'NE{i}', 's'); t(490, y + bh / 2 + 4.5, f'通道 {4 * i}–{4 * i + 3}', 's', 'end')
a(f'<rect x="120" y="{y0}" width="120" height="{16 * bh}" fill="none" stroke="#8e8e93" stroke-width="1.2"/>')
a(f'<text class="c mid" x="92" y="{y0 + 8 * bh}" transform="rotate(-90 92 {y0 + 8 * bh})">输出通道 0–63</text>')
# 说明
a(f'<path d="M512 {y0} h8 v{16 * bh} h-8" stroke="#48484a" stroke-width="1.2" fill="none"/>')
mid = y0 + 8 * bh
t(534, mid - 42, '每个 NE 4 个输出通道', 'b')
t(534, mid - 16, '每块 576 字节（0x240）：', 'b')
t(534, mid + 8, '4 × 64 × 2 B = 512 B，', 'c')
t(534, mid + 30, '加偏置与对齐', 'c')
t(534, mid + 62, '编译产物中为 16 个符号', 'c')
t(534, mid + 84, 'K…_ne_0 … K…_ne_15', 'm')

# ---------------- 右：超过 64 KiB 时拆成多个 TD ----------------
X = 760
t(X, 34, '② 每个 NE 的权重超过 64 KiB 时，按输出通道拆成多个 TD', 'h')
t(X, 58, '256 通道的 1×9 卷积（改写后约 19.3 个抽头），16×32 输入', 'c')
# 每 NE 需要的权重 vs 上限
sc = 3.4                                   # px / KiB
t(X, 98, '每个 NE 需要的权重', 'b')
a(f'<rect x="{X}" y="108" width="{154 * sc:.0f}" height="26" rx="4" fill="#c8e9e1" stroke="#00a087" stroke-width="1.2"/>')
t(X + (64 + 154) * sc / 2, 126, '≈ 154 KiB（16 个输出通道 × 9.6 KiB）', 's', 'mid')
a(f'<line x1="{X + 64 * sc:.0f}" y1="100" x2="{X + 64 * sc:.0f}" y2="142" stroke="#dc3a26" stroke-width="2" stroke-dasharray="4 3"/>')
t(X + 64 * sc + 6, 156, '64 KiB 常驻上限', 'c')
t(X + 64 * sc + 6, 156, '', 'c')
# 输出通道轴，按 64 / 96 / 96 切分
y = 196
t(X, y - 10, '输出通道 0–255', 'c')
segs = [(64, 'TD0', 0), (96, 'TD1', 64), (96, 'TD2', 160)]
L = 640
x = X
for n, name, start in segs:
    w = L * n / 256
    a(f'<rect x="{x:.1f}" y="{y}" width="{w:.1f}" height="30" fill="#e7eaf3" stroke="#3c5488" stroke-width="1.3"/>')
    t(x + w / 2, y + 20, f'{start}–{start + n - 1}', 's', 'mid')
    # 下方 TD 卡片（等宽，与通道段用箭头连接）
    idx = [g[1] for g in segs].index(name)
    cx0 = X + idx * 216
    cy = y + 76
    # 箭头从通道段中点竖直向下（三个中点都落在对应卡片的宽度内）
    a(f'<path d="M{x + w / 2:.1f} {y + 30} V{cy - 4}" stroke="#48484a" stroke-width="1.3" fill="none" marker-end="url(#ar)"/>')
    a(f'<rect x="{cx0}" y="{cy}" width="204" height="150" rx="8" fill="#ffffff" stroke="#3c5488" stroke-width="1.3"/>')
    t(cx0 + 14, cy + 26, f'{name}：{n} 个输出通道', 'b')
    t(cx0 + 14, cy + 50, f'每个 NE {n // 16} 个通道', 'c')
    kib = n // 16 * 9.63
    bw = 176
    a(f'<rect x="{cx0 + 14}" y="{cy + 66}" width="{bw}" height="20" rx="3" fill="#ffffff" stroke="#dc3a26" stroke-width="1" stroke-dasharray="3 2"/>')
    a(f'<rect x="{cx0 + 14}" y="{cy + 66}" width="{bw * kib / 64:.1f}" height="20" rx="3" fill="#c8e9e1" stroke="#00a087" stroke-width="1"/>')
    t(cx0 + 14, cy + 106, f'每 NE ≈ {kib:.0f} KiB（上限 64）', 'c')
    t(cx0 + 14, cy + 130, f'exe_cycles = {[7, 11, 11][idx]}', 'm')
    x += w
t(X, 458, 'TD 数 = ⌈154 ÷ 64⌉ = 3；三个 TD 的 exe_cycles 与输出通道数成正比。', 'c')

# 底部：小输入的例外
a(f'<rect x="{X}" y="482" width="{L}" height="70" rx="8" fill="#f5f5f7" stroke="#aeaeb2" stroke-width="1.1"/>')
t(X + 16, 508, '例外：输入较小时（4×32 的全部卷积核、8×32 的改写核）', 'b')
t(X + 16, 534, '全部 256 个输出通道放在一个 TD 中，执行时连续读入权重', 'c')
a('</svg>')
open(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'figs', 'fig5-1_weight_split.svg'), 'w').write('\n'.join(o))
