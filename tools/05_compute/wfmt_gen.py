"""权重格式实验（wfmt）的模型：同一份 FP16 基准权重，用 MIL 的 constexpr 运算直接构造各种压缩格式。

用法（M6，coremltools 环境，不需要 torch）：python wfmt_gen.py <输出目录> [名字 ...]（不给名字则生成全部）
名字：<形状>_<格式>_L<层数>
  形状  m2048：1×1 卷积，2048 → 2048 通道，输入 1×2048×1×32，各层权重不同（每层 FP16 8 MB）
        k1x9：1×9 卷积，256 通道，输入 1×256×4×32，各层共享一份权重（d2_wbound 的主测模型）
  格式  fp16      不压缩
        w8        int8，每个输出通道一个缩放（constexpr_blockwise_shift_scale）
        w4        int4，沿输入通道每 32 个一块，一块一个缩放
        p6/p4/p3/p2  整个张量一张调色板，2^n 个值（constexpr_lut_to_dense），值取均匀分布的分位点
        p4g16     每 16 个输出通道一张 16 值调色板（分组调色板）
        p4v2      16 个二维向量的调色板，沿输入通道两个一组（向量调色板，每个权重 2 位）
        p4v4      16 个四维向量的调色板（每个权重 1 位）
每个模型另存 <名字>.ref.npz：同一随机输入下 FP16 计算（numpy）的输出不在这里算，误差由 wfmt_err.py 用 Core ML 比较。
"""
import os
import subprocess
import sys

import numpy as np
import coremltools as ct
from coremltools.converters.mil import Builder as mb
from coremltools.converters.mil.mil import types

SHAPES = {
    "m2048": dict(C=2048, H=1, W=32, k=(1, 1), shared=False),
    "k1x9": dict(C=256, H=4, W=32, k=(1, 9), shared=True),
}
FORMATS = ["fp16", "w8", "w4", "p6", "p4", "p3", "p2", "p4g16", "p4v2", "p4v4"]
ALL = [f"m2048_{f}_L{L}" for f in FORMATS for L in (16, 32)] + [f"k1x9_{f}_L{L}" for f in ("fp16", "w8") for L in (40, 80)]
IDX = {1: types.np_uint1_dtype, 2: types.np_uint2_dtype, 3: types.np_uint3_dtype, 4: types.np_uint4_dtype,
       6: types.np_uint6_dtype, 8: np.uint8}


def base_weight(rng, C, k):
    return (rng.standard_normal((C, C, *k)) * np.sqrt(2.0 / (C * k[0] * k[1]))).astype(np.float16)


def lut_tensor(w, n):
    """整个张量一张 2^n 值的调色板：取均匀分位点，最近值索引。返回 (indices, lut[1,1,1,1,2^n,1])。"""
    flat = w.astype(np.float32).ravel()
    lut = np.quantile(flat, (np.arange(2 ** n) + 0.5) / 2 ** n).astype(np.float32)
    mid = (lut[1:] + lut[:-1]) / 2
    idx = np.searchsorted(mid, w.astype(np.float32)).astype(np.uint8)
    return idx, lut.astype(np.float16).reshape(1, 1, 1, 1, -1, 1)


