"""扫通道数和层数，找 Core ML 把 conv+bias+relu 链放到 ANE 的条件。"""
import os as _os, sys as _sys  # 仓库里按目录存放、部署到 M6 时平铺：两种布局都能找到公共模块
_here = _os.path.dirname(_os.path.abspath(__file__))
_sys.path[:0] = [_here, _os.path.join(_here, "..", "lib"), _os.path.join(_here, "..", "common")]
import os, subprocess, sys
import torch  # noqa: F401
import coremltools as ct
from bonded_cases import conv1x1_chain

out = sys.argv[1]
os.makedirs(out, exist_ok=True)
for C, H, W, L in [(1024, 1, 1, 1), (1024, 1, 1, 2), (256, 1, 16, 1), (256, 1, 16, 4), (64, 1, 16, 4), (64, 1, 16, 16),
                   (256, 32, 32, 1), (256, 32, 32, 2)]:
    name = f"q_c{C}_h{H}w{W}_L{L}"
    m = ct.convert(conv1x1_chain(C, H, W, L), convert_to="mlprogram", minimum_deployment_target=ct.target.iOS18,
                   compute_units=ct.ComputeUnit.CPU_AND_NE)
    pkg = os.path.join(out, name + ".mlpackage")
    m.save(pkg)
    subprocess.run(["xcrun", "coremlcompiler", "compile", pkg, out], check=True, capture_output=True)
    print("built", name, flush=True)
