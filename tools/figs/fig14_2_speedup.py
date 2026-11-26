#!/usr/bin/env python3
# 图 14-2（第 14.6 节）：各项实际任务在 ANE 上的 M6 ÷ M4 加速比（统一样式见 plotfig.py）。
# 数据：第 14 章整机测评记录（表 14-1、表 14-4）。
from plotfig import Plot, K, AXIS, SUB, C_BLUE, C_GREEN, C_ORANGE, C_GREY

ROWS = [
    ('文字检测 (CRAFT)', 2.69, C_BLUE),
    ('ResNet-50（一次 16 张）', 2.33, C_BLUE),
    ('LLM 解码（标准模型）', 1.86, C_GREEN),
    ('LLM 预填充（标准模型）', 1.83, C_BLUE),
    ('ResNet-50（一次 1 张）', 1.42, C_ORANGE),
    ('文字识别（含 CPU LSTM）', 1.41, C_GREY),
]

X0, AW, Y0 = 232, 544, 54
RH, BH = 38, 22
H_PLOT = len(ROWS) * RH  # 228

p = Plot(800, 392)
p.panel(4, 8, 792, 338)

ax = p.axes(x=X0, y=Y0, w=AW, h=H_PLOT, xr=(0, 3), yr=(0, 1),
            xticks=[0, 0.5, 1, 1.5, 2, 2.5, 3],
            xticklabels=['0', '0.5×', '1×', '1.5×', '2×', '2.5×', '3×'],
            yticks=[], xgrid=True, ygrid=False,
            xlabel='M6 ÷ M4（ANE 加速比）')

# 单 / 双引擎峰值参照线（字号 13 px，居中不碰撞）
for v, lab in ((1.1, '单引擎峰值 ≈ 1.1×'), (2.2, '双引擎峰值 ≈ 2.2×')):
    xx = ax.X(v)
    p.raw(f'<line x1="{xx:.1f}" y1="{Y0 - 6}" x2="{xx:.1f}" y2="{Y0 + H_PLOT}" '
          f'stroke="#666666" stroke-width="1.2" stroke-dasharray="5 4"/>')
    p.text(xx, Y0 - 15, lab, 13, SUB, 'middle', 600)

for i, (lab, val, (s, f)) in enumerate(ROWS):
    yc = Y0 + i * RH + RH / 2
    p.text(X0 - 12, yc + 4.5, lab, 13.5, K, 'end', 400)
    bw = ax.X(val) - ax.X(0)
    p.raw(f'<rect x="{ax.X(0):.1f}" y="{yc - BH / 2:.1f}" width="{bw:.1f}" height="{BH}" '
          f'fill="{f}" stroke="{AXIS}" stroke-width="0.9"/>')
    p.text(ax.X(val) + 8, yc + 4.5, f'{val:.2f}×', 13.5, s, 'start', 600)

# 底部白底居中单行图例
ly = 370
leg = [
    (C_BLUE, '计算密集'),
    (C_GREEN, '读权重 / 调用受限'),
    (C_ORANGE, '工作量小'),
    (C_GREY, '含 CPU 运算'),
]
parts = []
for (_, f), lb in leg:
    ic = f'<svg xmlns="http://www.w3.org/2000/svg" width="16" height="14" viewBox="0 0 16 14"><rect x="1" y="2" width="14" height="10" rx="1.5" fill="{f}" stroke="{AXIS}" stroke-width="1"/></svg>'
    parts.append(f'<span style="display:flex;align-items:center;gap:6px">{ic}<span>{lb}</span></span>')
p.raw(f'<foreignObject x="0" y="{ly - 14}" width="800" height="28"><div xmlns="http://www.w3.org/1999/xhtml" '
      f'style="display:flex;justify-content:center;gap:30px;align-items:center;height:28px;'
      f'font-family:Arial,\'Helvetica Neue\',\'PingFang SC\',sans-serif;font-size:13px;color:{K}">'
      + ''.join(parts) + '</div></foreignObject>')

print(p.save('fig14-2_speedup'))
