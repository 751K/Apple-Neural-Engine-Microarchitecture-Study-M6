#!/usr/bin/env python3
# 数据图的统一绘图库（与 archfig.py 共用画幅、字体、墨色与色板，供全报告定量图表统一风格）：
#   标准宽 800 px，纯白底，深炭黑坐标轴（#2b2b2b）配向外刻度，浅灰网格（#e6e6ea），
#   字号 ≥ 13 px，配色与 archfig.py 一脉相承且全部兼容 darken.py 深色转换。
import math
import os

K = '#111111'
AXIS = '#2b2b2b'
TICK = '#333333'
SUB = '#555555'
GRID = '#e6e6ea'
PANEL = '#efefef'
FONT = 'text{font-family:Arial,"Helvetica Neue","PingFang SC",sans-serif}'
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'figs', 'zh', 'light')

# 统一色板：与 archfig.py / fig4-1 / fig4-2 完全同源（描边色与浅填充色一一对应，且兼容 darken.py 深色转换）
C_BLUE = ('#2f5f98', '#b6c9e6')      # 主系列（与 archfig.BLUE / fig4-2 LOAD 同源）
C_GREEN = ('#607e2d', '#d5e3b8')     # 对照系列（与 archfig.GREEN 同色相的深橄榄绿）
C_RED = ('#a5302e', '#f0c4bc')       # 强调 / 警示（与 archfig.WT 同源）
C_ORANGE = ('#e07b22', '#e7d9b8')    # 暖色强调（与 archfig.ACT 同源）
C_PURPLE = ('#7b4ea3', '#dfd2eb')    # 控制 / 调频（与 fig4-2 CLKC 同源）
C_GREY = ('#555555', '#d9d9d9')      # 中性 / 基线
PALETTE = [C_BLUE, C_GREEN, C_RED, C_ORANGE, C_PURPLE, C_GREY]


def _col(c):
    return PALETTE[c] if isinstance(c, int) else c


def fmt(v):
    if isinstance(v, str):
        return v
    if abs(v - round(v)) < 1e-9:
        return str(int(round(v)))
    return f'{v:g}'


