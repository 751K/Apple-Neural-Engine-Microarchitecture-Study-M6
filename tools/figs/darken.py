#!/usr/bin/env python3
# 由浅色 SVG 生成深色版本：figs/<语言>/light/<名>.svg → figs/<语言>/dark/<名>.svg（供网页的深色模式使用）。
# 规则（HLS 空间逐色换算）：
#   中性色（饱和度 < 0.15）：亮度反转并压缩到 [0.10, 0.95]，文字变浅、底色变深；
#   彩色的浅底色（亮度 > 0.75）：保持色相，变为同色相的深色底（亮度约 0.2，饱和度不超过 0.45）；
#   彩色的描边与文字：保持色相，提高亮度，使其在深色背景上可读。
# 另在最底层加一块背景（BG），使导出的 PNG 也是深色底。
# 用法：python3 tools/figs/darken.py [figs/<语言>/light/<名>.svg ...]（缺省为 figs/zh/light 与 figs/en/light 下的全部 SVG）
import colorsys
import glob
import os
import re
import sys

BG = '#161618'
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..')


def dark(c):
    r, g, b = (int(c[i:i + 2], 16) / 255 for i in (1, 3, 5))
    h, l, s = colorsys.rgb_to_hls(r, g, b)
    if s < 0.15 or l > 0.98:                       # 中性色
        l2, s2 = 0.10 + 0.85 * (1 - l) ** 0.85, s
    elif l > 0.75:                                 # 彩色浅底
        l2, s2 = 0.30 - (l - 0.80) * 0.6, min(s, 0.45)
    else:                                          # 彩色描边、文字
        l2, s2 = min(0.80, 0.55 + 0.5 * (l - 0.30)), min(1.0, s * 1.1)
    r, g, b = colorsys.hls_to_rgb(h, max(0.0, min(1.0, l2)), s2)
    return '#%02x%02x%02x' % tuple(round(v * 255) for v in (r, g, b))


def convert(path):
    s = open(path).read()
    s = re.sub(r'#[0-9a-fA-F]{6}\b', lambda m: dark(m.group().lower()), s)
    vb = re.search(r'viewBox="([-\d.]+) ([-\d.]+) ([\d.]+) ([\d.]+)"', s).groups()
    tag_end = s.index('>', s.index('<svg')) + 1
    bg = f'\n<rect x="{vb[0]}" y="{vb[1]}" width="{vb[2]}" height="{vb[3]}" fill="{BG}"/>'
    s = s[:tag_end] + bg + s[tag_end:]
    light_dir = os.path.dirname(os.path.abspath(path))
    out_dir = os.path.join(os.path.dirname(light_dir), 'dark')
    os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(out_dir, os.path.basename(path))
    open(out, 'w').write(s)
    print(out)


files = sys.argv[1:] or sorted(glob.glob(os.path.join(ROOT, 'figs', '*', 'light', '*.svg')))
for f in files:
    convert(f)
