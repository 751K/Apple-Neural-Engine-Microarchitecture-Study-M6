"""ANE 数值（六）：H12 的区分实验。小于 1 LSB 的乘积被丢掉，是按乘积大小判断，还是按"x 指数 + w 指数"判断？

用法：./anewho python numerics6.py <输出目录>
每个用例 (w, x)：第 0 个输出通道 = x·w，读出后以 LSB = 2^-16 为单位。
"""
import os as _os, sys as _sys  # 仓库里按目录存放、部署到 M6 时平铺：两种布局都能找到公共模块
_here = _os.path.dirname(_os.path.abspath(__file__))
_sys.path[:0] = [_here, _os.path.join(_here, "..", "lib"), _os.path.join(_here, "..", "common")]
import sys

import numpy as np

sys.argv = [sys.argv[0], sys.argv[1] if len(sys.argv) > 1 else "numerics6_out"]
import numerics5 as n5  # noqa: E402

LSB = 2.0 ** -16


def ex(v):
    """fp16 的指数（非规格化数按 -14 计）。"""
    v = abs(float(v))
    return -14 if v < 2.0 ** -14 else int(np.floor(np.log2(v)))


# (w, [x ...])
CASES = {
    1.875 * 2 ** -3: [1.875 * 2 ** -14, 1.0 * 2 ** -14, 1.5 * 2 ** -14, 0.99 * 2 ** -14, 0.6 * 2 ** -14],
    1.99 * 2 ** -3: [1.99 * 2 ** -14, 1.0 * 2 ** -14, 0.9 * 2 ** -14],
    1.5 * 2 ** -4: [1.5 * 2 ** -13, 1.9 * 2 ** -13, 1.0 * 2 ** -13, 1.9 * 2 ** -14],
    1.9375 * 2 ** -5: [1.9375 * 2 ** -13, 1.9375 * 2 ** -12, 1.0 * 2 ** -12],
    0.2: [0.99 * 2 ** -14, 0.8 * 2 ** -14, 1.0 * 2 ** -14],
}
for wv, xs in CASES.items():
    wvec = np.zeros(n5.CIN, np.float16)
    wvec[0] = wv
    mm = n5.conv_bias(wvec, 0.0, f"h12_w{wv:g}")
    xs16 = [np.float16(x) for x in xs]
    a, c = n5.run_cols(mm, [[x] for x in xs16])
    w16 = np.float16(wv)
    print(f"== w={float(w16)!r}（指数 {ex(w16)}）")
    for x, ai in zip(xs16, a):
        p = float(x) * float(w16) / LSB
        sub = "非规格化" if abs(float(x)) < 2.0 ** -14 else "规格化"
        print(f"    x={float(x)!r:<24} {sub}  指数和 {ex(x) + ex(w16):>4}  乘积 {p:7.4f} LSB → ANE {ai / LSB:g} LSB")
