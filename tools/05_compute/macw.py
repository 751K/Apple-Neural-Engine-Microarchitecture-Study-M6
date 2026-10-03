"""INT8 MAC 宽度（第 1 步）：同一单层卷积分别编成 FP16、W8（只量化权重）、W8A8，比较编译器估计的 exe_cycles。

用法（M6）：
  /opt/miniconda3/envs/mps/bin/python macw.py build <目录>     生成 mlmodelc 并用 anecc 编成 h18g HWX
  python3 macw.py table <目录>                                  输出每种形状三种精度的 TD 数与 exe_cycles 之和
单层（L1），共享权重，输入直接从 DRAM 读，避免链式读入的层 exe_cycles 记为 0。
"""
import os as _os, sys as _sys  # 仓库里按目录存放、部署到 M6 时平铺：两种布局都能找到公共模块
_here = _os.path.dirname(_os.path.abspath(__file__))
_sys.path[:0] = [_here, _os.path.join(_here, "..", "lib"), _os.path.join(_here, "..", "common")]
import os
import subprocess
import sys

SHAPES = [(k, c, s) for k in (1, 3) for c in (32, 64, 128, 256, 512) for s in (16, 32, 64)]


def name(k, c, s):
    return f"k{k}_c{c}_h{s}w{s}_L1"


def build(out):
    import numpy as np
    import coremltools as ct
    import coremltools.optimize.coreml as oc
    from coremltools.optimize.coreml.experimental import OpActivationLinearQuantizerConfig, linear_quantize_activations
    from chain import program
    os.makedirs(out, exist_ok=True)
    for k, c, s in SHAPES:
        n = name(k, c, s)
        for mode in ("f16", "w8", "q8"):
            d = os.path.join(out, f"{n}_{mode}")
            if os.path.exists(os.path.join(d, "hwx", "model.hwx")):
                continue
            m = ct.convert(program(str(k), c, s, s, 1, False), convert_to="mlprogram",
                           minimum_deployment_target=ct.target.iOS18, compute_units=ct.ComputeUnit.CPU_ONLY)
            if mode == "q8":
                rng = np.random.default_rng(0)
                data = [{"x": rng.standard_normal((1, c, s, s)).astype(np.float16)} for _ in range(4)]
                m = linear_quantize_activations(m, oc.OptimizationConfig(
                    global_config=OpActivationLinearQuantizerConfig(mode="linear_symmetric")), data)
            if mode != "f16":
                m = oc.linear_quantize_weights(m, oc.OptimizationConfig(
                    global_config=oc.OpLinearQuantizerConfig(mode="linear_symmetric", dtype="int8")))
            pkg = d + ".mlpackage"
            m.save(pkg)
            subprocess.run(["xcrun", "coremlcompiler", "compile", pkg, d], check=True, capture_output=True)
            subprocess.run(["rm", "-rf", pkg])
            mc = os.path.join(d, os.path.basename(d) + ".mlmodelc")
            r = subprocess.run(["./anecc", mc, os.path.join(d, "hwx"), "h18g"], capture_output=True)
            print(n, mode, r.returncode, flush=True)


def table(out):
    sys.path.insert(0, ".")
    import td_widths as tw
    import tdwalk
    print(f"{'形状':22s} " + " ".join(f"{m:>14s}" for m in ("f16 TD/ec", "w8 TD/ec", "q8 TD/ec")) + "   f16/q8")
    for k, c, s in SHAPES:
        n = name(k, c, s)
        cells, ecs = [], []
        for mode in ("f16", "w8", "q8"):
            p = os.path.join(out, f"{n}_{mode}", "hwx", "model.hwx")
            if not os.path.exists(p):
                cells.append(f"{'-':>14s}"); ecs.append(None); continue
            st = tw.streams(p)
            nb = next(w for kk, w in st.items() if "nonb" in kk)
            e = [h[1] & 0xffff for _, h, _, _ in tdwalk.walk(nb)]
            cells.append(f"{len(e):5d} {sum(e):6d} {'' if len(e) < 2 else ''}".rjust(14))
            ecs.append(sum(e))
        r = f"{ecs[0] / ecs[2]:6.2f}" if ecs[0] and ecs[2] else "     -"
        print(f"{n:22s} " + " ".join(cells) + "   " + r)


if __name__ == "__main__":
    {"build": build, "table": table}[sys.argv[1]](sys.argv[2])
