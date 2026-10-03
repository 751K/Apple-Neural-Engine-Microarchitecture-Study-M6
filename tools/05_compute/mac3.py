"""INT8 MAC 宽度（第 3 步）：只受乘加限制的卷积链，FP16 与 W8A8 的每层耗时（斜率）。

用法（M6）：/opt/miniconda3/envs/mps/bin/python mac3.py <输出目录> [d,k,C,H,W ...]（另可用环境变量 MAC3_LAYERS=4,16）
生成 d{膨胀}_k{核}_c{C}_h{H}w{W}_L{层数}_{f16|q8}.mlmodelc。共享权重、He 初始化、relu。
形状选择：
  - 1×1 且 C ≥ 1024：每字节激活对应 C 次乘加，W8A8 链中激活经过 DRAM（H10）时所需带宽 ≤ 20 GB/s；
  - 1×1、512 通道、64²：对照（所需激活带宽约 40 GB/s）；
  - 膨胀率 2 的 3×3：没有 Winograd，测的是直接卷积。
"""
import os
import subprocess
import sys

import torch  # noqa: F401
import numpy as np
import coremltools as ct
import coremltools.optimize.coreml as oc
from coremltools.converters.mil import Builder as mb
from coremltools.converters.mil.mil import types
from coremltools.optimize.coreml.experimental import OpActivationLinearQuantizerConfig, linear_quantize_activations

SHAPES = [(1, 1, 1024, 32, 32), (1, 1, 2048, 16, 16), (1, 1, 2048, 32, 32), (1, 1, 512, 64, 64), (2, 3, 512, 32, 32)]
LAYERS = (4, 16)


def program(d, k, C, H, W, L):
    rng = np.random.default_rng(0)
    wt = (rng.standard_normal((C, C, k, k)) * np.sqrt(2.0 / (C * k * k))).astype(np.float16)

    @mb.program(input_specs=[mb.TensorSpec(shape=(1, C, H, W), dtype=types.fp16)], opset_version=ct.target.iOS18)
    def p(x):
        w = mb.const(val=wt)
        b = mb.const(val=np.zeros(C, np.float16))
        for _ in range(L):
            x = mb.relu(x=mb.conv(x=x, weight=w, bias=b, pad_type="same", dilations=[d, d]))
        return x
    return p


if __name__ == "__main__":
    out = sys.argv[1]
    # 可选：第 2 个参数起为形状列表 "d,k,C,H,W"，层数用环境变量 MAC3_LAYERS（如 "4,16"）
    if len(sys.argv) > 2:
        SHAPES = [tuple(int(x) for x in a.split(",")) for a in sys.argv[2:]]
    if os.environ.get("MAC3_LAYERS"):
        LAYERS = tuple(int(x) for x in os.environ["MAC3_LAYERS"].split(","))
    os.makedirs(out, exist_ok=True)
    for d, k, C, H, W in SHAPES:
        for L in LAYERS:
            for mode in ("f16", "q8"):
                name = f"d{d}_k{k}_c{C}_h{H}w{W}_L{L}_{mode}"
                if os.path.isdir(os.path.join(out, name + ".mlmodelc")):
                    continue
                m = ct.convert(program(d, k, C, H, W, L), convert_to="mlprogram",
                               minimum_deployment_target=ct.target.iOS18, compute_units=ct.ComputeUnit.CPU_ONLY)
                if mode == "q8":
                    rng = np.random.default_rng(0)
                    data = [{"x": rng.standard_normal((1, C, H, W)).astype(np.float16)} for _ in range(4)]
                    m = linear_quantize_activations(m, oc.OptimizationConfig(
                        global_config=OpActivationLinearQuantizerConfig(mode="linear_symmetric")), data)
                    m = oc.linear_quantize_weights(m, oc.OptimizationConfig(
                        global_config=oc.OpLinearQuantizerConfig(mode="linear_symmetric", dtype="int8")))
                pkg = os.path.join(out, name + ".mlpackage")
                m.save(pkg)
                subprocess.run(["xcrun", "coremlcompiler", "compile", pkg, out], check=True, capture_output=True)
                subprocess.run(["rm", "-rf", pkg])
                print("built", name, flush=True)
