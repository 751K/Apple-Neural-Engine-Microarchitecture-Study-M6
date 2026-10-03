"""把 chain.py 的模型做成 W8A8（激活和权重都量化为 int8），或只量化权重（W8）。

用法（M6）：python w8a8.py <输出目录> <名字> [<名字> ...]
名字 = chain.py 的名字 + "_q8"（W8A8）或 "_w8"（只量化权重，激活仍为 fp16）。
"""
import os as _os, sys as _sys  # 仓库里按目录存放、部署到 M6 时平铺：两种布局都能找到公共模块
_here = _os.path.dirname(_os.path.abspath(__file__))
_sys.path[:0] = [_here, _os.path.join(_here, "..", "lib"), _os.path.join(_here, "..", "common")]
import os
import subprocess
import sys

import torch  # noqa: F401
import numpy as np
import coremltools as ct
import coremltools.optimize.coreml as oc
from coremltools.optimize.coreml.experimental import OpActivationLinearQuantizerConfig, linear_quantize_activations

from chain import PAT, program

if __name__ == "__main__":
    out = sys.argv[1]
    os.makedirs(out, exist_ok=True)
    for name in sys.argv[2:]:
        if os.path.isdir(os.path.join(out, name + ".mlmodelc")):
            continue
        base, mode = name[:-3], name[-2:]
        k, C, H, W, L, u = PAT.match(base).groups()
        m = ct.convert(program(int(k), int(C), int(H), int(W), int(L), bool(u)), convert_to="mlprogram",
                       minimum_deployment_target=ct.target.iOS18,
                       # 校准只需要在 CPU 上跑；用 CPU_AND_NE 加载会触发 ANE 编译，384 层要好几分钟。
                       # 运行时的计算单元由 bondrun 的 MLModelConfiguration 决定，不受这里影响。
                       compute_units=ct.ComputeUnit.CPU_ONLY)
        if mode == "q8":
            rng = np.random.default_rng(0)
            data = [{"x": rng.standard_normal((1, int(C), int(H), int(W))).astype(np.float16)} for _ in range(4)]
            acfg = oc.OptimizationConfig(global_config=OpActivationLinearQuantizerConfig(mode="linear_symmetric"))
            m = linear_quantize_activations(m, acfg, data)
        wcfg = oc.OptimizationConfig(global_config=oc.OpLinearQuantizerConfig(mode="linear_symmetric", dtype="int8"))
        m = oc.linear_quantize_weights(m, wcfg)
        pkg = os.path.join(out, name + ".mlpackage")
        m.save(pkg)
        subprocess.run(["xcrun", "coremlcompiler", "compile", pkg, out], check=True, capture_output=True)
        subprocess.run(["rm", "-rf", pkg])
        print("built", name, flush=True)
