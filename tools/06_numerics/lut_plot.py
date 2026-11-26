"""画激活函数的误差曲线（ANE 输出 − 精确值），配色与版式完全对齐 plotfig.py / archfig.py。
用法：python3 tools/06_numerics/lut_plot.py data/06_numerics/lut_m6 figs
输出 figs/<语言>/<主题>/fig8-2_lut_error.png 与 fig8-3_lut_error_zoom.png（语言 zh、en，主题 light、dark）。"""
import math
import os
import sys
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import FancyBboxPatch
from matplotlib.ticker import MaxNLocator

erf = np.vectorize(math.erf)

src, dst = sys.argv[1], sys.argv[2]
EX = {
    "sigmoid": lambda x: 1 / (1 + np.exp(-x)), "tanh": np.tanh,
    "gelu": lambda x: 0.5 * x * (1 + erf(x / np.sqrt(2))),
    "gelu_tanh": lambda x: 0.5 * x * (1 + np.tanh(np.sqrt(2 / np.pi) * (x + 0.044715 * x ** 3))),
    "silu": lambda x: x / (1 + np.exp(-x)), "exp": np.exp, "log": np.log, "sqrt": np.sqrt,
    "rsqrt": lambda x: 1 / np.sqrt(x), "inverse": lambda x: 1 / x, "erf": erf, "sin": np.sin,
}

TXT = {
    "zh": dict(rel="相对", abs="绝对", ane="ANE", cpu="CPU",
               ane_err="ANE 误差", grid05="0.5 间隔"),
    "en": dict(rel="rel.", abs="abs.", ane="ANE", cpu="CPU",
               ane_err="ANE error", grid05="0.5 interval"),
}


def theme(dark):
    if dark:
        return dict(
            bg="#1a1a1a", panel="#27272a", axes="#1a1a1a",
            fg="#e8e8ea", axis="#b8b8be", tick="#c8c8ce", grid="#303036",
            zero="#55555d", ane="#6495d6", cpu="#7c9452", mark="#e89a54",
        )
    return dict(
        bg="#ffffff", panel="#efefef", axes="#ffffff",
        fg="#111111", axis="#2b2b2b", tick="#333333", grid="#e6e6ea",
        zero="#99999f", ane="#2f5f98", cpu="#b4c496", mark="#e07b22",
    )


def style_ax(ax, th):
    ax.set_facecolor(th["axes"])
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    for sp in ("left", "bottom"):
        ax.spines[sp].set_color(th["axis"])
        ax.spines[sp].set_linewidth(0.95)
    ax.tick_params(colors=th["tick"], labelsize=8.5, length=3.5, width=0.85, direction="out")
    ax.yaxis.set_major_locator(MaxNLocator(nbins=4, prune=None))
    ax.grid(axis="y", color=th["grid"], linewidth=0.65, zorder=0)
    ax.axhline(0, color=th["zero"], lw=0.6, zorder=1)


def add_panel(fig, x, y, w, h, color):
    fig.add_artist(FancyBboxPatch(
        (x, y), w, h,
        boxstyle="round,pad=0,rounding_size=0.012",
        transform=fig.transFigure, facecolor=color, edgecolor="none", zorder=-10,
    ))