class Axes:
    def __init__(self, p, x, y, w, h, xr, yr, xlog=False, ylog=False):
        self.p, self.x, self.y, self.w, self.h = p, x, y, w, h
        self.xr, self.yr, self.xlog, self.ylog = xr, yr, xlog, ylog

    def _m(self, v, r, log):
        if log:
            return (math.log10(v) - math.log10(r[0])) / (math.log10(r[1]) - math.log10(r[0]))
        return (v - r[0]) / (r[1] - r[0])

    def X(self, v):
        return self.x + self._m(v, self.xr, self.xlog) * self.w

    def Y(self, v):
        return self.y + self.h - self._m(v, self.yr, self.ylog) * self.h

    def line(self, xs, ys, color=0, marker='o', label=None, dash=None, width=2.4, r=4.2, step=False, fill_marker='#ffffff'):
        s, f = _col(color)
        pts = [(self.X(a), self.Y(b)) for a, b in zip(xs, ys)]
        if step:
            p2 = [pts[0]]
            for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
                p2 += [(x1, y0), (x1, y1)]
            d = 'M' + ' L'.join(f'{a:.1f} {b:.1f}' for a, b in p2)
        else:
            d = 'M' + ' L'.join(f'{a:.1f} {b:.1f}' for a, b in pts)
        da = f' stroke-dasharray="{dash}"' if dash else ''
        self.p.raw(f'<path d="{d}" fill="none" stroke="{s}" stroke-width="{width}" stroke-linejoin="round"{da}/>')
        if marker:
            for a, b in pts:
                self._marker(a, b, marker, s, r, fill_marker)
        if label:
            self.p.leg.append(('line', s, dash, marker, fill_marker, label))

    def _marker(self, x, y, kind, col, r=4.2, fill='#ffffff'):
        if kind == 'o':
            self.p.raw(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r}" fill="{fill}" stroke="{col}" stroke-width="2"/>')
        elif kind == 'O':
            self.p.raw(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r}" fill="{col}"/>')
        elif kind == 's':
            self.p.raw(f'<rect x="{x - r:.1f}" y="{y - r:.1f}" width="{2 * r:.1f}" height="{2 * r:.1f}" fill="{fill}" stroke="{col}" stroke-width="2"/>')
        elif kind == 'S':
            self.p.raw(f'<rect x="{x - r:.1f}" y="{y - r:.1f}" width="{2 * r:.1f}" height="{2 * r:.1f}" fill="{col}"/>')
        elif kind == 'd':
            self.p.raw(f'<path d="M{x:.1f} {y - r - 0.8:.1f} L{x + r + 0.8:.1f} {y:.1f} L{x:.1f} {y + r + 0.8:.1f} L{x - r - 0.8:.1f} {y:.1f} Z" fill="{fill}" stroke="{col}" stroke-width="1.9"/>')

    def point(self, vx, vy, color=0, marker='s', r=5.0, fill='#ffffff'):
        s, _ = _col(color)
        self._marker(self.X(vx), self.Y(vy), marker, s, r, fill)

    def scatter(self, xs, ys, color=0, r=2.6, label=None, op=0.65, hollow=False):
        s, _ = _col(color)
        for a, b in zip(xs, ys):
            if hollow:
                self.p.raw(f'<circle cx="{self.X(a):.1f}" cy="{self.Y(b):.1f}" r="{r}" fill="#ffffff" stroke="{s}" stroke-width="1.4" opacity="{op}"/>')
            else:
                self.p.raw(f'<circle cx="{self.X(a):.1f}" cy="{self.Y(b):.1f}" r="{r}" fill="{s}" opacity="{op}"/>')
        if label:
            self.p.leg.append(('dot', s, None, 'o' if hollow else 'O', '#ffffff' if hollow else s, label))

    def bars(self, xs, ys, color=0, width=28, label=None, base=None, offset=0):
        s, f = _col(color)
        b0 = self.yr[0] if base is None else base
        for a, b in zip(xs, ys):
            x = self.X(a) + offset - width / 2
            y1, y0 = self.Y(b), self.Y(b0)
            self.p.raw(f'<rect x="{x:.1f}" y="{min(y0, y1):.1f}" width="{width:.1f}" height="{abs(y0 - y1):.1f}" fill="{f}" stroke="{AXIS}" stroke-width="0.9"/>')
        if label:
            self.p.leg.append(('box', AXIS, None, None, f, label))

    def vline(self, v, color='#777777', dash='4 3', sw=1.2):
        x = self.X(v)
        da = f' stroke-dasharray="{dash}"' if dash else ''
        self.p.raw(f'<line x1="{x:.1f}" y1="{self.y}" x2="{x:.1f}" y2="{self.y + self.h}" stroke="{color}" stroke-width="{sw}"{da}/>')

    def hline(self, v, color='#777777', dash='4 3', sw=1.2):
        y = self.Y(v)
        da = f' stroke-dasharray="{dash}"' if dash else ''
        self.p.raw(f'<line x1="{self.x}" y1="{y:.1f}" x2="{self.x + self.w}" y2="{y:.1f}" stroke="{color}" stroke-width="{sw}"{da}/>')

    def text(self, vx, vy, s, size=13.5, col=K, anchor='start', w=600, dx=0, dy=0):
        self.p.text(self.X(vx) + dx, self.Y(vy) + dy, s, size, col, anchor, w)

    def arrow(self, v0, v1, color=2, sw=1.6, pad0=8, pad1=10):
        s, _ = _col(color)
        x0, y0 = self.X(v0[0]), self.Y(v0[1])
        x1, y1 = self.X(v1[0]), self.Y(v1[1])
        dist = math.hypot(x1 - x0, y1 - y0)
        if dist <= pad0 + pad1 + 2:
            return
        ux, uy = (x1 - x0) / dist, (y1 - y0) / dist
        mid = self.p._mark(s)
        self.p.raw(f'<line x1="{x0 + ux * pad0:.1f}" y1="{y0 + uy * pad0:.1f}" '
                   f'x2="{x1 - ux * pad1:.1f}" y2="{y1 - uy * pad1:.1f}" '
                   f'stroke="{s}" stroke-width="{sw}" marker-end="url(#{mid})"/>')


