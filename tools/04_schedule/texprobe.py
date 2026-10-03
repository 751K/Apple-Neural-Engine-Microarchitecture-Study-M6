"""试几种"纹理类"操作，看哪种会被 Core ML 放到 ANE 上（每个 16 步链，形状 [1, 512, 1, 128]）。
用法：python texprobe.py <输出目录> <名字>"""
import os, subprocess, sys
import torch  # noqa: F401
import numpy as np
import coremltools as ct
from coremltools.converters.mil import Builder as mb
from coremltools.converters.mil.mil import types

C, W, L = 512, 128, 16
out, name = sys.argv[1], sys.argv[2]
idx = np.random.default_rng(0).permutation(W).astype(np.int32)


def step(y):
    if name == "tp_resize_default":
        y = mb.resize_bilinear(x=y, target_size_height=1, target_size_width=160, sampling_mode="DEFAULT")
        return mb.resize_bilinear(x=y, target_size_height=1, target_size_width=W, sampling_mode="DEFAULT")
    if name == "tp_upsample":
        y = mb.upsample_bilinear(x=y, scale_factor_height=1, scale_factor_width=2, align_corners=False)
        return mb.avg_pool(x=y, kernel_sizes=[1, 2], strides=[1, 2], pad_type="valid")
    if name == "tp_upsample_nn":
        y = mb.upsample_nearest_neighbor(x=y, scale_factor_height=1, scale_factor_width=2)
        return mb.max_pool(x=y, kernel_sizes=[1, 2], strides=[1, 2], pad_type="valid")
    if name == "tp_gather":
        return mb.gather(x=y, indices=idx, axis=3)
    if name == "tp_crop_resize":
        y = mb.reshape(x=y, shape=[1, C, 1, W])
        return mb.resize(x=y, shape=[1, W], resized_dims=2, interpolation_mode="LINEAR", sampling_mode="DEFAULT") if hasattr(mb, "resize") else y
    raise ValueError(name)


@mb.program(input_specs=[mb.TensorSpec(shape=(1, C, 1, W), dtype=types.fp16)], opset_version=ct.target.iOS18)
def p(x):
    for _ in range(L):
        x = step(x)
    return x


m = ct.convert(p, convert_to="mlprogram", minimum_deployment_target=ct.target.iOS18,
               compute_units=ct.ComputeUnit.CPU_AND_NE, skip_model_load=True)
pkg = os.path.join(out, name + ".mlpackage")
m.save(pkg)
subprocess.run(["xcrun", "coremlcompiler", "compile", pkg, out], check=True, capture_output=True)
subprocess.run(["rm", "-rf", pkg])
print("built", name)