def draw(lang, dark):
    T = TXT[lang]
    th = theme(dark)
    out = os.path.join(dst, lang, "dark" if dark else "light")
    os.makedirs(out, exist_ok=True)
    names = list(EX)

    # ================= 图 8-2：12 个激活函数误差（4×3） =================
    fig, axs = plt.subplots(4, 3, figsize=(8.0, 7.6), facecolor=th["bg"])
    fig.subplots_adjust(left=0.088, right=0.975, top=0.952, bottom=0.098, wspace=0.30, hspace=0.42)
    add_panel(fig, 0.006, 0.054, 0.988, 0.936, th["panel"])

    for ax, n in zip(axs.flat, names):
        style_ax(ax, th)
        d = np.load(os.path.join(src, n + ".npz"))
        x, a, c = d["x"], d["ane"], d["cpu"]
        ux, i = np.unique(x, return_index=True)
        e = EX[n](ux)
        rel = n in ("exp", "inverse", "rsqrt", "sqrt", "log")
        ea = (a[i] - e) / (np.abs(e) if rel else 1)
        ec = (c[i] - e) / (np.abs(e) if rel else 1)
        ax.plot(ux, ec, lw=0.45, color=th["cpu"], zorder=2)
        ax.plot(ux, ea, lw=0.60, color=th["ane"], zorder=3)
        tag = T["rel"] if rel else T["abs"]
        title = f"{n}（{tag}）" if lang == "zh" else f"{n} ({tag})"
        ax.set_title(title, loc="left", fontsize=9.8, fontweight="bold", color=th["fg"], pad=5)
        if rel or n in ("log",):
            ax.set_xscale("log")

    handles = [
        Line2D([0], [0], color=th["ane"], lw=2.0, label=T["ane"]),
        Line2D([0], [0], color=th["cpu"], lw=2.0, label=T["cpu"]),
    ]
    leg = fig.legend(handles=handles, loc="lower center", bbox_to_anchor=(0.5, 0.008),
                     ncol=2, frameon=False, fontsize=9.8, handlelength=2.2, columnspacing=3.4)
    for txt in leg.get_texts():
        txt.set_color(th["fg"])
    fig.savefig(os.path.join(out, "fig8-2_lut_error.png"), dpi=200, facecolor=th["bg"])
    plt.close(fig)

    # ================= 图 8-3：4 个常用激活函数近景（2×2 独立浅灰面板） =================
    fig, axs = plt.subplots(2, 2, figsize=(8.0, 5.2), facecolor=th["bg"])
    fig.subplots_adjust(left=0.095, right=0.968, top=0.915, bottom=0.145, wspace=0.25, hspace=0.42)
    # 4 个独立圆角浅灰分区，对齐图 5-3 / 图 7-1..7-4
    add_panel(fig, 0.006, 0.545, 0.486, 0.440, th["panel"])
    add_panel(fig, 0.508, 0.545, 0.486, 0.440, th["panel"])
    add_panel(fig, 0.006, 0.085, 0.486, 0.440, th["panel"])
    add_panel(fig, 0.508, 0.085, 0.486, 0.440, th["panel"])

    for ax, n, (lo, hi) in zip(axs.flat, ["sigmoid", "gelu", "silu", "tanh"], [(-8.5, 8.5), (-6, 4), (-10, 6), (-5, 5)]):
        style_ax(ax, th)
        d = np.load(os.path.join(src, n + ".npz"))
        ux, i = np.unique(d["x"], return_index=True)
        m = (ux > lo) & (ux < hi)
        ea = d["ane"][i] - EX[n](ux)
        for k in np.arange(np.ceil(lo * 2) / 2, hi, 0.5):
            ax.axvline(k, color=th["mark"], lw=0.45, alpha=0.35 if dark else 0.30, zorder=1)
        ax.plot(ux[m], ea[m], lw=0.75, color=th["ane"], zorder=3)
        ax.set_title(n, loc="left", fontsize=10.5, fontweight="bold", color=th["fg"], pad=5)

    handles = [
        Line2D([0], [0], color=th["ane"], lw=2.0, label=T["ane_err"]),
        Line2D([0], [0], color=th["mark"], lw=1.4, alpha=0.7, label=T["grid05"]),
    ]
    leg = fig.legend(handles=handles, loc="lower center", bbox_to_anchor=(0.5, 0.012),
                     ncol=2, frameon=False, fontsize=9.8, handlelength=2.2, columnspacing=3.4)
    for txt in leg.get_texts():
        txt.set_color(th["fg"])
    fig.savefig(os.path.join(out, "fig8-3_lut_error_zoom.png"), dpi=200, facecolor=th["bg"])
    plt.close(fig)


plt.rcParams["font.sans-serif"] = ["PingFang SC", "Hiragino Sans GB", "Arial Unicode MS", "Arial"]
plt.rcParams["axes.unicode_minus"] = False

for lang in ("zh", "en"):
    for dark in (False, True):
        draw(lang, dark)
print("ok")
