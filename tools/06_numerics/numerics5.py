"""ANE 数值（五）：bias 在哪里加（H11）；小于 LSB 的乘积怎么舍入，和权重、输入是否为非规格化数的关系（H12）。

用法：./anewho python numerics5.py <输出目录>
方法同 numerics3：1×1 卷积，输出通道补到 2048，后接陪跑支路让模型留在 ANE 上；只读第 0 个输出通道。
"""
import os as _os, sys as _sys  # 仓库里按目录存放、部署到 M6 时平铺：两种布局都能找到公共模块
_here = _os.path.dirname(_os.path.abspath(__file__))
_sys.path[:0] = [_here, _os.path.join(_here, "..", "lib"), _os.path.join(_here, "..", "common")]
import json
import os
import sys

import torch  # noqa: F401
import numpy as np
import coremltools as ct
from coremltools.converters.mil import Builder as mb
from coremltools.converters.mil.mil import types

sys.argv = [sys.argv[0], sys.argv[1] if len(sys.argv) > 1 else "numerics5_out"]
import numerics3 as n3  # noqa: E402  复用 sidecar / save

OUT = sys.argv[1]
CIN, W = n3.CIN, n3.W
LSB = 2.0 ** -16


def conv_bias(wvec, bias, name):
    """第 0 个输出通道：权重 wvec（长 CIN）、bias；其余输出通道为 0。"""
    wt = np.zeros((2048, CIN, 1, 1), np.float16)
    wt[0, :, 0, 0] = wvec
    b = np.zeros(2048, np.float16)
    b[0] = bias

    @mb.program(input_specs=[mb.TensorSpec(shape=(1, CIN, 1, W), dtype=types.fp16)], opset_version=ct.target.iOS18)
    def p(x):
        y = mb.conv(x=x, weight=wt, bias=b, name="y")
        return y, n3.sidecar(y, 2048)
    return n3.save(p, name)


def run_cols(mm, cols):
    """cols：每列一组输入（长度 ≤ CIN 的列表），返回 ANE、CPU 的第 0 通道输出。"""
    x = np.zeros((CIN, W), np.float16)
    for j, c in enumerate(cols):
        x[:len(c), j] = c
    f = lambda m: np.asarray(m.predict({"x": x.reshape(1, CIN, 1, W)})["y"])[0, 0, 0, :len(cols)].astype(np.float64)
    return f(mm[0]), f(mm[1])


def main():
    R = {}

    # H11：bias。权重全为 1，第 0 通道输出 = Σx + bias
    ones = np.ones(CIN, np.float16)
    BIAS_CASES = {
        -16384.0: [[16384, 16384], [16384], [0], [32752], [16384, 16384, 16384]],
        32.0: [[32752], [32736], [0], [16384, 16368]],
        2.0 ** -20: [[0], [2.0 ** -16], [2.0 ** -17]],
        2.0 ** -17: [[0], [2.0 ** -17], [2.0 ** -16]],
        2.0 ** -12: [[0], [1.0], [2.0 ** -16]],
        1000.3: [[0], [0.25], [2.0 ** -16]],
        -1.0: [[1.0], [0.5], [2.0 ** -17]],
    }
    for bias, cols in BIAS_CASES.items():
        mm = conv_bias(ones, bias, f"bias_{bias:g}")
        a, c = run_cols(mm, cols)
        R[f"bias={bias:g}（fp16 {float(np.float16(bias))!r}）"] = [
            [" + ".join(f"{v:g}" for v in col), ai, ci] for col, ai, ci in zip(cols, a, c)]

    # H12：单个乘积 p = x·w，p 取 0.25 / 0.5 / 0.75 / 1 / 1.5 / 2.5 LSB 及其负数；w 从 2^-12 扫到 2^4，再加几个非 2 的幂
    fracs = [0.25, 0.5, 0.75, 1.0, 1.5, 2.5, 3.5, -0.5, -1.5, -2.5]
    ws = [2.0 ** k for k in range(-12, 5)] + [0.75, 1.5, 3.0, 0.375]
    for wv in ws:
        wvec = np.zeros(CIN, np.float16)
        wvec[0] = wv
        mm = conv_bias(wvec, 0.0, f"lsb_w{wv:g}")
        cols, meta = [], []
        for fr in fracs:
            x = np.float16(fr * LSB / wv)
            cols.append([x])
            meta.append((fr, float(x), float(x) * wv / LSB, abs(float(x)) < 2.0 ** -14))
        a, c = run_cols(mm, cols)
        R[f"w={wv:g}"] = [[f"{fr:g} LSB", xv, f"实际 {pl:g} LSB", "x 非规格化" if sub else "x 规格化",
                          ai / LSB, ci / LSB] for (fr, xv, pl, sub), ai, ci in zip(meta, a, c)]

    with open(os.path.join(OUT, "numerics5.json"), "w") as f:
        json.dump(R, f, ensure_ascii=False, indent=1)
    for k, rows in R.items():
        print("==", k)
        for r in rows:
            print("   ", *[f"{v!r:>14}" if isinstance(v, float) else f"{v:>14}" for v in r])


if __name__ == "__main__":
    main()