class Plot:
    def __init__(self, W=800, H=440):
        self.W, self.H = W, H
        self.o = []
        self.leg = []
        self.marks = {}

    def _mark(self, col):
        if col not in self.marks:
            self.marks[col] = f'pm{len(self.marks)}'
        return self.marks[col]

    def raw(self, s):
        self.o.append(s)

    def panel(self, x, y, w, h, rx=10):
        self.raw(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{PANEL}"/>')

    def text(self, x, y, s, size=14, col=K, anchor='start', w=400):
        self.raw(f'<text x="{x:.1f}" y="{y:.1f}" text-anchor="{anchor}" style="font-size:{size}px;fill:{col};font-weight:{w}">{s}</text>')

    def axes(self, x, y, w, h, xr, yr, xlabel=None, ylabel=None, xticks=(), yticks=(),
             xlog=False, ylog=False, xticklabels=None, yticklabels=None,
             xgrid=False, ygrid=True, yminor=False, title=None, plot_bg='#ffffff', title_x=None):
        ax = Axes(self, x, y, w, h, xr, yr, xlog, ylog)
        if title:
            self.text(x if title_x is None else title_x, y - 14, title, 15.5, K, 'start', 600)
        if plot_bg:
            self.raw(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="{plot_bg}"/>')
        # 网格线先画
        if ygrid:
            for v in yticks:
                yy = ax.Y(v)
                self.raw(f'<line x1="{x}" y1="{yy:.1f}" x2="{x + w}" y2="{yy:.1f}" stroke="{GRID}" stroke-width="0.9"/>')
        if xgrid:
            for v in xticks:
                xx = ax.X(v)
                self.raw(f'<line x1="{xx:.1f}" y1="{y}" x2="{xx:.1f}" y2="{y + h}" stroke="{GRID}" stroke-width="0.9"/>')
        # 对数纵轴次刻度（一眼可见对数坐标，不必在轴标题写“对数坐标”）
        if ylog and yminor:
            p0 = int(math.floor(math.log10(yr[0])))
            p1 = int(math.ceil(math.log10(yr[1])))
            for p in range(p0, p1 + 1):
                for m in range(2, 10):
                    v = m * (10 ** p)
                    if yr[0] < v < yr[1]:
                        yy = ax.Y(v)
                        self.raw(f'<line x1="{x - 3}" y1="{yy:.1f}" x2="{x}" y2="{yy:.1f}" stroke="#777777" stroke-width="0.9"/>')
        # 主刻度与标签
        for i, v in enumerate(yticks):
            yy = ax.Y(v)
            self.raw(f'<line x1="{x - 5}" y1="{yy:.1f}" x2="{x}" y2="{yy:.1f}" stroke="{AXIS}" stroke-width="1.1"/>')
            self.text(x - 10, yy + 4.5, yticklabels[i] if yticklabels else fmt(v), 13, TICK, 'end', 400)
        for i, v in enumerate(xticks):
            xx = ax.X(v)
            self.raw(f'<line x1="{xx:.1f}" y1="{y + h}" x2="{xx:.1f}" y2="{y + h + 5}" stroke="{AXIS}" stroke-width="1.1"/>')
            self.text(xx, y + h + 21, xticklabels[i] if xticklabels else fmt(v), 13, TICK, 'middle', 400)
        # 坐标轴边框（L 形经典论文样式）
        self.raw(f'<line x1="{x}" y1="{y + h}" x2="{x + w}" y2="{y + h}" stroke="{AXIS}" stroke-width="1.3"/>')
        self.raw(f'<line x1="{x}" y1="{y}" x2="{x}" y2="{y + h}" stroke="{AXIS}" stroke-width="1.3"/>')
        if xlabel:
            self.text(x + w / 2, y + h + 45, xlabel, 14.5, K, 'middle', 600)
        if ylabel:
            self.raw(f'<text x="{x - 54}" y="{y + h / 2:.1f}" text-anchor="middle" '
                     f'transform="rotate(-90 {x - 54} {y + h / 2:.1f})" '
                     f'style="font-size:14.5px;fill:{K};font-weight:600">{ylabel}</text>')
        return ax

    def legend_box(self, x, y, items=None, dy=24):
        """图内左上/右上简洁竖排图例"""
        entries = items if items is not None else self.leg
        for i, it in enumerate(entries):
            kind, col, dash, mk, fill, lab = it
            cy = y + i * dy
            if kind == 'line':
                da = f' stroke-dasharray="{dash}"' if dash else ''
                self.raw(f'<line x1="{x}" y1="{cy - 4}" x2="{x + 26}" y2="{cy - 4}" stroke="{col}" stroke-width="2.4"{da}/>')
                if mk == 'o':
                    self.raw(f'<circle cx="{x + 13}" cy="{cy - 4}" r="4" fill="{fill}" stroke="{col}" stroke-width="2"/>')
                elif mk == 'O':
                    self.raw(f'<circle cx="{x + 13}" cy="{cy - 4}" r="4" fill="{col}"/>')
                elif mk == 'S':
                    self.raw(f'<rect x="{x + 9}" y="{cy - 8}" width="8" height="8" fill="{col}"/>')
            elif kind == 'dot':
                if mk == 'o':
                    self.raw(f'<circle cx="{x + 13}" cy="{cy - 4}" r="4.5" fill="{fill}" stroke="{col}" stroke-width="1.8"/>')
                elif mk == 's':
                    self.raw(f'<rect x="{x + 8.5}" y="{cy - 8.5}" width="9" height="9" fill="{fill}" stroke="{col}" stroke-width="1.8"/>')
                elif mk == 'S':
                    self.raw(f'<rect x="{x + 8.5}" y="{cy - 8.5}" width="9" height="9" fill="{col}"/>')
                elif mk == 'd':
                    self.raw(f'<path d="M{x + 13} {cy - 10} L{x + 19} {cy - 4} L{x + 13} {cy + 2} L{x + 7} {cy - 4} Z" fill="{fill}" stroke="{col}" stroke-width="1.9"/>')
                else:
                    self.raw(f'<circle cx="{x + 13}" cy="{cy - 4}" r="4.5" fill="{col}"/>')
            elif kind == 'line':
                pass
            elif kind == 'box':
                self.raw(f'<rect x="{x + 4}" y="{cy - 11}" width="18" height="13" fill="{fill}" stroke="{col}" stroke-width="0.9"/>')
            elif kind == 'squares':
                # 双空心方块对照（如 h18 / h18g）
                for k, c2 in enumerate(col):
                    self.raw(f'<rect x="{x + 1 + k * 14}" y="{cy - 9.5}" width="10" height="10" fill="#ffffff" stroke="{c2}" stroke-width="2"/>')
            self.text(x + 34, cy + 1, lab, 13.5, K, 'start', 400)

    def save(self, name):
        defs = ''
        if self.marks:
            defs = '<defs>' + ''.join(
                f'<marker id="{m}" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="5" markerHeight="5" orient="auto">'
                f'<path d="M0,0 L10,5 L0,10 z" fill="{c}"/></marker>'
                for c, m in self.marks.items()) + '</defs>'
        svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {self.W} {self.H}" width="{self.W}" height="{self.H}">'
               f'<style>{FONT}</style>{defs}'
               f'<rect width="{self.W}" height="{self.H}" fill="#ffffff"/>\n'
               + '\n'.join(self.o) + '\n</svg>')
        path = os.path.join(OUT, name + '.svg')
        open(path, 'w').write(svg)
        return path
