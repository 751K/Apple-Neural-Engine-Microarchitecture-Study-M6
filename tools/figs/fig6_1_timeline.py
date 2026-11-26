#!/usr/bin/env python3
# 图 6-1：一次同步调用的时间线（正式科研论文时间轴样式，极简标注，对齐 archfig.py 配色）。
# 图契约：
#   核心结论：任务变长后（16 层 → 384 层），提交不变（≈31 µs），任务结束后的开销从 146 µs 增至 319 µs，
#             增长集中在驱动完成处理（21 → 106 µs）与用户线程返回（81 → 157 µs）。
#   图原型：上下两张泳道时间线以 t = 0（任务结束）对齐，右侧共用 µs 定量横轴与淡网格；
#           方框内只标关键数值，不重复泳道名，不加编号圆点与事件表。
#   能不能更少：去掉次要小段数字、括号总耗时与冗余文字，细节留在图注与表 6-1、表 6-2。
# 数据：data/04_schedule/d1b_stages.txt（A 组 c512 L16、L384 各阶段中位数）。
from archfig import Fig, K, SK, GREEN, WHITE, WT

HOST_HI = '#e7d9b8'                # 主机侧主要增长段（驱动完成处理、用户线程返回）
GRID = '#e6e6ea'
AXIS = '#555555'

SC = 1.42                          # px / µs（t >= 0 区域定量比例尺）
X0 = 278                           # t = 0（ANE 任务结束）对齐线
X_LEFT = 104
X_MAX = X0 + 350 * SC              # 350 µs = 775 px

LANES = ['用户线程', '内核驱动', 'ANE 固件', 'ANE']
STAGE_LANE = ['ANE 固件', '内核驱动', '内核驱动', '内核驱动', '用户线程', '用户线程']

CASES = [
    ('(a) 16 层', 30.8, 49.4, [7.4, 22.3, 7.5, 20.9, 81.2, 7.0], None),
    ('(b) 384 层', 30.8, 1262.0, [19.9, 17.6, 11.4, 105.5, 157.0, 7.8], 122.0),
]

f = Fig(800, 404)
T, R = f.text, f.rect

LANE_DY = 28
BAR_H = 20

Y_TOP1, Y_TOP2 = 38, 202
Y_BOT1 = Y_TOP1 + 4 * LANE_DY
Y_BOT2 = Y_TOP2 + 4 * LANE_DY
Y_AXIS = Y_BOT2 + 10

# 定量时间网格
for tick in (50, 100, 150, 200, 250, 300, 350):
    gx = X0 + tick * SC
    f.raw(f'<line x1="{gx:.1f}" y1="{Y_TOP1 - 4}" x2="{gx:.1f}" y2="{Y_BOT1 + 2}" stroke="{GRID}" stroke-width="0.9"/>')
    f.raw(f'<line x1="{gx:.1f}" y1="{Y_TOP2 - 4}" x2="{gx:.1f}" y2="{Y_AXIS}" stroke="{GRID}" stroke-width="0.9"/>')

# 面板分隔细线
f.raw(f'<line x1="12" y1="164" x2="{X_MAX:.1f}" y2="164" stroke="#dcdce0" stroke-width="1"/>')

# t = 0 对齐基准虚线
f.raw(f'<line x1="{X0}" y1="{Y_TOP1 - 8}" x2="{X0}" y2="{Y_AXIS}" stroke="{AXIS}" stroke-width="1.2" stroke-dasharray="4 3"/>')
T(X0, 22, 't = 0', 13.5, AXIS, 'middle', 600)


