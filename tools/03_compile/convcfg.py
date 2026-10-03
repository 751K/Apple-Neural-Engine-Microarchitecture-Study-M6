"""在 TD 流中找卷积配置字（v31 ConvCfg：Kw 0-5、Kh 6-11、Sx 13-14、Sy 15-16、PadLeft 17-21、PadTop 22-26、Ox 28-29、Oy 30-31），逐个解码。

用法：python3 convcfg.py <model.hwx> <kHxkW>（见 hwx_h18g.md §10）"""
import os as _os, sys as _sys  # 仓库里按目录存放、部署到 M6 时平铺：两种布局都能找到公共模块
_here = _os.path.dirname(_os.path.abspath(__file__))
_sys.path[:0] = [_here, _os.path.join(_here, "..", "lib"), _os.path.join(_here, "..", "common")]
import sys
from collections import Counter
sys.path.insert(0, __import__("os").path.dirname(__file__) or ".")
import td_widths as tw
kh, kw = map(int, sys.argv[2].split("x"))
st = tw.streams(sys.argv[1])
w = next(v for k, v in st.items() if "nonbonded" in k)
def dec(x):
    return dict(Kw=x & 63, Kh=(x >> 6) & 63, b12=(x >> 12) & 1, Sx=(x >> 13) & 3, Sy=(x >> 15) & 3,
                PadL=(x >> 17) & 31, PadT=(x >> 22) & 31, b27=(x >> 27) & 1, Ox=(x >> 28) & 3, Oy=(x >> 30) & 3)
# 候选：1 ≤ Kw ≤ max(kw,15)、1 ≤ Kh ≤ max(kh,17)，Sx、Sy ≤ 2，且该位置在每个卷积 TD 中都出现
cand = Counter()
for i, x in enumerate(w):
    d = dec(x)
    if 1 <= d["Kw"] <= 17 and 1 <= d["Kh"] <= 17 and d["Sx"] <= 2 and d["Sy"] <= 2 and d["PadL"] <= 16 and d["PadT"] <= 16:
        cand[x] += 1
print(f"== {sys.argv[2]}：符合 ConvCfg 形态的字（值 ×出现次数 → 解码）")
for x, n in cand.most_common(8):
    print(f"   {x:#010x} ×{n:3d}  {dec(x)}")
