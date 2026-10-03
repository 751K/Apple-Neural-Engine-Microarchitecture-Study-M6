"""调度组 D3 / D4：同一个模型里的两条独立支路能否在 ANE 内部重叠执行。

用法（M6）：python overlap.py <输出目录> [名字 ...]
所有张量都是 [1, C, 1, 128]（单 ANE）。两个输入 x、u。
  A：x 上的 1×1 卷积链（MAC 为主），共享权重，LA 层
  B：u 上的逐元素链（PE 为主），每步 y = y * u + u（动态输入，编译器不能折叠），LB 步
  S：u 上的 softmax 链（沿宽度），LS 步
模型：
  ovl_A{LA}           只有 A（u 不用）
  ovl_B{LB}           只有 B
  ovl_AB{LA}_{LB}     A 和 B 并列，两个输出
  ovl_AtoB{LA}_{LB}   A 的输出接给 B（串行对照）
  ovl_S{LS}、ovl_AS{LA}_{LS}、ovl_AtoS{LA}_{LS}   softmax 版本
  T：u 上的重采样链，每步双线性上采样 ×2 再平均池化缩回（推测走纹理单元 + PE），LT 步
  ovl_T{LT}、ovl_AT{LA}_{LT}            纹理单元 + MAC
  D：第三个输入 v（[1, 512, 1, 32768]，32 MB）做一次转置（交换通道和宽度），几乎不计算，主要是 DMA 搬运
  ovl_D、ovl_DB{LB}、ovl_DA{LA}          DMA 单独、DMA + PE、DMA + MAC
  add8_par / add8_ser 8 个独立 add（8 个输出）与 8 个串联 add
  mm_relu / mm_only   matmul 加一个独立 relu，与只有 matmul（maderix Part 4 §5.2）
"""
import os
import re
import subprocess
import sys

import torch  # noqa: F401
import numpy as np
import coremltools as ct
from coremltools.converters.mil import Builder as mb
from coremltools.converters.mil.mil import types

C, W = 512, 128
rng = np.random.default_rng(0)
SPEC = [mb.TensorSpec(shape=(1, C, 1, W), dtype=types.fp16), mb.TensorSpec(shape=(1, C, 1, W), dtype=types.fp16)]


def conv_chain(x, L):
    k = mb.const(val=(rng.standard_normal((C, C, 1, 1)) * np.sqrt(2.0 / C)).astype(np.float16))
    for _ in range(L):
        x = mb.relu(x=mb.conv(x=x, weight=k))
    return x


def elt_chain(y, u, L):
    for _ in range(L):
        y = mb.add(x=mb.mul(x=y, y=u), y=u)
    return y


def softmax_chain(y, L):
    for _ in range(L):
        y = mb.softmax(x=y, axis=-1)  # 沿宽度；沿通道（axis=1）的 softmax 链会被放到 CPU 上
    return y


def resize_chain(y, L):
    # 双线性上采样 ×2（推测走纹理 / 重采样单元）+ 平均池化缩回。
    # resize_bilinear、最近邻上采样、gather 都会被 Core ML 放到 CPU 上（见 texprobe.py），只有这种组合在 ANE 上。
    for _ in range(L):
        y = mb.upsample_bilinear(x=y, scale_factor_height=1, scale_factor_width=2, align_corners=False)
        y = mb.avg_pool(x=y, kernel_sizes=[1, 2], strides=[1, 2], pad_type="valid")
    return y


WV = 32768
SPEC3 = SPEC + [mb.TensorSpec(shape=(1, C, 1, WV), dtype=types.fp16)]


def transpose_big(v):
    return mb.transpose(x=v, perm=[0, 3, 2, 1])


def make(name):
    m = re.fullmatch(r"ovl_(T|AT)(\d+)(?:_(\d+))?", name)
    if m:
        kind, n1, n2 = m.group(1), int(m.group(2)), int(m.group(3) or 0)

        @mb.program(input_specs=SPEC, opset_version=ct.target.iOS18)
        def p(x, u):
            if kind == "T":
                return resize_chain(u, n1)
            return conv_chain(x, n1), resize_chain(u, n2)
        return p
    m = re.fullmatch(r"ovl_(D|DB|DA)(\d*)", name)
    if m:
        kind, n1 = m.group(1), int(m.group(2) or 0)

        @mb.program(input_specs=SPEC3, opset_version=ct.target.iOS18)
        def p(x, u, v):
            if kind == "D":
                return transpose_big(v)
            if kind == "DB":
                return transpose_big(v), elt_chain(u, x, n1)
            return transpose_big(v), conv_chain(x, n1)
        return p
    m = re.fullmatch(r"ovl_(A|B|S|AB|AS|AtoB|AtoS)(\d+)(?:_(\d+))?", name)
    if m:
        kind, n1, n2 = m.group(1), int(m.group(2)), int(m.group(3) or 0)

        @mb.program(input_specs=SPEC, opset_version=ct.target.iOS18)
        def p(x, u):
            if kind == "A":
                return conv_chain(x, n1)
            if kind == "B":
                return elt_chain(u, x, n1)
            if kind == "S":
                return softmax_chain(u, n1)
            if kind == "AB":
                return conv_chain(x, n1), elt_chain(u, u, n2)
            if kind == "AS":
                return conv_chain(x, n1), softmax_chain(u, n2)
            if kind == "AtoB":
                return elt_chain(conv_chain(x, n1), u, n2)
            if kind == "AtoS":
                return softmax_chain(conv_chain(x, n1), n2)
        return p
    if name == "side16":  # add8 的陪跑支路单独跑，作基线
        @mb.program(input_specs=SPEC, opset_version=ct.target.iOS18)
        def p(x, u):
            return conv_chain(x, 16)
        return p
    if name in ("add8_par", "add8_ser"):
        @mb.program(input_specs=SPEC, opset_version=ct.target.iOS18)
        def p(x, u):
            # 两者都带同样的陪跑支路（x 上 16 层卷积），否则太小会被放到 CPU 上
            side = conv_chain(x, 16)
            if name == "add8_ser":
                y = u
                for i in range(8):
                    y = mb.add(x=mb.mul(x=y, y=np.float16(1.001)), y=u)
                return y, side
            return tuple(mb.add(x=mb.mul(x=u, y=np.float16(i + 2)), y=u) for i in range(8)) + (side,)
        return p
    if name in ("mm_relu", "mm_only"):
        @mb.program(input_specs=SPEC, opset_version=ct.target.iOS18)
        def p(x, u):
            y = conv_chain(x, 8)
            return (y, mb.relu(x=u)) if name == "mm_relu" else y
        return p
    raise ValueError(name)


if __name__ == "__main__":
    out = sys.argv[1]
    os.makedirs(out, exist_ok=True)
    for name in sys.argv[2:]:
        if os.path.isdir(os.path.join(out, name + ".mlmodelc")):
            continue
        mdl = ct.convert(make(name), convert_to="mlprogram", minimum_deployment_target=ct.target.iOS18,
                         compute_units=ct.ComputeUnit.CPU_AND_NE,
                       skip_model_load=True)  # 生成时不加载：加载会触发一次 ANE 编译，大模型要十几分钟
        pkg = os.path.join(out, name + ".mlpackage")
        mdl.save(pkg)
        subprocess.run(["xcrun", "coremlcompiler", "compile", pkg, out], check=True, capture_output=True)
        subprocess.run(["rm", "-rf", pkg])
        print("built", name, flush=True)