def draw_case(y_top, title, sub, task, stages, brk):
    T(12, y_top - 15, title, 15, K, 'start', 600)

    # 4 条泳道标签与细参考线
    for i, ln in enumerate(LANES):
        yc = y_top + i * LANE_DY + LANE_DY / 2
        T(X_LEFT - 10, yc + 4.5, ln, 13.5, K, 'end', 400)
        f.raw(f'<line x1="{X_LEFT}" y1="{yc}" x2="{X_MAX:.1f}" y2="{yc}" stroke="#efefef" stroke-width="1"/>')

    def seg(lane, x_abs, w, fill, label='', dashed=False):
        yc = y_top + LANES.index(lane) * LANE_DY + LANE_DY / 2
        y = yc - BAR_H / 2
        ex = ' stroke-dasharray="4 3"' if dashed else ''
        R(x_abs, y, w, BAR_H, fill, sw=0.85, extra=ex)
        if label:
            T(x_abs + w / 2, yc + 4.5, label, 13, K, 'middle', 600)

    # t <= 0：提交与 ANE 任务
    tw = brk if brk else task * SC
    x_ane = X0 - tw
    x_sub = x_ane - sub * SC
    seg('内核驱动', x_sub, sub * SC, WHITE, '≈31', dashed=True)

    if brk:
        yc = y_top + 3 * LANE_DY + LANE_DY / 2
        y = yc - BAR_H / 2
        R(x_ane, y, tw, BAR_H, GREEN, sw=0.85)
        bx = x_ane + 26
        f.raw(f'<rect x="{bx - 4}" y="{y - 1}" width="8" height="{BAR_H + 2}" fill="#ffffff"/>')
        for dx in (-3.5, 3.0):
            f.raw(f'<line x1="{bx + dx - 2.5}" y1="{y + BAR_H + 2}" x2="{bx + dx + 2.5}" y2="{y - 2}" stroke="{SK}" stroke-width="1.2"/>')
        T(x_ane + 33 + (tw - 33) / 2, yc + 4.5, f'{task:.0f}', 13, K, 'middle', 600)
    else:
        seg('ANE', x_ane, tw, GREEN, f'{task:.0f}')

    # t >= 0：任务结束后的各阶段（只在关键增长段标纯数字，避免视觉噪音）
    cur = float(X0)
    for i, (d, ln) in enumerate(zip(stages, STAGE_LANE)):
        w = d * SC
        is_hi = i in (3, 4)
        seg(ln, cur, w, HOST_HI if is_hi else WHITE, f'{d:.0f}' if is_hi else '')
        cur += w

    # 末端总耗时
    total_after = sum(stages)
    yc_top = y_top + LANE_DY / 2
    T(cur + 8, yc_top + 4.5, f'+{total_after:.0f} µs', 13.5, WT, 'start', 600)


draw_case(Y_TOP1, *CASES[0])
draw_case(Y_TOP2, *CASES[1])

# 底部定量横轴
f.raw(f'<line x1="{X_LEFT}" y1="{Y_AXIS}" x2="{X0}" y2="{Y_AXIS}" stroke="#d0d0d4" stroke-width="1"/>')
f.raw(f'<line x1="{X0}" y1="{Y_AXIS}" x2="{X_MAX:.1f}" y2="{Y_AXIS}" stroke="{AXIS}" stroke-width="1.2"/>')
for tick in (0, 50, 100, 150, 200, 250, 300, 350):
    tx = X0 + tick * SC
    f.raw(f'<line x1="{tx:.1f}" y1="{Y_AXIS}" x2="{tx:.1f}" y2="{Y_AXIS + 5}" stroke="{AXIS}" stroke-width="1.1"/>')
    T(tx, Y_AXIS + 19, str(tick), 12.5, AXIS, 'middle', 400)
T((X0 + X_MAX) / 2, Y_AXIS + 38, '任务结束后 (µs)', 13.5, K, 'middle', 600)

# 极简单行图例
LY = 390
items = [
    (WHITE, True, '提交'),
    (GREEN, False, 'ANE 任务'),
    (HOST_HI, False, '完成 / 返回'),
    (WHITE, False, '其余'),
]
parts = []
for fill, dashed, lab in items:
    bd = f'1.1px dashed {SK}' if dashed else f'0.85px solid {SK}'
    icon = f'<span style="display:inline-block;width:24px;height:14px;box-sizing:border-box;background:{fill};border:{bd}"></span>'
    parts.append(f'<span style="display:flex;align-items:center;gap:8px">{icon}<span>{lab}</span></span>')
f.raw(f'<foreignObject x="0" y="{LY - 14}" width="800" height="28"><div xmlns="http://www.w3.org/1999/xhtml" '
      f'style="display:flex;justify-content:center;gap:48px;align-items:center;height:28px;'
      f'font-family:Arial,\'Helvetica Neue\',\'PingFang SC\',sans-serif;font-size:14px;color:{K}">'
      + ''.join(parts) + '</div></foreignObject>')

print(f.save('fig6-1_call_timeline'))
