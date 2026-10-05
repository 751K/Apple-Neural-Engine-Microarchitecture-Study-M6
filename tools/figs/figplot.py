# 数据图共用的坐标轴与绘图辅助：手写 SVG，配色与字体同示意图（浅色，fig10_2_split.py 等）。
# 用法：
#   c = Chart(W=1000, H=520, title='…', sub='…')
#   ax = c.axes(x=90, y=80, w=820, h=360, xr=(0, 400), yr=(0, 1.6), xlabel='层数', ylabel='耗时（ms）',
#               xticks=[0, 100, 200], yticks=[0, 0.5, 1.0], xlog=False, ylog=False)
#   ax.line(xs, ys, color=0, marker=True, label='单 ANE')
#   ax.bars(xs, ys, color=1, width=10); ax.text(x, y, '…'); ax.vline(x, '…')
#   c.legend(x, y); c.save('fig7-1_ocg_step')   # 写 figs/<name>.svg，再用 render.sh 导出 PNG
import math
import os

FG, FG2, FG3, GRID, AXIS = '#1d1d1f', '#3a3a3c', '#6e6e73', '#e5e5ea', '#8e8e93'
# 系列颜色（描边, 浅填充）：紫（ANE0 / M6）、蓝（ANE1 / 对照）、橙（强调）、绿、红、灰
COLORS = [('#3c5488', '#e7eaf3'), ('#00a087', '#e3f4f0'), ('#7e6148', '#efe8e1'),
          ('#2f9ab5', '#e1f3f8'), ('#e64b35', '#fbe3df'), ('#6e6e73', '#ececee')]
FIGS = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'figs')


def fmt(v):
    if isinstance(v, str):
        return v
    if abs(v - round(v)) < 1e-9:
        return str(int(round(v)))
    return f'{v:g}'


class Axes:
    def __init__(self, c, x, y, w, h, xr, yr, xlog=False, ylog=False):
        self.c, self.x, self.y, self.w, self.h = c, x, y, w, h
        self.xr, self.yr, self.xlog, self.ylog = xr, yr, xlog, ylog

    def _m(self, v, r, log):
        if log:
            return (math.log10(v) - math.log10(r[0])) / (math.log10(r[1]) - math.log10(r[0]))
        return (v - r[0]) / (r[1] - r[0])

    def X(self, v):
        return self.x + self._m(v, self.xr, self.xlog) * self.w

    def Y(self, v):
        return self.y + self.h - self._m(v, self.yr, self.ylog) * self.h

    def line(self, xs, ys, color=0, marker=True, label=None, dash=False, width=2.2, r=3.6, step=False):
        s, f = COLORS[color] if isinstance(color, int) else color
        pts = [(self.X(a), self.Y(b)) for a, b in zip(xs, ys)]
        if step:
            p2 = [pts[0]]
            for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
                p2 += [(x1, y0), (x1, y1)]
            d = 'M' + ' L'.join(f'{a:.1f} {b:.1f}' for a, b in p2)
        else:
            d = 'M' + ' L'.join(f'{a:.1f} {b:.1f}' for a, b in pts)
        self.c.a(f'<path d="{d}" fill="none" stroke="{s}" stroke-width="{width}" stroke-linejoin="round"'
                 + (' stroke-dasharray="6 4"' if dash else '') + '/>')
        if marker:
            for a, b in pts:
                self.c.a(f'<circle cx="{a:.1f}" cy="{b:.1f}" r="{r}" fill="#ffffff" stroke="{s}" stroke-width="1.8"/>')
        if label:
            self.c.leg.append((label, s, 'line', dash))

    def scatter(self, xs, ys, color=0, r=2.2, label=None, op=0.6):
        s, f = COLORS[color] if isinstance(color, int) else color
        for a, b in zip(xs, ys):
            self.c.a(f'<circle cx="{self.X(a):.1f}" cy="{self.Y(b):.1f}" r="{r}" fill="{s}" opacity="{op}"/>')
        if label:
            self.c.leg.append((label, s, 'dot', False))

    def bars(self, xs, ys, color=0, width=20, label=None, base=None, offset=0):
        s, f = COLORS[color] if isinstance(color, int) else color
        b0 = self.yr[0] if base is None else base
        for a, b in zip(xs, ys):
            x = self.X(a) + offset - width / 2
            y1, y0 = self.Y(b), self.Y(b0)
            self.c.a(f'<rect x="{x:.1f}" y="{min(y0, y1):.1f}" width="{width}" height="{abs(y0 - y1):.1f}" fill="{f}" stroke="{s}" stroke-width="1.3"/>')
        if label:
            self.c.leg.append((label, s, 'box', f))

    def hbar(self, x0, x1, yc, h, color=0, text=None):
        s, f = COLORS[color] if isinstance(color, int) else color
        self.c.a(f'<rect x="{self.X(x0):.1f}" y="{yc - h / 2:.1f}" width="{self.X(x1) - self.X(x0):.1f}" height="{h}" fill="{f}" stroke="{s}" stroke-width="1.3"/>')
        if text:
            self.c.t((self.X(x0) + self.X(x1)) / 2, yc + 5, text, 's', 'middle')

    def vline(self, v, text=None, color=AXIS, dash=True, ty=None):
        x = self.X(v)
        self.c.a(f'<line x1="{x:.1f}" y1="{self.y}" x2="{x:.1f}" y2="{self.y + self.h}" stroke="{color}" stroke-width="1.2"'
                 + (' stroke-dasharray="4 4"' if dash else '') + '/>')
        if text:
            self.c.t(x + 6, ty if ty is not None else self.y + 16, text, 'c')

    def hline(self, v, text=None, color=AXIS, dash=True, anchor='end'):
        y = self.Y(v)
        self.c.a(f'<line x1="{self.x}" y1="{y:.1f}" x2="{self.x + self.w}" y2="{y:.1f}" stroke="{color}" stroke-width="1.2"'
                 + (' stroke-dasharray="4 4"' if dash else '') + '/>')
        if text:
            tx = self.x + self.w - 6 if anchor == 'end' else self.x + 6
            self.c.t(tx, y - 6, text, 'c', anchor)

    def text(self, vx, vy, s, cls='c', anchor='start', dx=0, dy=0, col=None):
        self.c.t(self.X(vx) + dx, self.Y(vy) + dy, s, cls, anchor, col)

    def arrow(self, v0, v1, color=FG2):
        (x0, y0), (x1, y1) = v0, v1
        self.c.a(f'<path d="M{self.X(x0):.1f} {self.Y(y0):.1f} L{self.X(x1):.1f} {self.Y(y1):.1f}" stroke="{color}" stroke-width="1.4" fill="none" marker-end="url(#a)"/>')


