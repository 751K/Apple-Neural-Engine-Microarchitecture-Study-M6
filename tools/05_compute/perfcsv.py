"""编译器性能模型的逐层 CSV（DebugMask bit 11）与 TD 形状对齐。

用法（M6）：python3 perfcsv.py <输出目录> <mlmodelc> [<mlmodelc> ...]
每个模型用 anevariant.dylib（只在本进程把 os_variant_has_internal_content("com.apple.ane") 视为真）+ anecc 编译，
读 <输出>/<名字>/model.hwx.h18g_perf_all.csv，按顺序与 nonbonded 流的 TD 对齐（CSV 每行一个 TD）。
输出每个 TD：类型、Cin、Cout、H×W、核、OCG、NumWU、每 WU 像素（Hout×Wout ÷ NumWU）、mac/WU、
每 NE 每周期乘加（卷积：Cout×Hout×Wout×Cin×kH×kW ÷ 16 NE ÷ (NumWU × mac/WU)）。
寄存器：1 Win、2 Hin、3 Cin、5 Wout、6 Hout、7 Cout、0xa 卷积配置字、0x10 NE 配置（OcgSize log2 [2:0]）；TD 只写变化的寄存器，沿流累积。
"""
import os as _os, sys as _sys  # 仓库里按目录存放、部署到 M6 时平铺：两种布局都能找到公共模块
_here = _os.path.dirname(_os.path.abspath(__file__))
_sys.path[:0] = [_here, _os.path.join(_here, "..", "lib"), _os.path.join(_here, "..", "common")]
import csv
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(__file__) or ".")
import td_widths as tw  # noqa: E402
import tdwalk  # noqa: E402

out = sys.argv[1]
os.makedirs(out, exist_ok=True)
env = dict(os.environ, DYLD_INSERT_LIBRARIES=os.path.abspath("anevariant.dylib"))
M = 0x1ffff
print(f"{'模型':30s} {'#':>2} {'类':2s} {'Cin':>4} {'Cout':>4} {'H×W':>7} {'核':>4} {'OCG':>3} {'NumWU':>5} {'像素/WU':>7} "
      f"{'mac/WU':>7} {'post/WU':>7} {'NE单缓冲':>9} {'NE双缓冲':>9} {'PE':>7} {'L2周期':>8} {'MAC/NE/周期':>11} {'估计ms':>8}")
for mc in sys.argv[2:]:
    name = os.path.basename(mc.rstrip("/")).replace(".mlmodelc", "")
    d = os.path.join(out, name)
    csvp = os.path.join(d, "model.hwx.h18g_perf_all.csv")
    if not os.path.exists(csvp):
        subprocess.run(["./anecc", mc, d, "h18g", "DebugMask=0x800"], env=env, capture_output=True)
    if not os.path.exists(csvp):
        print(f"{name:30s} 没有 CSV")
        continue
    rows = [r for r in csv.DictReader(open(csvp)) if r[""].strip().isdigit()]
    nb = next(w for k, w in tw.streams(os.path.join(d, "model.hwx")).items() if "nonb" in k)
    st, tds = {}, []
    for _, h, r, _ in tdwalk.walk(nb):
        st.update(r)
        tds.append((h, dict(st)))
    for i, row in enumerate(rows):
        if i >= len(tds):
            break
        h, s = tds[i]
        conv = (h[8] >> 16) & 7 == 5
        cfg = s.get(0xa, 0)
        kh, kw = (cfg >> 6) & 63, cfg & 63
        if conv and kh == 0:
            kh = kw = 1
        cin, cout, ho, wo = s.get(3, 0) & M, s.get(7, 0) & M, s.get(6, 0) & M, s.get(5, 0) & M
        nwu, mpw = int(row["NumWU"]), int(row["mac_cycles_per_WU"])
        px = ho * wo / nwu if nwu else 0
        mac = cout * ho * wo * cin * kh * kw if conv else 0
        rate = mac / 16 / (nwu * mpw) if conv and nwu and mpw else 0
        print(f"{name:30s} {i:2d} {'卷' if conv else '他':2s} {cin:4d} {cout:4d} {f'{ho}×{wo}':>7} {f'{kh}×{kw}' if conv else '-':>4} "
              f"{1 << (s.get(0x10, 0) & 7):3d} {nwu:5d} {px:7.1f} {mpw:7d} {int(row['post_cycles_per_WU']):7d} "
              f"{int(row['ne_cycle_single_buffering']):9d} {int(row['ne_cycle_double_buffering']):9d} {int(row['pe_cycle']):7d} "
              f"{int(row['l2_cycle_count']):8d} {rate:11.1f} {float(row['estimated_time(ms)']):8.4f}")
