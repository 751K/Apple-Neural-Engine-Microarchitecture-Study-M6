"""稀疏实验（sparse）的模型：同一份 FP16 基准权重，用 coremltools 的 prune_weights 剪枝，看 ANE 能否从权重稀疏或激活稀疏中获益。

用法（M6，coremltools 环境，不需要 torch）：python sparse_gen.py <输出目录> [名字 ...]（不给名字则生成全部）
名字：<形状>_<版本>_L<层数>
  形状  m2048：1×1 卷积，2048 通道，输入 1×2048×1×32，各层权重不同（每层 FP16 8 MB，读权重受限；与 wfmt 相同）
        c1x1 ：1×1 卷积，512 通道，输入 1×512×1×128，各层共享一份权重（计算受限，直接卷积；D2 的原模型）
        c3x3 ：3×3 卷积，512 通道，输入 1×512×16×16，各层共享一份权重（计算受限，走硬件 Winograd）
  权重版本（层间 ReLU、偏置 0，激活约一半为 0）
        fp16   稠密（对照）
        s50 / s75 / s90  非结构化剪枝，按绝对值剪掉 50% / 75% / 90%（OpMagnitudePrunerConfig(target_sparsity=…)）
        nm24   每 4 个剪 2 个（n_m_ratio=(2, 4)，即常说的 2:4 结构化稀疏，50%）
        nm34   每 4 个剪 3 个（n_m_ratio=(3, 4)，即每 4 个只留 1 个的 1:4，75%）
        s50p4  剪枝 50% 后再对非零值做 4 位调色板（palettize_weights(joint_compression=True)），只做 m2048
  激活版本（只做 c1x1、c3x3，权重为稠密 FP16、各层共享，让每一层的输入都有给定比例的 0）
        lin    层间无激活函数：激活稠密（约 0% 为 0）
        ch50   ReLU，一半输出通道的偏置为 −30（这些通道恒为 0），另一半偏置为 0：共约 75% 为 0，其中一半是整通道为 0
        z00 / z50 / z75 / z90  层间无激活函数，卷积后乘一个固定掩码 [1, C, H, W]（各层共享一个常量）：
               掩码中给定比例的元素为 0（位置随机），其余取 [0.5, 1) 的随机数（不是常数，编译器无法把它并进权重或省掉）。
               四个版本的图结构、权重、掩码位置之外完全相同，只有掩码里 0 的比例不同，下一层输入的 0 比例即为 0% / 50% / 75% / 90%
        zch    同上，掩码为前一半通道整体为 0（50%，与 z50 同样的 0 比例，比较整通道与随机位置）
        zpc / zpco / zpw / zpwo  50% 为 0，0 两两成对，沿通道（c）或宽度（w），对齐 (2k, 2k+1) 或错开一位 (2k+1, 2k+2)；
               只做 c1x1、128 层，用于功耗实验（power_parts.py 的 zp* 负载）
        （fp16 本身即 "ReLU、约 50% 为 0"。输入全 0 时偏置为 0 的模型每层都是 0，见 sparse.sh 的 BONDRUN_FILL。）
        （第一版曾用 ReLU(x − t_i) 逐层设阈值，但每层偏置不同时编译器不再共享权重，每层各存一份，改掉了；
          固定阈值则因共享权重反复作用、幅度漂移，0 的比例会从 71% 一路涨到 99.8%。）
  为了让 32 层后数值既不溢出也不落入 FP16 次正规数（剪枝会让每层增益变小、几十层后衰减到下溢，
  下溢成 0 会混进激活稀疏的效果），权重乘一个增益：
    各层权重不同的 m2048：逐层按模拟的输入算出增益，使每层预激活的均方根为 1；
    共享权重的 c1x1、c3x3：二分一个全局增益，使最后一层预激活的均方根为 1。
  剪枝对整体缩放不敏感（按绝对值排序），所以先乘增益再交给 coremltools 剪枝，等价于剪枝后再缩放。
  增益用 numpy 在同一随机输入上模拟（FP32；剪枝掩码在 numpy 里按同样规则近似）。生成时打印每个模型第 1 层和最后一层
  输入中 0 的比例和均方根，写进 <输出目录>/act_stats.txt。
"""
import os
import subprocess
import sys

import numpy as np
import coremltools as ct
import coremltools.optimize.coreml as cto
from coremltools.converters.mil import Builder as mb
from coremltools.converters.mil.mil import types