class Chart:
    def __init__(self, W, H, title=None, sub=None):
        self.W, self.H, self.o, self.leg = W, H, [], []
        self.a = self.o.append
        self.a(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" font-family="PingFang SC, Helvetica Neue, Arial, sans-serif">')
        self.a(f'<style>text{{fill:{FG}}} .h{{font-size:18px;font-weight:600}} .h2{{font-size:15.5px;font-weight:600}}'
               f' .b{{font-size:14.5px;fill:{FG2}}} .c{{font-size:13px;fill:{FG3}}} .s{{font-size:12.5px;fill:{FG2}}}'
               f' .tk{{font-size:12.5px;fill:{FG3};font-family:Helvetica Neue,Arial,sans-serif}}</style>')
        self.a(f'<defs><marker id="a" markerWidth="10" markerHeight="10" refX="8" refY="5" orient="auto">'
               f'<path d="M0,1 L9,5 L0,9" fill="none" stroke="{FG2}" stroke-width="1.6"/></marker></defs>')
        if title:
            self.t(40, 32, title, 'h')
        if sub:
            self.t(40, 54, sub, 'c')

    def t(self, x, y, s, cls='b', anchor='start', col=None):
        self.a(f'<text class="{cls}" x="{x:.1f}" y="{y:.1f}" text-anchor="{anchor}"' + (f' fill="{col}"' if col else '') + f'>{s}</text>')

    def axes(self, x, y, w, h, xr, yr, xlabel=None, ylabel=None, xticks=(), yticks=(), xlog=False, ylog=False,
             xticklabels=None, yticklabels=None, grid=True, title=None):
        ax = Axes(self, x, y, w, h, xr, yr, xlog, ylog)
        if title:
            self.t(x, y - 12, title, 'h2')
        for i, v in enumerate(yticks):
            yy = ax.Y(v)
            if grid:
                self.a(f'<line x1="{x}" y1="{yy:.1f}" x2="{x + w}" y2="{yy:.1f}" stroke="{GRID}" stroke-width="1"/>')
            self.t(x - 8, yy + 4.5, yticklabels[i] if yticklabels else fmt(v), 'tk', 'end')
        for i, v in enumerate(xticks):
            xx = ax.X(v)
            self.a(f'<line x1="{xx:.1f}" y1="{y + h}" x2="{xx:.1f}" y2="{y + h + 5}" stroke="{AXIS}" stroke-width="1"/>')
            self.t(xx, y + h + 20, xticklabels[i] if xticklabels else fmt(v), 'tk', 'middle')
        self.a(f'<line x1="{x}" y1="{y + h}" x2="{x + w}" y2="{y + h}" stroke="{AXIS}" stroke-width="1.2"/>')
        self.a(f'<line x1="{x}" y1="{y}" x2="{x}" y2="{y + h}" stroke="{AXIS}" stroke-width="1.2"/>')
        if xlabel:
            self.t(x + w / 2, y + h + 44, xlabel, 's', 'middle')
        if ylabel:
            self.a(f'<text class="s" x="{x - 54}" y="{y + h / 2:.1f}" text-anchor="middle" transform="rotate(-90 {x - 54} {y + h / 2:.1f})">{ylabel}</text>')
        return ax

    def legend(self, x, y, dx=None, dy=22, cols=1):
        for i, (lab, s, kind, extra) in enumerate(self.leg):
            cx = x + (i % cols) * (dx or 200)
            cy = y + (i // cols) * dy
            if kind == 'line':
                self.a(f'<line x1="{cx}" y1="{cy - 4}" x2="{cx + 26}" y2="{cy - 4}" stroke="{s}" stroke-width="2.2"'
                       + (' stroke-dasharray="6 4"' if extra else '') + '/>')
                self.a(f'<circle cx="{cx + 13}" cy="{cy - 4}" r="3.6" fill="#ffffff" stroke="{s}" stroke-width="1.8"/>')
            elif kind == 'dot':
                self.a(f'<circle cx="{cx + 13}" cy="{cy - 4}" r="3.5" fill="{s}"/>')
            else:
                self.a(f'<rect x="{cx + 5}" y="{cy - 11}" width="16" height="14" rx="2" fill="{extra}" stroke="{s}" stroke-width="1.3"/>')
            self.t(cx + 34, cy + 1, lab, 's')

    def save(self, name):
        p = os.path.join(FIGS, name + '.svg')
        open(p, 'w').write('\n'.join(self.o + ['</svg>']))
        print(p)
