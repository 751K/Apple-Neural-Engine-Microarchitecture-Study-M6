"""ANE 数值行为测试（对应论文 §2.1 归约树、§5 数值）。

用法（M6，coremltools 环境）：./anewho python numerics.py <输出目录>
每个测试是一个 1×1 卷积：输入 x 为 [1, Cin, 1, W]，每个输出通道的权重是一种测试图样。
结果和"理论上的几种累加方式"对比。
"""
import json
import os
import sys

import torch  # noqa: F401
import numpy as np
import coremltools as ct
from coremltools.converters.mil import Builder as mb
from coremltools.converters.mil.mil import types

OUT = sys.argv[1] if len(sys.argv) > 1 else "numerics_out"
os.makedirs(OUT, exist_ok=True)
W = 64  # 空间宽度
# Core ML 会把单个小卷积放到 CPU 上。测试卷积后面接一条"陪跑"支路（3 层 conv+relu），
# 让整个模型够重、被放到 ANE；测试卷积的原始输出单独作为输出 y 读出。
# 同一个模型再用 CPU_ONLY 跑一遍作参照：两者不同，说明测试卷积确实是 ANE 算的。
rng = np.random.default_rng(1)


def conv_model(weight, name):
    # 输出通道补零到至少 2048，让模型够重、被放到 ANE；读结果时只取前面的行
    if weight.shape[0] < 2048:
        weight = np.vstack([weight, np.zeros((2048 - weight.shape[0], weight.shape[1]), weight.dtype)])
    cout, cin = weight.shape
    wt = weight.reshape(cout, cin, 1, 1).astype(np.float16)
    s0 = (rng.standard_normal((256, cout, 1, 1)) * 0.01).astype(np.float16)
    sw = [(rng.standard_normal((256, 256, 1, 1)) * 0.05).astype(np.float16) for _ in range(3)]

    @mb.program(input_specs=[mb.TensorSpec(shape=(1, cin, 1, W), dtype=types.fp16)], opset_version=ct.target.iOS18)
    def p(x):
        y = mb.conv(x=x, weight=wt, name="y")
        z = mb.relu(x=mb.conv(x=y, weight=s0))
        for k in sw:
            z = mb.relu(x=mb.conv(x=z, weight=k))
        z = mb.identity(x=z, name="z")
        return y, z

    kw = dict(convert_to="mlprogram", minimum_deployment_target=ct.target.iOS18, compute_precision=ct.precision.FLOAT16)
    m = ct.convert(p, compute_units=ct.ComputeUnit.CPU_AND_NE, **kw)
    m.save(os.path.join(OUT, name + ".mlpackage"))
    mc = ct.models.MLModel(os.path.join(OUT, name + ".mlpackage"), compute_units=ct.ComputeUnit.CPU_ONLY)
    return (m, mc)


DIFF = {}


def run(mm, x, tag=None):
    m, mc = mm
    cin = x.shape[0]
    if x.ndim == 1:  # 各列相同，取第 0 列
        xin = np.repeat(x.astype(np.float16).reshape(1, cin, 1, 1), W, axis=3)
        pick = lambda a: np.asarray(a)[0, :, 0, 0].astype(np.float32)
    else:  # x 为 [cin, W]：每列独立，取第 0 个输出通道的所有列
        xin = x.astype(np.float16).reshape(1, cin, 1, W)
        pick = lambda a: np.asarray(a)[0, 0, 0, :].astype(np.float32)
    y = pick(m.predict({"x": xin})["y"])
    yc = pick(mc.predict({"x": xin})["y"])
    if tag:
        same = np.array_equal(y, yc) or np.allclose(y, yc, equal_nan=True, rtol=0, atol=0)
        DIFF[tag] = {"cpu_equal": bool(same), "n_diff": int(np.sum(~((y == yc) | (np.isnan(y) & np.isnan(yc)))))}
        RESULTS_CPU[tag] = yc.tolist()
    return y


RESULTS_CPU = {}


results = {}

# ---------- F1：归约树 ----------
# 输入全 1；第 o 个输出通道的权重在 p 处为 +B、q 处为 −B、r 处为 +1，其余为 0。
# 如果 +1 先和 +B 在 fp16 里相加（B=2048 时 2048+1 舍入回 2048），结果是 0；否则是 1。
CIN = 64
B = 2048.0
pats = []
for q in range(1, CIN):
    for r in range(1, CIN):
        if r != q:
            pats.append((0, q, r))
wmat = np.zeros((len(pats), CIN), np.float32)
for i, (p_, q, r) in enumerate(pats):
    wmat[i, p_], wmat[i, q], wmat[i, r] = B, -B, 1.0