SHAPES = {
    "m2048": dict(C=2048, H=1, W=32, k=(1, 1), shared=False),
    "c1x1": dict(C=512, H=1, W=128, k=(1, 1), shared=True),
    "c3x3": dict(C=512, H=16, W=16, k=(3, 3), shared=True),
}
WVARS = ["fp16", "s50", "s75", "s90", "nm24", "nm34"]
AVARS = ["lin", "ch50", "z00", "z50", "z75", "z90", "zch"]
LAYERS = {"m2048": (16, 32), "c1x1": (32, 128), "c3x3": (16, 32)}   # c1x1 每层只有约 3 µs，取 32 和 128 层
ALL = ([f"m2048_{v}_L{L}" for v in WVARS + ["s50p4"] for L in LAYERS["m2048"]]
       + [f"{s}_{v}_L{L}" for s in ("c1x1", "c3x3") for v in WVARS + AVARS for L in LAYERS[s]]
       + [f"c1x1_{v}_L64" for v in AVARS if v.startswith("z")]
       + [f"c1x1_{v}_L128" for v in ("zpc", "zpco", "zpw", "zpwo")])   # 128 层的掩码模型在 M6 上每个编译约 5 分钟，另做 64 层
PRUNE = {"s50": dict(target_sparsity=0.5), "s75": dict(target_sparsity=0.75), "s90": dict(target_sparsity=0.9),
         "nm24": dict(n_m_ratio=(2, 4)), "nm34": dict(n_m_ratio=(3, 4)), "s50p4": dict(target_sparsity=0.5)}
MASK = {"z00": 0.0, "z50": 0.5, "z75": 0.75, "z90": 0.9, "zch": "ch",
        "zpc": ("c", 0), "zpco": ("c", 1), "zpw": ("w", 0), "zpwo": ("w", 1)}


def base_weight(rng, C, k):
    return (rng.standard_normal((C, C, *k)) * np.sqrt(2.0 / (C * k[0] * k[1]))).astype(np.float32)


def np_prune(w, var):
    """numpy 近似 coremltools 的剪枝（只用来算增益和激活统计，不进模型）。"""
    if var not in PRUNE:
        return w
    p = PRUNE[var]
    if "target_sparsity" in p:
        t = np.quantile(np.abs(w), p["target_sparsity"])
        return np.where(np.abs(w) > t, w, 0)
    n, m = p["n_m_ratio"]                             # 沿输入通道（轴 1）每 m 个剪掉绝对值最小的 n 个
    g = np.moveaxis(w, 1, -1).reshape(-1, m)
    keep = np.argsort(np.abs(g), axis=1)[:, n:]
    out = np.zeros_like(g)
    np.put_along_axis(out, keep, np.take_along_axis(g, keep, 1), 1)
    return np.moveaxis(out.reshape(np.moveaxis(w, 1, -1).shape), -1, 1)