def weight_op(w, fmt):
    """返回一个 MIL 变量：解压后的 FP16 权重（形状与 w 相同）。"""
    Co, Ci = w.shape[:2]
    w32 = w.astype(np.float32)
    if fmt == "fp16":
        return mb.const(val=w)
    if fmt == "w8":
        s = np.abs(w32).reshape(Co, -1).max(1) / 127 + 1e-12
        q = np.clip(np.round(w32 / s.reshape(Co, 1, 1, 1)), -127, 127).astype(np.int8)
        return mb.constexpr_blockwise_shift_scale(data=q, scale=s.astype(np.float16).reshape(Co, 1, 1, 1))
    if fmt == "w4":
        B = 32
        g = w32.reshape(Co, Ci // B, B, *w.shape[2:])
        s = np.abs(g).max(axis=(2, 3, 4)) / 7 + 1e-12                       # [Co, Ci/B]
        q = np.clip(np.round(g / s[:, :, None, None, None]), -7, 7).reshape(w.shape).astype(np.int8)
        return mb.constexpr_blockwise_shift_scale(data=q.astype(types.np_int4_dtype),
                                                  scale=s.astype(np.float16).reshape(Co, Ci // B, 1, 1))
    if fmt in ("p6", "p4", "p3", "p2"):
        n = int(fmt[1])
        idx, lut = lut_tensor(w, n)
        return mb.constexpr_lut_to_dense(indices=idx.astype(IDX[n]), lut=lut)
    if fmt == "p4g16":
        G = 16
        idx = np.empty(w.shape, np.uint8)
        luts = np.empty((Co // G, 1, 1, 1, 16, 1), np.float16)
        for g in range(Co // G):
            i, l = lut_tensor(w[g * G:(g + 1) * G], 4)
            idx[g * G:(g + 1) * G] = i
            luts[g] = l[0]
        return mb.constexpr_lut_to_dense(indices=idx.astype(types.np_uint4_dtype), lut=luts)
    if fmt in ("p4v2", "p4v4"):
        V = int(fmt[-1])
        # 沿输入通道（轴 1）V 个一组成向量；16 个码字取自数据中随机的 16 个向量，按最近距离分配
        vec = np.moveaxis(w32, 1, -1).reshape(-1, V)                      # [Co*kh*kw*Ci/V, V]
        rng = np.random.default_rng(1)
        code = vec[rng.choice(len(vec), 16, replace=False)]
        best = np.zeros(len(vec), np.uint8)
        bestd = np.full(len(vec), np.inf, np.float32)
        for c in range(16):
            dd = ((vec - code[c]) ** 2).sum(1)
            m = dd < bestd
            best[m], bestd[m] = c, dd[m]
        kh, kw = w.shape[2:]
        idx = np.moveaxis(best.reshape(Co, kh, kw, Ci // V), -1, 1)       # [Co, Ci/V, kh, kw]
        return mb.constexpr_lut_to_dense(indices=idx.astype(types.np_uint4_dtype),
                                         lut=code.astype(np.float16).reshape(1, 1, 1, 1, 16, V), vector_axis=1)
    raise ValueError(fmt)


def program(name):
    shape, fmt, L = name.split("_")
    L = int(L[1:])
    sp = SHAPES[shape]
    C, H, W, k = sp["C"], sp["H"], sp["W"], sp["k"]
    rng = np.random.default_rng(0)

    @mb.program(input_specs=[mb.TensorSpec(shape=(1, C, H, W), dtype=types.fp16)], opset_version=ct.target.iOS18)
    def p(x):
        shared = weight_op(base_weight(rng, C, k), fmt) if sp["shared"] else None
        b = mb.const(val=np.zeros(C, np.float16))
        for _ in range(L):
            w_ = shared if sp["shared"] else weight_op(base_weight(rng, C, k), fmt)
            x = mb.relu(x=mb.conv(x=x, weight=w_, bias=b, pad_type="same"))
        return x
    return p


if __name__ == "__main__":
    out = sys.argv[1]
    os.makedirs(out, exist_ok=True)
    for name in sys.argv[2:] or ALL:
        if os.path.isdir(os.path.join(out, name + ".mlmodelc")):
            continue
        try:
            m = ct.convert(program(name), convert_to="mlprogram", minimum_deployment_target=ct.target.iOS18,
                           compute_units=ct.ComputeUnit.CPU_AND_NE)
            pkg = os.path.join(out, name + ".mlpackage")
            m.save(pkg)
            subprocess.run(["xcrun", "coremlcompiler", "compile", pkg, out], check=True, capture_output=True)
            print("built", name, flush=True)
        except Exception as e:  # 记录失败本身也是结果
            print("FAILED", name, type(e).__name__, str(e)[:300], flush=True)
