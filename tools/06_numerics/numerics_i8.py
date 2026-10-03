"""ANE 数值（七）：int8（W8A8）卷积的累加器位宽与溢出行为。

用法（M6）：[I8_ROUND=2] ./anewho python numerics_i8.py <输出目录>（第 1 轮 S ≤ 2^28，第 2 轮 S 到 2^31（N ≥ 120000 时退回 CPU，无效），第 3 轮用 kh×1 卷积让 S 达到 2^31）
方法：手写 quantize → dequantize → conv（权重为 int8 常量 + 缩放），不经校准，缩放完全可控。
  输入 x 全部 = 127·sx（量化后恰为 int8 127），权重全部为 int8 127（缩放 sw），1×1 卷积，输入通道 N。
  整数累加和 S = N·127·127 = N·16129；输出（fp16）理论值 = S·sx·sw。
  sx = sw = 2^-k：k = 7 时输出 ≈ 0.98·N（远小于 32768，只看整数位宽）；k = 6 时 ≈ 3.94·N（N > 8323 时超过 32768，看是否有 fp16 路径的 ±32768 上限）。
  另有"正负抵消"用例：一半通道权重为 +127、一半为 −127，最终和为 0，但中间部分和很大，用来区分"中途溢出"与"只在结果处饱和"。
每个模型同时在 CPU_AND_NE、CPU_ONLY 上运行，输出写入 <输出目录>/results.json。
"""
import json
import os
import sys

import torch  # noqa: F401
import numpy as np
import coremltools as ct
from coremltools.converters.mil import Builder as mb
from coremltools.converters.mil.mil import types

OUT = sys.argv[1] if len(sys.argv) > 1 else "numerics_i8_out"
os.makedirs(OUT, exist_ok=True)
COUT, W = 256, 64


