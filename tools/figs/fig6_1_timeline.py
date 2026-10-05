#!/usr/bin/env python3
# 图 6-1：一次同步调用的时间线（单 ANE，1×1 卷积，512 通道，1×128；16 层与 384 层）。
# 数据：data/04_schedule/d1b_stages.txt（A 组 c512 L16、L384 各阶段的中位数）；
# "提交 ≈ 31 µs"取自"提交 → 任务结束"对计算量的线性拟合截距（30.8 µs）。
import os

SC = 2.6                     # 每微秒的像素数
X0 = 210
LANES = ['用户线程', '内核驱动', 'ANE 固件', 'ANE']
COL = {'用户线程': ('#eef2f8', '#5b6b8c'), '内核驱动': ('#e3e8f1', '#5b6b8c'),
       'ANE 固件': ('#ececee', '#6e6e73'), 'ANE': ('#e7eaf3', '#3c5488')}
EVENTS = [('01a9', '驱动收到提交'), ('0126', 'ANE 任务结束'), ('00b8', '固件发出消息'), ('0020', '中断处理'),
          ('00a0', '完成标记'), ('0170', '驱动完成处理结束'), ('0024', '用户线程返回'), ('01a9', '下一次提交')]

CASES = [
    ('16 层：任务约 49 µs，每次调用 227 µs', 30.8, 80.2 - 30.8, [7.4, 22.3, 7.5, 20.9, 81.2, 7.0], None),
    ('384 层：任务约 1262 µs，每次调用 1618 µs', 30.8, 1292.8 - 30.8, [19.9, 17.6, 11.4, 105.5, 157.0, 7.8], 220),
]
STAGE_LANE = ['ANE 固件', '内核驱动', '内核驱动', '内核驱动', '用户线程', '用户线程']
STAGE_NAME = ['发出消息', '中断', '完成标记', '驱动完成处理', '用户线程返回', '提交']

o = []
a = o.append
W, H = 1440, 690
a(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" font-family="PingFang SC, Helvetica Neue, Arial, sans-serif">')
a('<style>text{fill:#1d1d1f} .h{font-size:18px;font-weight:600} .b{font-size:14px;fill:#3a3a3c} .c{font-size:12.5px;fill:#6e6e73}'
  ' .m{font-size:11px;font-family:Menlo,SF Mono,monospace;fill:#ffffff} .mid{text-anchor:middle} .end{text-anchor:end}</style>')


def textw(s):
    return sum(12.5 if ord(ch) > 0x2e80 else 7 for ch in s)


def lane_y(top, name):
    return top + 30 + LANES.index(name) * 40


def seg(top, lane, t0, w_px, label=None, dashed=False):
    y = lane_y(top, lane)
    f, s = COL[lane]
    x = X0 + t0
    a(f'<rect x="{x:.1f}" y="{y}" width="{w_px:.1f}" height="26" rx="3" fill="{f}" stroke="{s}" stroke-width="1.3"'
      + (' stroke-dasharray="4 3"' if dashed else '') + '/>')
    if label:
        for lab in label if isinstance(label, list) else [label]:
            if textw(lab) + 10 <= w_px:
                a(f'<text class="c mid" x="{x + w_px / 2:.1f}" y="{y + 18}">{lab}</text>')
                break


def event(top, xpx, k):
    a(f'<line x1="{X0 + xpx:.1f}" y1="{top + 22}" x2="{X0 + xpx:.1f}" y2="{top + 30 + 4 * 40 - 8}" stroke="#aeaeb2" stroke-width="1" stroke-dasharray="2 3"/>')
    a(f'<circle cx="{X0 + xpx:.1f}" cy="{top + 12}" r="9" fill="#48484a"/>')
    a(f'<text class="m mid" x="{X0 + xpx:.1f}" y="{top + 16}">{k}</text>')


top = 40
for title, sub, task, stages, brk in CASES:
    a(f'<text class="h" x="40" y="{top - 6}">{title}</text>')
    top += 18
    for ln in LANES:
        a(f'<text class="b end" x="{X0 - 16}" y="{lane_y(top, ln) + 18}">{ln}</text>')
        a(f'<line x1="{X0}" y1="{lane_y(top, ln) + 13}" x2="{W - 40}" y2="{lane_y(top, ln) + 13}" stroke="#ececee" stroke-width="1"/>')
    t = 0.0
    event(top, t, 1)
    seg(top, '内核驱动', t, sub * SC, ['提交 ≈ 31 µs', '提交 ≈ 31'], dashed=True); t += sub * SC
    tw = brk if brk else task * SC
    seg(top, 'ANE', t, tw, f'ANE 任务 {task:.0f} µs' if not brk else '')
    if brk:
        xm = X0 + t + tw / 2
        a(f'<rect x="{xm - 10:.1f}" y="{lane_y(top, "ANE") - 2}" width="20" height="30" fill="#ffffff"/>')
        for dx in (-6, 4):
            a(f'<path d="M{xm + dx:.1f} {lane_y(top, "ANE") - 4} l6 34" stroke="#3c5488" stroke-width="1.5"/>')
        a(f'<text class="c mid" x="{X0 + t + tw / 4:.1f}" y="{lane_y(top, "ANE") + 18}">ANE 任务</text>')
        a(f'<text class="c mid" x="{X0 + t + 3 * tw / 4:.1f}" y="{lane_y(top, "ANE") + 18}">{task:.0f} µs</text>')
    t += tw
    event(top, t, 2)
    for i, (d, ln) in enumerate(zip(stages, STAGE_LANE)):
        seg(top, ln, t, d * SC, [f'{STAGE_NAME[i]} {d:.0f} µs', f'{STAGE_NAME[i]} {d:.0f}', f'{d:.0f}'])
        t += d * SC
        event(top, t, i + 3)
    total_after = sum(stages)
    # 任务结束之后的总开销
    x1 = X0 + (sub * SC + tw)
    x2 = X0 + t
    yb = top + 30 + 4 * 40 + 2
    a(f'<path d="M{x1:.1f} {yb} v6 H{x2:.1f} v-6" stroke="#48484a" stroke-width="1.2" fill="none"/>')
    a(f'<text class="b mid" x="{(x1 + x2) / 2:.1f}" y="{yb + 24}">任务结束之后 {total_after:.0f} µs（驱动完成处理 {stages[3]:.0f} µs，用户线程返回 {stages[4]:.0f} µs）</text>')
    top += 30 + 4 * 40 + 70

# 事件说明
y = top + 4
a(f'<text class="h" x="40" y="{y}">kdebug 事件（类 0x06，子类 0x1b；表 6-1）</text>')
for i, (eid, name) in enumerate(EVENTS):
    cx = 52 + (i % 4) * 340
    cy = y + 30 + (i // 4) * 30
    a(f'<circle cx="{cx}" cy="{cy - 5}" r="9" fill="#48484a"/><text class="m mid" x="{cx}" y="{cy - 1}">{i + 1}</text>')
    a(f'<text class="b" x="{cx + 18}" y="{cy}"><tspan font-family="Menlo, SF Mono, monospace">61b{eid}</tspan>　{name}</text>')
a('</svg>')

out = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'figs', 'fig6-1_call_timeline.svg')
open(out, 'w').write('\n'.join(o))
