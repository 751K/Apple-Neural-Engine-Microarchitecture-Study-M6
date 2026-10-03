"""ANE 数值（四）：输入里 exp=31（inf/NaN）的 fp16 怎么解码；大输入是否在进入累加器前就溢出。
用法：./anewho python numerics4.py <输出目录>"""
import os as _os, sys as _sys  # 仓库里按目录存放、部署到 M6 时平铺：两种布局都能找到公共模块
_here = _os.path.dirname(_os.path.abspath(__file__))
_sys.path[:0] = [_here, _os.path.join(_here, "..", "lib"), _os.path.join(_here, "..", "common")]
import os, sys
import numpy as np
sys.argv = [sys.argv[0], sys.argv[1] if len(sys.argv) > 1 else "numerics4_out"]
import numerics3 as n3  # noqa: E402  复用 conv_w / run_conv

bits = [0x7C00, 0xFC00, 0x7E00, 0x7C01, 0x7FFF, 0xFE00, 0x7BFF, 0x8000]
xs = np.array(bits, np.uint16).view(np.float16)
for wv in (2.0 ** -12, 2.0 ** -4):
    a, c = n3.run_conv(n3.conv_w(wv, f"exp31_w{wv}"), xs)
    print(f"== w={wv}  （输入位 / ANE 输出 / ANE 输出÷w / CPU）")
    for b, ai, ci in zip(bits, a, c):
        print(f"    0x{b:04X}  {ai!r:>12}  {ai / wv!r:>12}  {ci!r}")