def build(N, k, mode):
    sx = sw = np.float32(2.0 ** -k)
    wq = np.full((COUT, N, 1, 1), 127, np.int8)
    if mode == "cancel":
        wq[:, N // 2:] = -127

    @mb.program(input_specs=[mb.TensorSpec(shape=(1, N, 1, W), dtype=types.fp16)], opset_version=ct.target.iOS18)
    def p(x):
        q = mb.quantize(input=x, scale=np.float16(sx), zero_point=np.int8(0), output_dtype="int8")
        xd = mb.dequantize(input=q, scale=np.float16(sx), zero_point=np.int8(0))
        wd = mb.constexpr_blockwise_shift_scale(data=wq, scale=np.full((COUT, 1, 1, 1), sw, np.float16))
        return mb.conv(x=xd, weight=wd, name="y")
    m = ct.convert(p, convert_to="mlprogram", minimum_deployment_target=ct.target.iOS18,
                   compute_units=ct.ComputeUnit.CPU_ONLY, skip_model_load=True)
    path = os.path.join(OUT, f"i8_N{N}_k{k}_{mode}.mlpackage")
    m.save(path)
    return path, float(sx)


def build_k(N, kh, k, mode, H=16, Wd=None):
    """竖向 kh×1 卷积：输入、权重全为 int8 −128（乘积 2^14），每个输出点 S = kh·N·2^14。"""
    sx = sw = np.float32(2.0 ** -k)
    wq = np.full((64, N, kh, 1), -128, np.int8)
    if mode == "alt":  # 奇数行权重取 +127，使最终和小、中间部分和大
        wq[:, :, 1::2, :] = 127

    Wd = Wd or W

    @mb.program(input_specs=[mb.TensorSpec(shape=(1, N, H, Wd), dtype=types.fp16)], opset_version=ct.target.iOS18)
    def p(x):
        q = mb.quantize(input=x, scale=np.float16(sx), zero_point=np.int8(0), output_dtype="int8")
        xd = mb.dequantize(input=q, scale=np.float16(sx), zero_point=np.int8(0))
        wd = mb.constexpr_blockwise_shift_scale(data=wq, scale=np.full((64, 1, 1, 1), sw, np.float16))
        return mb.conv(x=xd, weight=wd, pad_type="valid", name="y")
    m = ct.convert(p, convert_to="mlprogram", minimum_deployment_target=ct.target.iOS18,
                   compute_units=ct.ComputeUnit.CPU_ONLY, skip_model_load=True)
    path = os.path.join(OUT, f"i8k_N{N}_kh{kh}_k{k}_{mode}_h{H}w{Wd}.mlpackage")
    m.save(path)
    return path, float(sx)


def run(path, cu, N, sx):
    m = ct.models.MLModel(path, compute_units=cu)
    x = np.full((1, N, 1, W), 127 * sx, np.float16)
    y = np.asarray(m.predict({"x": x})["y"]).astype(np.float64)
    return float(y[0, 0, 0, 0]), float(y.min()), float(y.max())


CASES = {
    "1": ((7, (256, 512, 520, 521, 1024, 2048, 2080, 2082, 4096, 8192, 16384), "pos"),
          (6, (4096, 8192, 8320, 8330, 9000, 12000, 16384), "pos"),
          (7, (1024, 4096, 16384), "cancel"),
          (6, (16384,), "cancel")),
    # 第二轮：把整数和推到 2^30–2^31（int32 在 2^31 溢出），k = 8 使输出 ≈ 0.246·N 留在 fp16 范围内
    "2": ((8, (32768, 65536, 120000, 133000, 133200, 140000), "pos"),
          (8, (140000, 270000), "cancel")),
}
res = []
if os.environ.get("I8_ROUND") == "3":
    # 第三轮：N = 16384，kh×1 卷积，输入 / 权重全为 −128：S = kh·2^28；kh = 8 时 S = 2^31（int32 上限 + 1）
    kk = int(os.environ.get("I8_K", "8"))  # 缩放 2^-kk；kk = 9 时 S = 2^31 对应输出 8192，用来排除"输出值 32768 上限"的巧合
    for N, kh, mode, H, Wd in ((65536, 1, "neg", 4, 8), (65536, 2, "neg", 4, 8), (65536, 3, "neg", 4, 8), (65536, 3, "alt", 4, 8),
                               (16384, 8, "neg", 9, 8), (16384, 9, "neg", 9, 8)):
        path, sx = build_k(N, kh, kk, mode, H, Wd)
        if mode == "neg":
            S = kh * N * 16384
        else:
            S = ((kh + 1) // 2) * N * 16384 - (kh // 2) * N * 128 * 127
        exact = S * sx * sx
        xin = np.full((1, N, H, Wd), -128 * sx, np.float16)
        y = np.asarray(ct.models.MLModel(path, compute_units=ct.ComputeUnit.CPU_AND_NE).predict({"x": xin})["y"]).astype(np.float64)
        c = np.asarray(ct.models.MLModel(path, compute_units=ct.ComputeUnit.CPU_ONLY).predict({"x": xin})["y"]).astype(np.float64)
        res.append(dict(N=N, kh=kh, mode=mode, H=H, W=Wd, S=S, exact=exact, ane=[float(y.flat[0]), float(y.min()), float(y.max())], cpu=float(c.flat[0])))
        print(f"N={N} kh={kh} {mode:4s} S={S:>11d}（≈2^{np.log2(abs(S)):.3f}，int32 上限 2^31−1） 理论 {exact:10.3f} | ANE {y.flat[0]:10.3f}（{y.min():g}…{y.max():g}） | CPU {c.flat[0]:10.3f}", flush=True)
    json.dump(res, open(os.path.join(OUT, f"results_3_k{kk}.json"), "w"), indent=1)
    sys.exit(0)
for k, Ns, mode in CASES[os.environ.get("I8_ROUND", "1")]:
    for N in Ns:
        path, sx = build(N, k, mode)
        exact = (N * 16129 if mode == "pos" else 0) * sx * sx
        a = run(path, ct.ComputeUnit.CPU_AND_NE, N, sx)
        c = run(path, ct.ComputeUnit.CPU_ONLY, N, sx)
        r = dict(N=N, k=k, mode=mode, S=N * 16129, exact=exact, ane=a, cpu=c)
        res.append(r)
        print(f"k={k} {mode:6s} N={N:6d} S={N * 16129:>10d}（≈2^{np.log2(N * 16129):.2f}） 理论 {exact:10.3f} | ANE {a[0]:10.3f}（{a[1]:g}…{a[2]:g}） | CPU {c[0]:10.3f}", flush=True)
json.dump(res, open(os.path.join(OUT, f"results_{os.environ.get('I8_ROUND', '1')}.json"), "w"), indent=1)
