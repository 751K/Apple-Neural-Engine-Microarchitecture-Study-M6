"""NE 的 OCG（每轮输出通道数）与工作单元形状：编译器在 TD 里的选择。

用法（M6）：
  /opt/miniconda3/envs/mps/bin/python ocg.py build <目录>   生成单层卷积（FP16 / W8A8），用 anecc 编成 h18g
  python3 ocg.py table <目录>                               逐个卷积 TD 输出：Cin、Cout、核、OCG、HalfWU、patch 宽 / 高、SmallSourceMode
寄存器（hwx_h18g.md §12）：0xf 任务信息（SmallSourceMode bits 2–3）；0x10 = NE 配置：OcgSize（log2）[2:0]、HalfWU [6]；
0x11 = PatchWidth [3:0]、PatchHeight [8:4]。TD 只写与上一个 TD 不同的寄存器，解析时沿流累积状态。
"""
import os as _os, sys as _sys  # 仓库里按目录存放、部署到 M6 时平铺：两种布局都能找到公共模块
_here = _os.path.dirname(_os.path.abspath(__file__))
_sys.path[:0] = [_here, _os.path.join(_here, "..", "lib"), _os.path.join(_here, "..", "common")]
import os
import subprocess
import sys

KS = ["1", "1x3", "3x1", "2", "3", "5", "7"]
CS = [(16, 256), (64, 256), (256, 256), (512, 512)]


def models():
    for k in KS:
        for cin, cout in CS:
            for mode in ("f16", "q8"):
                yield f"k{k}_ci{cin}_co{cout}_{mode}", k, cin, cout, mode


def build(out):
    import numpy as np
    import coremltools as ct
    import coremltools.optimize.coreml as oc
    from coremltools.converters.mil import Builder as mb
    from coremltools.converters.mil.mil import types
    from coremltools.optimize.coreml.experimental import OpActivationLinearQuantizerConfig, linear_quantize_activations
    os.makedirs(out, exist_ok=True)
    H = W = 32
    for name, k, cin, cout, mode in models():
        d = os.path.join(out, name)
        if os.path.exists(os.path.join(d, "hwx", "model.hwx")):
            continue
        kh, kw = (int(k.split("x")[0]), int(k.split("x")[-1]))
        wt = (np.random.default_rng(0).standard_normal((cout, cin, kh, kw)) * np.sqrt(2.0 / (cin * kh * kw))).astype(np.float16)

        @mb.program(input_specs=[mb.TensorSpec(shape=(1, cin, H, W), dtype=types.fp16)], opset_version=ct.target.iOS18)
        def p(x):
            return mb.relu(x=mb.conv(x=x, weight=mb.const(val=wt), bias=mb.const(val=np.zeros(cout, np.float16)), pad_type="same"))
        m = ct.convert(p, convert_to="mlprogram", minimum_deployment_target=ct.target.iOS18, compute_units=ct.ComputeUnit.CPU_ONLY)
        if mode == "q8":
            data = [{"x": np.random.default_rng(i).standard_normal((1, cin, H, W)).astype(np.float16)} for i in range(4)]
            m = linear_quantize_activations(m, oc.OptimizationConfig(
                global_config=OpActivationLinearQuantizerConfig(mode="linear_symmetric")), data)
            m = oc.linear_quantize_weights(m, oc.OptimizationConfig(
                global_config=oc.OpLinearQuantizerConfig(mode="linear_symmetric", dtype="int8")))
        pkg = d + ".mlpackage"
        m.save(pkg)
        subprocess.run(["xcrun", "coremlcompiler", "compile", pkg, d], check=True, capture_output=True)
        subprocess.run(["rm", "-rf", pkg])
        mc = os.path.join(d, name + ".mlmodelc")
        r = subprocess.run(["./anecc", mc, os.path.join(d, "hwx"), "h18g"], capture_output=True)
        print("built", name, r.returncode, flush=True)


def table(out):
    sys.path.insert(0, ".")
    import td_widths as tw
    import tdwalk
    M = 0x1ffff
    print(f"{'模型':24s} TD  {'Cin':>4} {'Cout/TD':>7} {'核':>5}  OCG  HalfWU  patch宽×高  SSM  ActiveNE估计")
    for name, *_ in models():
        p = os.path.join(out, name, "hwx", "model.hwx")
        if not os.path.exists(p):
            continue
        nb = next(w for k, w in tw.streams(p).items() if "nonb" in k)
        st = {}
        seen = set()
        for i, (_, h, r, _) in enumerate(tdwalk.walk(nb)):
            st.update(r)
            if (h[8] >> 16) & 7 != 5:
                continue
            g = lambda a: st.get(a, 0)
            cfg = g(0xa)
            kw_, kh_ = cfg & 63, (cfg >> 6) & 63
            ne, pt, ti = g(0x10), g(0x11), g(0xf)
            row = (g(3) & M, g(7) & M, f"{kh_}×{kw_}", 1 << (ne & 7), (ne >> 6) & 1, f"{1 << (pt & 15)}×{1 << ((pt >> 4) & 31)}" if pt else "-", (ti >> 2) & 3)
            if row in seen:
                continue
            seen.add(row)
            cin, cout, kk, ocg, hw, patch, ssm = row
            print(f"{name:24s} {i:2d}  {cin:4d} {cout:7d} {kk:>5}  {ocg:3d}  {hw:4d}    {patch:>9}  {ssm:3d}  {cout / ocg:6.1f}")


if __name__ == "__main__":
    {"build": build, "table": table}[sys.argv[1]](sys.argv[2])
