"""按某个配置字对齐，并排打印多个 TD 中该字前后的字。用法：python3 tddump.py <model.hwx> <配置字十六进制> [TD 个数] [起始字偏移] [结束字偏移]"""
import os as _os, sys as _sys  # 仓库里按目录存放、部署到 M6 时平铺：两种布局都能找到公共模块
_here = _os.path.dirname(_os.path.abspath(__file__))
_sys.path[:0] = [_here, _os.path.join(_here, "..", "lib"), _os.path.join(_here, "..", "common")]
import sys
sys.path.insert(0, __import__("os").path.dirname(__file__) or ".")
import td_widths as tw
st = tw.streams(sys.argv[1])
w = next(v for k, v in st.items() if "nonbonded" in k)
cfg = int(sys.argv[2], 16)
pos = [i for i, x in enumerate(w) if x == cfg]
n = int(sys.argv[3]) if len(sys.argv) > 3 else 3
lo, hi = int(sys.argv[4]) if len(sys.argv) > 4 else -80, int(sys.argv[5]) if len(sys.argv) > 5 else 80
print(f"配置字 {cfg:#010x} 出现在流内偏移：{[hex(4*p) for p in pos[:8]]}")
for d in range(lo, hi):
    vals = [w[p + d] if 0 <= p + d < len(w) else None for p in pos[:n]]
    if all(v == 0 for v in vals):
        continue
    print(f"  {4*d:+05x}  " + "  ".join(f"{v:08x}" if v is not None else "--------" for v in vals))
