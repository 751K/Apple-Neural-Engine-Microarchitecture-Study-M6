"""画激活函数的误差曲线（ANE 输出 − 精确值），并用"误差拱形"的端点估计采样点。
用法：python lut_plot.py <npz 目录> <figs 目录>
输出 figs/<语言>/<主题>/fig8-2_lut_error.png 与 fig8-3_lut_error_zoom.png（语言 zh、en，主题 light、dark）。"""
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


TXT = {
    "zh": dict(rel="相对误差", abs="绝对误差", zoom="{n}：ANE 误差（蓝线为 0.5 间隔）"),
    "en": dict(rel="relative error", abs="absolute error", zoom="{n}: ANE error (blue lines every 0.5)"),
}


def draw(lang, dark):
    """lang 为 zh 或 en；dark 为 True 时出深色版（供网页的深色模式使用）。"""
    T = TXT[lang]
    out = os.path.join(dst, lang, "dark" if dark else "light")
    os.makedirs(out, exist_ok=True)
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
        ax.plot(ux, ec, lw=0.4, color=("0.45" if dark else "0.7"), label="CPU")
        ax.plot(ux, ea, lw=0.5, color="tab:red", label="ANE")
        ax.set_title(f"{n}（{T['rel'] if rel else T['abs']}）" if lang == "zh" else f"{n} ({T['rel'] if rel else T['abs']})")
        if rel or n in ("log",):
            ax.set_xscale("log")
        ax.axhline(0, color=("0.8" if dark else "k"), lw=0.3)
        ax.legend(fontsize=7)
    plt.tight_layout()
    plt.savefig(os.path.join(out, "fig8-2_lut_error.png"), dpi=110, facecolor=fig.get_facecolor())

    # sigmoid / gelu / silu / tanh 的近景
    fig, axs = plt.subplots(2, 2, figsize=(14, 8))
    for ax, n, (lo, hi) in zip(axs.flat, ["sigmoid", "gelu", "silu", "tanh"], [(-8.5, 8.5), (-6, 4), (-10, 6), (-5, 5)]):
        d = np.load(os.path.join(src, n + ".npz"))
        ux, i = np.unique(d["x"], return_index=True)
        m = (ux > lo) & (ux < hi)
        ea = d["ane"][i] - EX[n](ux)
        ax.plot(ux[m], ea[m], lw=0.6, color="tab:red")
        for k in np.arange(np.ceil(lo * 2) / 2, hi, 0.5):
            ax.axvline(k, color="tab:blue", lw=0.3, alpha=(0.8 if dark else 0.5))
        ax.set_title(T["zoom"].format(n=n))
        ax.axhline(0, color=("0.8" if dark else "k"), lw=0.3)
    plt.tight_layout()
    plt.savefig(os.path.join(out, "fig8-3_lut_error_zoom.png"), dpi=110, facecolor=fig.get_facecolor())


for lang, dark in ((l, d) for l in ("zh", "en") for d in (False, True)):
    with plt.style.context("dark_background" if dark else "default"):
        if dark:
            plt.rcParams.update({"figure.facecolor": "#161618", "axes.facecolor": "#161618", "savefig.facecolor": "#161618"})
        plt.rcParams["font.sans-serif"] = ["PingFang SC", "Arial Unicode MS"]
        draw(lang, dark)
        plt.close("all")
print("ok")