m = conv_model(wmat, "f1_tree")
y = run(m, np.ones(CIN), "f1")[:len(pats)]
grid = np.full((CIN, CIN), -1.0)
for (p_, q, r), v in zip(pats, y):
    grid[q, r] = v
np.save(os.path.join(OUT, "f1_grid.npy"), grid)
results["f1_values"] = sorted(set(np.round(y, 3).tolist()))
# 对每个 r，统计 +1 被吞掉（结果 0）的 q 有哪些
absorbed = {r: [q for q in range(1, CIN) if q != r and grid[q, r] == 0] for r in range(1, CIN)}
results["f1_absorbed_r_to_q"] = {str(r): v for r, v in absorbed.items() if v}

# ---------- F1b：累加器位宽 ----------
# 一个通道上 +B，再加 k 个 +1（分散在不同位置），再 −B。fp32 累加器：结果 = k。
rows, desc = [], []
for Bv in (2048.0, 8192.0, 32768.0, 65504.0):
    for k in (1, 3, 7, 15, 31):
        w_ = np.zeros(CIN, np.float32)
        w_[0], w_[CIN - 1] = Bv, -Bv
        w_[1:1 + k] = 1.0
        rows.append(w_)
        desc.append((Bv, k))
m = conv_model(np.array(rows), "f1b_acc")
y = run(m, np.ones(CIN), "f1b")[:len(desc)]
results["f1b_acc"] = [[b, k, float(v)] for (b, k), v in zip(desc, y)]

# ---------- F2：舍入、饱和、非规格化数、NaN ----------
# 输出 = Σ x_i·w_i，每一行一个用例；x 取全 1，权重即加数。
cases = {
    "2048+1 (tie→even=2048)": [2048, 1],
    "2048+3 (tie→even=2052)": [2048, 3],
    "2050+1 (tie→even=2052)": [2050, 1],
    "1+2^-11 (tie→1)": [1, 2 ** -11],
    "1+3·2^-11 (tie→1+2^-9)": [1, 2 ** -11, 2 ** -10],
    "20000+20000 (40000)": [20000, 20000],
    "16384+16384 (32768)": [16384, 16384],
    "16384+16385": [16384, 16384, 1],
    "40000+40000 (overflow→inf?)": [40000, 40000],
    "65504+16": [65504, 16],
    "65504+32 (→inf)": [65504, 32],
    "2^-24 (smallest subnormal)": [2 ** -24],
    "2^-20 (subnormal)": [2 ** -20],
    "2^-14 (smallest normal)": [2 ** -14],
    "2^-15+2^-15": [2 ** -15, 2 ** -15],
}
rows = []
for v in cases.values():
    w_ = np.zeros(CIN, np.float32)
    w_[:len(v)] = v
    rows.append(w_)
m = conv_model(np.array(rows), "f2_round")
y = run(m, np.ones(CIN), "f2")[:len(cases)]
results["f2"] = {k: float(v) for k, v in zip(cases, y)}

# 输入里的特殊值：放在通道 0 的不同列上（每列独立），第 0 个输出通道的权重为 e0，输出 = 输入
specials = np.array([np.nan, np.inf, -np.inf, 2 ** -24, 2 ** -20, 2 ** -15, -0.0, 65504], np.float32)
e0 = np.zeros((1, CIN), np.float32)
e0[0, 0] = 1.0
m = conv_model(e0, "f2_special")
x = np.zeros((CIN, W), np.float32)
x[0, :len(specials)] = specials
y = run(m, x, "f2s")
results["f2_special_in_to_out"] = [[str(a), str(b)] for a, b in zip(specials, y[:len(specials)])]

# 乘法里的非规格化数：x = 2^-12，w = 2^-12，积 2^-24
m = conv_model(np.array([[2 ** -12] + [0] * (CIN - 1), [2 ** -7] + [0] * (CIN - 1)], np.float32), "f2_mul_sub")
x = np.zeros(CIN, np.float32)
x[0] = 2 ** -12
y = run(m, x, "f2m")[:2]
results["f2_mul_subnormal"] = {"2^-12*2^-12 (2^-24)": float(y[0]), "2^-12*2^-7 (2^-19)": float(y[1])}

results["ane_vs_cpu"] = DIFF
results["cpu"] = RESULTS_CPU
json.dump(results, open(os.path.join(OUT, "results.json"), "w"), indent=1)
print(json.dumps({k: v for k, v in results.items() if k not in ("f1_absorbed_r_to_q", "cpu")}))
print("f1 被吞掉的 (r: q 列表)，前 20 个：")
for r, v in list(results["f1_absorbed_r_to_q"].items())[:20]:
    print(" ", r, v)
