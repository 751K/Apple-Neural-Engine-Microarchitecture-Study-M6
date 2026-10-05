"""TD 字段动态跟踪（tdtrace）用的小模型：每个模型 2 层，尽量覆盖编译器生成 TD 时会走到的不同分支。

用法：python tdtrace_gen.py <输出目录> [名字 ...]（coremltools；没有 Xcode 时用 ct.utils.compile_model 编译）
稀疏、调色板、W8 直接用 MIL 的 constexpr 运算构造，不经过 coremltools.optimize。
"""
import os
import shutil
import subprocess
import sys

import numpy as np
import coremltools as ct
from coremltools.converters.mil import Builder as mb
from coremltools.converters.mil.mil import types

rng = np.random.default_rng(0)
F16 = np.float16


def w(*s, scale=None):
    fan = int(np.prod(s[1:])) if len(s) > 1 else s[0]
    return (rng.standard_normal(s) * (scale or np.sqrt(2.0 / fan))).astype(F16)


def conv(x, C, k=(1, 1), act="relu", **kw):
    x = mb.conv(x=x, weight=mb.const(val=w(C, C // kw.get("groups", 1), *k)), bias=mb.const(val=np.zeros(C, F16)),
                pad_type=kw.pop("pad_type", "same"), **kw)
    return getattr(mb, act)(x=x) if act else x


def sparse_w(C, frac):
    wt = w(C, C, 1, 1).astype(np.float32)
    t = np.quantile(np.abs(wt), frac)
    mask = np.abs(wt) > t
    return mb.constexpr_sparse_to_dense(nonzero_data=wt[mask].astype(F16), mask=mask.astype(types.np_uint1_dtype))


def lut_w(C, n, groups=1):
    wt = w(C, C, 1, 1).astype(np.float32)
    G = C // groups
    idx = np.empty(wt.shape, np.uint8)
    lut = np.empty((groups, 1, 1, 1, 2 ** n, 1), F16)
    for g in range(groups):
        s = wt[g * G:(g + 1) * G]
        q = np.quantile(s, (np.arange(2 ** n) + 0.5) / 2 ** n)
        idx[g * G:(g + 1) * G] = np.searchsorted((q[1:] + q[:-1]) / 2, s)
        lut[g, ..., 0] = q
    dt = {2: types.np_uint2_dtype, 4: types.np_uint4_dtype, 6: types.np_uint6_dtype}[n]
    return mb.constexpr_lut_to_dense(indices=idx.astype(dt), lut=lut)


def w8_w(C):
    wt = w(C, C, 1, 1).astype(np.float32)
    s = np.abs(wt).reshape(C, -1).max(1) / 127
    q = np.round(wt / s.reshape(C, 1, 1, 1)).astype(np.int8)
    return mb.constexpr_blockwise_shift_scale(data=q, scale=s.astype(F16).reshape(C, 1, 1, 1))


def body(name, x, x2):
    C = x.shape[1]
    if name == "conv1x1":       return conv(conv(x, C), C)
    if name == "conv3x3":       return conv(conv(x, C, (3, 3)), C, (3, 3))
    if name == "conv3x3_dil":   return conv(conv(x, C, (3, 3), dilations=[2, 2]), C, (3, 3), dilations=[2, 2])
    if name == "conv1x9":       return conv(conv(x, C, (1, 9)), C, (1, 9))
    if name == "conv5x5":       return conv(conv(x, C, (5, 5)), C, (5, 5))
    if name == "conv_s2":       return conv(conv(x, C, (3, 3), strides=[2, 2]), C, (3, 3))
    if name == "dwconv":        return conv(conv(x, C, (3, 3), groups=C), C, (3, 3), groups=C)
    if name == "gconv":         return conv(conv(x, C, (3, 3), groups=4), C, (3, 3), groups=4)
    if name == "conv_noact":    return conv(conv(x, C, act=None), C, act=None)
    if name == "conv_sigmoid":  return conv(conv(x, C, act="sigmoid"), C, act="sigmoid")
    if name == "conv_tanh":     return conv(conv(x, C, act="tanh"), C, act="tanh")
    if name == "conv_gelu":     return mb.gelu(x=conv(mb.gelu(x=conv(x, C, act=None)), C, act=None))
    if name == "deconv":
        y = mb.conv_transpose(x=x, weight=mb.const(val=w(C, C, 2, 2)), strides=[2, 2])
        return conv(y, C)
    if name == "bn":            return mb.relu(x=mb.add(x=mb.mul(x=conv(x, C, act=None), y=w(1, C, 1, 1)), y=w(1, C, 1, 1)))
    if name in ("sparse50", "sparse90"):
        k = sparse_w(C, 0.5 if name == "sparse50" else 0.9)
        b = mb.const(val=np.zeros(C, F16))
        return mb.relu(x=mb.conv(x=mb.relu(x=mb.conv(x=x, weight=k, bias=b)), weight=k, bias=b))
    if name in ("pal4", "pal2", "pal4g"):
        k = lut_w(C, 2 if name == "pal2" else 4, groups=8 if name == "pal4g" else 1)
        return mb.relu(x=mb.conv(x=mb.relu(x=mb.conv(x=x, weight=k)), weight=k))
    if name == "w8":
        k = w8_w(C)
        return mb.relu(x=mb.conv(x=mb.relu(x=mb.conv(x=x, weight=k)), weight=k))
    if name == "w8a8":
        k = w8_w(C)
        y = x
        for _ in range(2):
            q = mb.quantize(input=y, scale=F16(0.02), output_dtype="int8")
            y = mb.relu(x=mb.conv(x=mb.dequantize(input=q, scale=F16(0.02)), weight=k))
        return y
    if name == "linear":        return mb.relu(x=mb.linear(x=mb.relu(x=mb.linear(x=x, weight=w(C, C))), weight=w(C, C)))
    if name == "matmul2":       return mb.matmul(x=mb.matmul(x=x, y=x2), y=x2)
    if name == "add2":          return mb.relu(x=mb.add(x=mb.add(x=x, y=x2), y=x2))
    if name == "mul2":          return mb.mul(x=mb.mul(x=x, y=x2), y=x2)
    if name == "maxpool":       return mb.max_pool(x=mb.max_pool(x=x, kernel_sizes=[2, 2], strides=[2, 2], pad_type="valid"), kernel_sizes=[2, 2], strides=[2, 2], pad_type="valid")
    if name == "avgpool":       return mb.avg_pool(x=mb.avg_pool(x=x, kernel_sizes=[3, 3], strides=[1, 1], pad_type="same"), kernel_sizes=[3, 3], strides=[1, 1], pad_type="same")
    if name == "reduce_mean":   return conv(mb.reduce_mean(x=conv(x, C), axes=[2, 3], keep_dims=True), C)
    if name == "softmax":       return mb.softmax(x=mb.softmax(x=x, axis=1), axis=1)
    if name == "layernorm":     return mb.layer_norm(x=mb.layer_norm(x=x, axes=[1]), axes=[1])
    if name == "concat":        return conv(mb.concat(values=[x, x2], axis=1), 2 * C)
    if name == "transpose":     return conv(mb.transpose(x=conv(x, C), perm=[0, 1, 3, 2]), C)
    if name == "pad":           return conv(mb.pad(x=conv(x, C), pad=[0, 0, 0, 0, 1, 1, 1, 1], mode="reflect"), C, pad_type="valid")
    if name == "upsample":      return conv(mb.upsample_nearest_neighbor(x=conv(x, C), scale_factor_height=2, scale_factor_width=2), C)
    if name == "bonded":        return conv(conv(x, C), C)
    raise KeyError(name)


SHAPE = {"bonded": (512, 64, 64), "linear": None, "matmul2": None, "softmax": (128, 1, 256), "layernorm": (128, 1, 256)}
TWO = {"matmul2", "add2", "mul2", "concat"}
ALL = ["conv1x1", "conv3x3", "conv3x3_dil", "conv1x9", "conv5x5", "conv_s2", "dwconv", "gconv", "conv_noact",
       "conv_sigmoid", "conv_tanh", "conv_gelu", "deconv", "bn", "sparse50", "sparse90", "pal4", "pal2", "pal4g", "w8",
       "w8a8", "linear", "matmul2", "add2", "mul2", "maxpool", "avgpool", "reduce_mean", "softmax", "layernorm",
       "concat", "transpose", "pad", "upsample", "bonded"]


def program(name):
    if name == "linear":
        specs = [mb.TensorSpec(shape=(64, 256), dtype=types.fp16)]
    elif name == "matmul2":
        specs = [mb.TensorSpec(shape=(1, 4, 64, 64), dtype=types.fp16), mb.TensorSpec(shape=(1, 4, 64, 64), dtype=types.fp16)]
    else:
        C, H, W = SHAPE.get(name) or (128, 16, 16)
        specs = [mb.TensorSpec(shape=(1, C, H, W), dtype=types.fp16) for _ in range(2 if name in TWO else 1)]

    if len(specs) == 2:
        @mb.program(input_specs=specs, opset_version=ct.target.iOS18)
        def p(x, y):
            return body(name, x, y)
    else:
        @mb.program(input_specs=specs, opset_version=ct.target.iOS18)
        def p(x):
            return body(name, x, None)
    return p


if __name__ == "__main__":
    out = sys.argv[1]
    os.makedirs(out, exist_ok=True)
    for name in sys.argv[2:] or ALL:
        if os.path.isdir(os.path.join(out, name + ".mlmodelc")):
            continue
        try:
            m = ct.convert(program(name), convert_to="mlprogram", minimum_deployment_target=ct.target.iOS18,
                           compute_units=ct.ComputeUnit.CPU_AND_NE, skip_model_load=True)
            pkg = os.path.join(out, name + ".mlpackage")
            m.save(pkg)
            if subprocess.run(["xcrun", "--find", "coremlcompiler"], capture_output=True).returncode == 0:
                subprocess.run(["xcrun", "coremlcompiler", "compile", pkg, out], check=True, capture_output=True)
            else:
                shutil.move(ct.utils.compile_model(pkg), os.path.join(out, name + ".mlmodelc"))
            print("built", name, flush=True)
        except Exception as e:
            print("FAILED", name, type(e).__name__, str(e)[:200], flush=True)
