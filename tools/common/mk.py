# 生成一个 3 层 1x1 卷积 + relu 的小模型（64 通道，64x64），用于观察编译产物
import torch  # 必须先于 coremltools 导入
import numpy as np
import coremltools as ct
from coremltools.converters.mil import Builder as mb
from coremltools.converters.mil.mil import types

C, H, W = 64, 64, 64
rng = np.random.default_rng(0)

@mb.program(input_specs=[mb.TensorSpec(shape=(1, C, H, W), dtype=types.fp16)],
            opset_version=ct.target.iOS18)
def prog(x):
    for i in range(3):
        w = (rng.standard_normal((C, C, 1, 1)) * 0.05).astype(np.float16)
        b = (rng.standard_normal((C,)) * 0.05).astype(np.float16)
        x = mb.conv(x=x, weight=w, bias=b, name=f"conv{i}")
        x = mb.relu(x=x, name=f"relu{i}")
    return x

m = ct.convert(prog, convert_to="mlprogram", minimum_deployment_target=ct.target.iOS18,
               compute_units=ct.ComputeUnit.CPU_AND_NE)
m.save("conv3.mlpackage")
print("saved")
