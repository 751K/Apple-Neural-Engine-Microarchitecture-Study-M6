"""寄存器 0x1240（权重配置字）实验的模型：c1x1、512 通道、1×128、共享权重；稠密随机、稠密但 50–100% 为 0、剪枝、W8、4 位调色板。
用法：python kfmt_gen.py <输出目录>（coremltools 9.0；用 ct.utils.compile_model 编译，不需要 Xcode）
"""
import os, subprocess, sys
import numpy as np
import coremltools as ct
import coremltools.optimize.coreml as cto
from coremltools.converters.mil import Builder as mb
from coremltools.converters.mil.mil import types
out = sys.argv[1]
C, H, W = 512, 1, 128
def wgen(zero_frac):
    w = np.random.default_rng(0).standard_normal((C, C, 1, 1)).astype(np.float32) * np.sqrt(2.0 / C)
    if zero_frac >= 1: return np.zeros_like(w)
    if zero_frac > 0:
        t = np.quantile(np.abs(w), zero_frac); w = np.where(np.abs(w) > t, w, 0)
        w *= 1 / np.sqrt(1 - zero_frac) ** 0.5
    return w
def prog(w, L):
    @mb.program(input_specs=[mb.TensorSpec(shape=(1, C, H, W), dtype=types.fp16)], opset_version=ct.target.iOS18)
    def p(x):
        k = mb.const(val=w.astype(np.float16)); b = mb.const(val=np.zeros(C, np.float16))
        for _ in range(L): x = mb.relu(x=mb.conv(x=x, weight=k, bias=b))
        return x
    return p
V = {"dense": (0, None), "dz50": (0.5, None), "dz75": (0.75, None), "dz90": (0.9, None), "dz100": (1.0, None),
     "s75": (0, cto.OpMagnitudePrunerConfig(target_sparsity=0.75)),
     "w8": (0, cto.OpLinearQuantizerConfig(mode="linear_symmetric", dtype="int8", granularity="per_channel")),
     "p4": (0, cto.OpPalettizerConfig(mode="uniform", nbits=4))}
for v, (zf, cfg) in V.items():
    for L in (32, 128):
        n = f"c1x1_{v}_L{L}"
        if os.path.isdir(f"{out}/{n}.mlmodelc"): continue
        m = ct.convert(prog(wgen(zf), L), convert_to="mlprogram", minimum_deployment_target=ct.target.iOS18,
                       compute_units=ct.ComputeUnit.CPU_AND_NE, skip_model_load=True)
        if cfg is not None:
            oc = cto.OptimizationConfig(global_config=cfg)
            m = (cto.prune_weights if v == "s75" else cto.linear_quantize_weights if v == "w8" else cto.palettize_weights)(m, config=oc)
        m.save(f"{out}/{n}.mlpackage")
        import shutil; shutil.move(ct.utils.compile_model(f"{out}/{n}.mlpackage"), f"{out}/{n}.mlmodelc")
        ops = open(f"{out}/{n}.mlmodelc/model.mil").read()
        print(n, "constexpr" if "constexpr" in ops else "plain const", flush=True)
