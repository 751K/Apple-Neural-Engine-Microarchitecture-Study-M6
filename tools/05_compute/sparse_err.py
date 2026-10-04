"""稀疏实验的输出误差：同一个（已剪枝的）模型、同一份随机输入，ANE（CPU_AND_NE）与 CPU（CPU_ONLY）的输出对比。
剪枝本身就会改变结果，这里只确认 ANE 执行剪枝模型与 CPU 执行同一模型一致。

用法（M6，coremltools 环境）：python sparse_err.py <sparse 目录> [名字 ...]（默认所有 L16 模型）
列：输出均方根（CPU）、最大绝对误差 ÷ 输出均方根、误差均方根 ÷ 输出均方根。
"""
import glob
import os
import sys

import numpy as np
import coremltools as ct

d = sys.argv[1]
names = sys.argv[2:] or sorted(os.path.basename(p)[:-9] for p in glob.glob(os.path.join(d, "*_L16.mlmodelc")))
print(f"{'模型':>18} {'输出 RMS':>9} {'最大误差/RMS':>12} {'误差 RMS/RMS':>12}")
for n in names:
    path = os.path.join(d, n + ".mlmodelc")
    desc = ct.utils.load_spec(os.path.join(d, n + ".mlpackage")).description.input[0]   # 输入名和形状
    x = np.random.default_rng(3).uniform(-1, 1, tuple(desc.type.multiArrayType.shape)).astype(np.float16)
    ys = []
    for cu in (ct.ComputeUnit.CPU_ONLY, ct.ComputeUnit.CPU_AND_NE):
        out = ct.models.CompiledMLModel(path, compute_units=cu).predict({desc.name: x})
        ys.append(np.asarray(list(out.values())[0], np.float32))
    ref, ane = ys
    rms = np.sqrt((ref ** 2).mean())
    e = ane - ref
    print(f"{n:>18} {rms:9.4f} {np.abs(e).max() / rms:12.4f} {np.sqrt((e ** 2).mean()) / rms:12.4f}", flush=True)
