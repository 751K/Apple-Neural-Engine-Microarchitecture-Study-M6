"""双 ANE（h18g）HWX 中每个引擎流的卷积 TD：数量，以及每个 TD 卷积配置字之前的 8 个字（输入宽、行、通道、X、输出宽、行、通道等）。

用法：python3 ks4_td.py <model.hwx> <kHxkW>
  卷积配置字按 v31 ConvCfg 布局识别（取流中出现最多的、Kh / Kw 与核相符的字；核宽 9–15 被改写为步长 2，
  配置字里的 Kw = 核宽 + 1 再补成偶数，例如 9 → 10、12 → 14、15 → 16）。
"""
import os as _os, sys as _sys  # 仓库里按目录存放、部署到 M6 时平铺：两种布局都能找到公共模块
_here = _os.path.dirname(_os.path.abspath(__file__))
_sys.path[:0] = [_here, _os.path.join(_here, "..", "lib"), _os.path.join(_here, "..", "common")]
import sys
from collections import Counter
sys.path.insert(0, __import__("os").path.dirname(__file__) or ".")
import td_widths as tw

kh, kw = map(int, sys.argv[2].split("x"))
st = tw.streams(sys.argv[1])


def is_cfg(x):
    return (x >> 6) & 63 == kh and (x & 63) in (kw, kw + 1 + ((kw + 1) & 1)) and (x >> 13) & 3 <= 2


for name in sorted(st):
    w = st[name]
    c = Counter(x for x in w if is_cfg(x))
    if not c:
        print(f"{name}: 无卷积配置字")
        continue
    cfg = c.most_common(1)[0][0]
    pos = [i for i, x in enumerate(w) if x == cfg]
    print(f"{name}: 配置字 {cfg:#010x}，卷积 TD {len(pos)} 个，流 {4 * len(w)} 字节")
    for p in pos[:12]:
        print("   " + " ".join(f"{w[p + d]:08x}" if p + d >= 0 else "--------" for d in range(-8, 1)))
