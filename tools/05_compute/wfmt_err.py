"""压缩格式的输出误差（默认 16 层模型，环境变量 L 指定层数；同一随机输入）。
  ane_vs_cpu：同一压缩模型在 CPU_AND_NE 与 CPU_ONLY 上输出的相对 L2 误差（检验 ANE 的解压是否正确）
  vs_fp16  ：压缩模型（CPU_ONLY）相对 FP16 原模型（CPU_ONLY）的相对 L2 误差（压缩本身的损失）
  cos      ：vs_fp16 对应的余弦相似度
用法：python wfmt_err.py [格式 ...]
"""
import sys
import numpy as np
import coremltools as ct

L = int(__import__("os").environ.get("L", 16))
FMTS = sys.argv[1:] or ["fp16", "w8", "p4", "w4c", "w4t", "p4o2", "p4o4"]
x = np.random.default_rng(42).standard_normal((1, 2048, 1, 32)).astype(np.float16)


def run(fmt, cu):
    m = ct.models.CompiledMLModel(f"models/m2048_{fmt}_L{L}.mlmodelc", compute_units=cu)
    out = m.predict({"x": x})
    return np.asarray(next(iter(out.values())), np.float32)


rel = lambda a, b: float(np.linalg.norm(a - b) / np.linalg.norm(b))
ref = run("fp16", ct.ComputeUnit.CPU_ONLY)
print(f"{'格式':6s} {'ane_vs_cpu':>11s} {'vs_fp16':>9s} {'cos':>8s}  输出范数")
for f in FMTS:
    cpu = run(f, ct.ComputeUnit.CPU_ONLY)
    ane = run(f, ct.ComputeUnit.CPU_AND_NE)
    cos = float((cpu * ref).sum() / np.linalg.norm(cpu) / np.linalg.norm(ref))
    print(f"{f:6s} {rel(ane, cpu):11.2e} {rel(cpu, ref):9.4f} {cos:8.5f}  {np.linalg.norm(cpu):.3g}", flush=True)