def conv_np(x, w):
    """x [C, H, W]，w [Co, C, kh, kw]，same padding，步长 1。"""
    Co, C, kh, kw = w.shape
    _, H, W = x.shape
    if kh == kw == 1:
        return (w.reshape(Co, C) @ x.reshape(C, -1)).reshape(Co, H, W)
    xp = np.pad(x, ((0, 0), (kh // 2, kh // 2), (kw // 2, kw // 2)))
    cols = np.stack([xp[:, i:i + H, j:j + W] for i in range(kh) for j in range(kw)], 1)   # [C, kh*kw, H, W]
    return (w.reshape(Co, -1) @ cols.reshape(C * kh * kw, -1)).reshape(Co, H, W)


def act_fn(var):
    """返回 (是否 ReLU, 偏置生成函数 C -> [C])。偏置以预激活均方根 1 为单位。"""
    if var == "lin" or var in MASK:
        return False, lambda C: np.zeros(C, np.float32)
    if var == "ch50":
        return True, lambda C: np.where(np.arange(C) % 2 == 0, -30.0, 0.0).astype(np.float32)
    return True, lambda C: np.zeros(C, np.float32)


def make_mask(var, C, H, W):
    m = np.random.default_rng(5).uniform(0.5, 1.0, (C, H, W)).astype(np.float32)
    if MASK[var] == "ch":
        m[:C // 2] = 0
    elif isinstance(MASK[var], tuple):
        # 成对的 0（50%）：沿通道（c）或宽度（w）把元素两两分组，每组随机地两个都为 0 或都不为 0。
        # 偏移 0 按 (2k, 2k+1) 分组（对齐），偏移 1 按 (2k+1, 2k+2) 分组（错开一位，首尾循环）。
        # 两者 0 的比例、成段长度和先后顺序相同，只差配对位置：用来区分"固定两元素为单位的门控"与"不翻转"。
        ax, off = MASK[var]
        n = C if ax == "c" else W
        z = np.random.default_rng(6).random((n // 2,) + ((H, W) if ax == "c" else (C, H))) < 0.5
        z = np.repeat(z, 2, axis=0)                       # [n, ...]：相邻两元素同为 0
        z = np.roll(z, off, axis=0)
        if ax == "w":
            z = np.moveaxis(z, 0, -1)                     # [C, H, W]
        m[z] = 0
    else:
        m[np.random.default_rng(6).random((C, H, W)) < MASK[var]] = 0
    return m


def simulate(x, ws, relu, b, L, stats=None, mask=None):
    """逐层前向，返回最后一层预激活的均方根；stats 收集每层输入中 0 的比例和均方根。"""
    rms = 1.0
    for i in range(L):
        if stats is not None:
            stats.append(((x == 0).mean(), np.sqrt((x ** 2).mean())))
        y = conv_np(x, ws[i % len(ws)])
        rms = np.sqrt((y ** 2).mean())
        y = y + b[:, None, None]
        x = np.maximum(y, 0) if relu else y
        if mask is not None:
            x = x * mask
    return rms


def build(name):
    shape, var, L = name.split("_")
    L = int(L[1:])
    sp = SHAPES[shape]
    C, H, W, k = sp["C"], sp["H"], sp["W"], sp["k"]
    rng = np.random.default_rng(0)
    relu, bias = act_fn(var)
    b = bias(C)
    mask = make_mask(var, C, H, W) if var in MASK else None
    x0 = np.random.default_rng(7).uniform(-1, 1, (C, H, W)).astype(np.float32)   # 与 bondrun 默认输入同分布
    if sp["shared"]:
        w = base_weight(rng, C, k)
        wp = np_prune(w, var)
        lo, hi = 0.05, 50.0                                 # 二分全局增益：最后一层预激活均方根 = 1
        for _ in range(30):
            g = np.sqrt(lo * hi)
            r = simulate(x0, [wp * g], relu, b, L, mask=mask)
            if not np.isfinite(r) or r > 1:
                hi = g
            else:
                lo = g
        ws = [w * g]
    else:
        ws, x = [], x0
        for _ in range(L):                                  # 逐层增益：每层预激活均方根 = 1
            w = base_weight(rng, C, k)
            y = conv_np(x, np_prune(w, var))
            g = 1.0 / np.sqrt((y ** 2).mean())
            ws.append(w * g)
            y = y * g + b[:, None, None]
            x = np.maximum(y, 0) if relu else y
    st = []
    simulate(x0, [np_prune(w, var) for w in ws], relu, b, L, st, mask=mask)

    @mb.program(input_specs=[mb.TensorSpec(shape=(1, C, H, W), dtype=types.fp16)], opset_version=ct.target.iOS18)
    def p(x):
        bb = mb.const(val=b.astype(np.float16))
        consts = [mb.const(val=w.astype(np.float16)) for w in ws]
        mk = mb.const(val=mask[None].astype(np.float16)) if mask is not None else None
        for i in range(L):
            x = mb.conv(x=x, weight=consts[i % len(consts)], bias=bb, pad_type="same")
            if relu:
                x = mb.relu(x=x)
            if mk is not None:
                x = mb.mul(x=x, y=mk)
        return x
    return p, st


def compress(m, var):
    if var not in PRUNE:
        return m
    m = cto.prune_weights(m, config=cto.OptimizationConfig(global_config=cto.OpMagnitudePrunerConfig(**PRUNE[var])))
    if var == "s50p4":
        m = cto.palettize_weights(m, config=cto.OptimizationConfig(
            global_config=cto.OpPalettizerConfig(mode="kmeans", nbits=4)), joint_compression=True)
    return m


if __name__ == "__main__":
    out = sys.argv[1]
    os.makedirs(out, exist_ok=True)
    log = open(os.path.join(out, "act_stats.txt"), "a")
    for name in sys.argv[2:] or ALL:
        if os.path.isdir(os.path.join(out, name + ".mlmodelc")):
            continue
        try:
            prog, st = build(name)
            m = ct.convert(prog, convert_to="mlprogram", minimum_deployment_target=ct.target.iOS18,
                           compute_units=ct.ComputeUnit.CPU_AND_NE, skip_model_load=True)
            m = compress(m, name.split("_")[1])
            pkg = os.path.join(out, name + ".mlpackage")
            m.save(pkg)
            if subprocess.run(["xcrun", "--find", "coremlcompiler"], capture_output=True).returncode == 0:
                subprocess.run(["xcrun", "coremlcompiler", "compile", pkg, out], check=True, capture_output=True)
            else:                                         # 没有 Xcode 时用 Core ML 自己编译
                import shutil
                shutil.move(ct.utils.compile_model(pkg), os.path.join(out, name + ".mlmodelc"))
            z, r = [s[0] for s in st[1:]], [s[1] for s in st[1:]]
            msg = (f"{name}: 第 1 层输入 0 比例 {st[0][0]:.3f} 均方根 {st[0][1]:.3f}；第 2 层起 0 比例 {min(z):.3f}–{max(z):.3f}，"
                   f"均方根 {min(r):.3g}–{max(r):.3g}")
            print("built", msg, flush=True)
            print(msg, file=log, flush=True)
        except Exception as e:  # 记录失败本身也是结果
            print("FAILED", name, type(e).__name__, str(e)[:300], flush=True)
