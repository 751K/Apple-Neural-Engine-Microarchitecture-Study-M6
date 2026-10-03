"""画激活函数的误差曲线（ANE 输出 − 精确值），并用"误差拱形"的端点估计采样点。
用法：python lut_plot.py <npz 目录> <图片输出目录>"""
import sys, os
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy.special import erf

src, dst = sys.argv[1], sys.argv[2]
EX = {
    "sigmoid": lambda x: 1 / (1 + np.exp(-x)), "tanh": np.tanh,
    "gelu": lambda x: 0.5 * x * (1 + erf(x / np.sqrt(2))),
    "gelu_tanh": lambda x: 0.5 * x * (1 + np.tanh(np.sqrt(2 / np.pi) * (x + 0.044715 * x ** 3))),
    "silu": lambda x: x / (1 + np.exp(-x)), "exp": np.exp, "log": np.log, "sqrt": np.sqrt,
    "rsqrt": lambda x: 1 / np.sqrt(x), "inverse": lambda x: 1 / x, "erf": erf, "sin": np.sin,
}
names = list(EX)
fig, axs = plt.subplots(4, 3, figsize=(15, 13))
for ax, n in zip(axs.flat, names):
    d = np.load(os.path.join(src, n + ".npz"))
    x, a, c = d["x"], d["ane"], d["cpu"]
    ux, i = np.unique(x, return_index=True)
    e = EX[n](ux)
    rel = n in ("exp", "inverse", "rsqrt", "sqrt", "log")
    ea = (a[i] - e) / (np.abs(e) if rel else 1)
    ec = (c[i] - e) / (np.abs(e) if rel else 1)
    ax.plot(ux, ec, lw=0.4, color="0.7", label="CPU")
    ax.plot(ux, ea, lw=0.5, color="C3", label="ANE")
    ax.set_title(f"{n}（{'相对' if rel else '绝对'}误差）")
    if rel or n in ("log",):
        ax.set_xscale("log")
    ax.axhline(0, color="k", lw=0.3)
    ax.legend(fontsize=7)
plt.rcParams["font.sans-serif"] = ["PingFang SC", "Arial Unicode MS"]
plt.tight_layout()
plt.savefig(os.path.join(dst, "lut_error_m6.png"), dpi=110)

# sigmoid / gelu / silu / tanh 的近景
fig, axs = plt.subplots(2, 2, figsize=(14, 8))
for ax, n, (lo, hi) in zip(axs.flat, ["sigmoid", "gelu", "silu", "tanh"], [(-8.5, 8.5), (-6, 4), (-10, 6), (-5, 5)]):
    d = np.load(os.path.join(src, n + ".npz"))
    ux, i = np.unique(d["x"], return_index=True)
    m = (ux > lo) & (ux < hi)
    ea = d["ane"][i] - EX[n](ux)
    ax.plot(ux[m], ea[m], lw=0.6, color="C3")
    for k in np.arange(np.ceil(lo * 2) / 2, hi, 0.5):
        ax.axvline(k, color="C0", lw=0.3, alpha=0.5)
    ax.set_title(f"{n}：ANE 误差（蓝线为 0.5 间隔）")
    ax.axhline(0, color="k", lw=0.3)
plt.tight_layout()
plt.savefig(os.path.join(dst, "lut_error_zoom_m6.png"), dpi=110)
print("ok")
