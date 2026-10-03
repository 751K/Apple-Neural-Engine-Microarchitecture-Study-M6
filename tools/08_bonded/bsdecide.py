"""双 ANE 决策分析：每个 h18g 编译产物的 nonbonded 程序估计耗时（TD 头 exe_cycles 之和）与 bonded 程序是否用到 ANE1。

用法：python3 bsdecide.py <目录>（目录下每个子目录含 model.hwx，子目录名为模型名）
输出每行：模型 nonbonded_TD数 exe_cycles之和 bonded是否有ANE1流 ANE1_TD数 ANE0_TD数
"""
import os as _os, sys as _sys  # 仓库里按目录存放、部署到 M6 时平铺：两种布局都能找到公共模块
_here = _os.path.dirname(_os.path.abspath(__file__))
_sys.path[:0] = [_here, _os.path.join(_here, "..", "lib"), _os.path.join(_here, "..", "common")]
import os
import sys
sys.path.insert(0, os.path.dirname(__file__) or ".")
import td_widths as tw
import tdwalk

rows = []
for m in sorted(os.listdir(sys.argv[1])):
    p = os.path.join(sys.argv[1], m, "model.hwx")
    if not os.path.exists(p):
        continue
    st = tw.streams(p)
    nb = next((w for k, w in st.items() if "nonbonded" in k), None)
    if nb is None:
        continue
    tds = list(tdwalk.walk(nb))
    ec = sum(h[1] & 0xffff for _, h, _, _ in tds)
    a1 = next((w for k, w in st.items() if "ane1" in k), None)
    a0 = next((w for k, w in st.items() if "ane0" in k and "nonbonded" not in k), None)
    n1 = len(list(tdwalk.walk(a1))) if a1 else 0
    n0 = len(list(tdwalk.walk(a0))) if a0 else 0
    print(f"{m:28s} {len(tds):4d} {ec:6d} {'双' if a1 else '单'} {n1:4d} {n0:4d}")
