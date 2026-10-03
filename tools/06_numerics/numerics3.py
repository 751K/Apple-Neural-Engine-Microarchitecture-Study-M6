"""ANE 数值行为（三）：累加器刻度是否固定；逐元素运算（PE）的数值。

用法：./anewho python numerics3.py <输出目录>
"""
import json
import os
import sys

import torch  # noqa: F401
import numpy as np
import coremltools as ct
from coremltools.converters.mil import Builder as mb
from coremltools.converters.mil.mil import types

OUT = sys.argv[1] if len(sys.argv) > 1 else "numerics3_out"
os.makedirs(OUT, exist_ok=True)
CIN, W = 64, 256
rng = np.random.default_rng(1)
KW = dict(convert_to="mlprogram", minimum_deployment_target=ct.target.iOS18, compute_precision=ct.precision.FLOAT16)


def sidecar(y, cin):
    s0 = (rng.standard_normal((256, cin, 1, 1)) * 0.01).astype(np.float16)
    z = mb.relu(x=mb.conv(x=y, weight=s0))
    for _ in range(3):
        z = mb.relu(x=mb.conv(x=z, weight=(rng.standard_normal((256, 256, 1, 1)) * 0.05).astype(np.float16)))
    return mb.identity(x=z, name="z")


def save(p, name):
    m = ct.convert(p, compute_units=ct.ComputeUnit.CPU_AND_NE, **KW)
    m.save(os.path.join(OUT, name + ".mlpackage"))
    return m, ct.models.MLModel(os.path.join(OUT, name + ".mlpackage"), compute_units=ct.ComputeUnit.CPU_ONLY)


def conv_w(wval, name):
    wt = np.zeros((2048, CIN, 1, 1), np.float16)
    wt[0, 0, 0, 0] = wval

    @mb.program(input_specs=[mb.TensorSpec(shape=(1, CIN, 1, W), dtype=types.fp16)], opset_version=ct.target.iOS18)
    def p(x):
        y = mb.conv(x=x, weight=wt, name="y")
        return y, sidecar(y, 2048)
    return save(p, name)


def run_conv(mm, xs):
    x = np.zeros((CIN, W), np.float16)
    x[0, :len(xs)] = xs
    f = lambda m: np.asarray(m.predict({"x": x.reshape(1, CIN, 1, W)})["y"])[0, 0, 0, :len(xs)].astype(np.float64)
    return f(mm[0]), f(mm[1])


def main():
    R = {}

    # 1. 权重很大 / 很小时，累加器的 LSB 和溢出点是否随之移动
    for wv in (2.0 ** -12, 2.0 ** -4, 1.0, 16.0, 256.0, 4096.0):
        mm = conv_w(wv, f"w_{wv}")
        # 让乘积分别为 2^-14 … 2^-20 和 32752、32768
        prods = [2.0 ** -k for k in range(14, 21)] + [32752.0, 32768.0, 1.0]
        xs = [p / wv for p in prods]
        a, c = run_conv(mm, np.array(xs, np.float16))
        R[f"conv_w={wv}"] = [[f"x*w={p:g}", float(np.float16(x)), ai, ci] for p, x, ai, ci in zip(prods, xs, a, c)]

    # 2. 逐元素运算：两个输入 a、b（[1, 2048, 1, W]），y = op(a, b)
    ELT = {"add": mb.add, "mul": mb.mul, "sub": mb.sub}
    CASES = [  # (a, b)
        (2048, 1), (-2048, -1), (4096, 2), (1, 2 ** -11), (16384, 16384), (32752, 16), (65504, 0), (40000, 1),
        (2 ** -14, 0), (2 ** -15, 0), (2 ** -17, 0), (2 ** -20, 0), (2 ** -24, 0), (2 ** -12, 2 ** -12),
        (2 ** -7, 2 ** -10), (256, 256), (200, 200), (np.nan, 1), (np.inf, 1),
    ]
    for opn, op in ELT.items():
        @mb.program(input_specs=[mb.TensorSpec(shape=(1, 2048, 1, W), dtype=types.fp16),
                                 mb.TensorSpec(shape=(1, 2048, 1, W), dtype=types.fp16)], opset_version=ct.target.iOS18)
        def p(a, b):
            y = op(x=a, y=b, name="y")
            return y, sidecar(y, 2048)
        mm = save(p, f"elt_{opn}")
        A = np.zeros((1, 2048, 1, W), np.float16)
        B = np.zeros((1, 2048, 1, W), np.float16)
        for j, (av, bv) in enumerate(CASES):
            A[0, 0, 0, j], B[0, 0, 0, j] = av, bv
        f = lambda m: np.asarray(m.predict({"a": A, "b": B})["y"])[0, 0, 0, :len(CASES)].astype(np.float64)
        a, c = f(mm[0]), f(mm[1])
        R[f"elt_{opn}"] = [[f"{av:g},{bv:g}", ai, ci] for (av, bv), ai, ci in zip(CASES, a, c)]

    json.dump(R, open(os.path.join(OUT, "results.json"), "w"), indent=1, default=str)
    for k, v in R.items():
        print(f"== {k}  （用例 / ANE / CPU）")
        for row in v:
            print("   ", row)


if __name__ == "__main__":
    main()
