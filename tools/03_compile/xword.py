"""收集每个卷积 TD 中 Cin 之后的那个字（与 Win、Hin、Cin 一起按"Win Hin Cin X Wout Hout Cout ConvCfg"定位：ConvCfg 前 4 个字），和该 TD 的其他字段并列。"""
import os as _os, sys as _sys  # 仓库里按目录存放、部署到 M6 时平铺：两种布局都能找到公共模块
_here = _os.path.dirname(_os.path.abspath(__file__))
_sys.path[:0] = [_here, _os.path.join(_here, "..", "lib"), _os.path.join(_here, "..", "common")]
import sys, glob, os
from collections import Counter
sys.path.insert(0, __import__("os").path.dirname(__file__) or ".")
import td_widths as tw
def isconv(x):
    kw, kh, sx, sy = x & 63, (x >> 6) & 63, (x >> 13) & 3, (x >> 15) & 3
    return 1 <= kw <= 16 and 1 <= kh <= 16 and 1 <= sx <= 2 and 1 <= sy <= 2 and (x >> 28) & 3 in (1, 2)
for path in sys.argv[1:]:
    st = tw.streams(path)
    for k, w in st.items():
        rows = Counter()
        for i in range(8, len(w)):
            x = w[i]
            if isconv(x) and 1 <= w[i - 7] <= 65536 and w[i - 5] in (16, 32, 48, 64, 96, 128, 256, 512, 1024) and w[i - 3] <= 65536:
                rows[(w[i - 7], w[i - 6], w[i - 5], w[i - 4], w[i - 3], w[i - 2], w[i - 1], x)] += 1
        for r, n in rows.most_common(4):
            Win, Hin, Cin, X, Wo, Ho, Co, cfg = r
            print(f"{os.path.basename(os.path.dirname(path)):26s} {k.split('_main__')[1][:9]:9s} ×{n:3d}  Win {Win:5d} Hin {Hin:4d} Cin {Cin:4d}  X {X:#010x}  Wout {Wo:5d} Hout {Ho:4d} Cout {Co:4d}  cfg {cfg:#010x}")
