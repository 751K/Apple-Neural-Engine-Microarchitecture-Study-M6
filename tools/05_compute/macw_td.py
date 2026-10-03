"""INT8 MAC 宽度：逐个 TD 输出形状、乘加次数和编译器估计 exe_cycles，以及"每单位 exe_cycles 的乘加次数"。

用法：python3 macw_td.py <macw 目录> [模型名过滤]
寄存器（hwx_h18g.md §11）：1 Win、2 Hin、3 Cin、5 Wout、6 Hout、7 Cout、10 卷积配置字（bits 0–5 Kw、6–11 Kh）。各 17 位。
标志字 bits 16–18 = 5 表示卷积 TD。
"""
import os as _os, sys as _sys  # 仓库里按目录存放、部署到 M6 时平铺：两种布局都能找到公共模块
_here = _os.path.dirname(_os.path.abspath(__file__))
_sys.path[:0] = [_here, _os.path.join(_here, "..", "lib"), _os.path.join(_here, "..", "common")]
import os
import sys
sys.path.insert(0, os.path.dirname(__file__) or ".")
import td_widths as tw
import tdwalk

d = sys.argv[1]
flt = sys.argv[2] if len(sys.argv) > 2 else ""
M = 0x1ffff
for m in sorted(os.listdir(d)):
    p = os.path.join(d, m, "hwx", "model.hwx")
    if flt not in m or not os.path.exists(p):
        continue
    nb = next(w for k, w in tw.streams(p).items() if "nonb" in k)
    print(m)
    for _, h, r, _ in tdwalk.walk(nb):
        ec, fl = h[1] & 0xffff, h[8]
        g = lambda a: r.get(a, 0) & M
        cfg = r.get(10, 0)
        kw_, kh_ = cfg & 63, (cfg >> 6) & 63
        conv = (fl >> 16) & 7 == 5
        mac = g(5) * g(6) * g(7) * g(3) * kh_ * kw_ if conv else 0
        print(f"   ec {ec:4d} 标志 {fl:08x} in {g(1)}×{g(2)}×{g(3)} out {g(5)}×{g(6)}×{g(7)} k {kh_}×{kw_}"
              + (f"  MAC {mac / 1e6:8.2f} M  MAC/ec {mac / ec / 1e6:6.2f} M" if conv and ec else ""))
