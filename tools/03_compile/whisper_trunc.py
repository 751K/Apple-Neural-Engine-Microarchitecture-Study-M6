"""把抓出的 Whisper AudioEncoder ANE 模型（whisper_capture.sh 的 ane_mil_model）截成只含前 N 个编码器层的版本，
用来找 h18g 编译失控的最小复现。

用法：python3 whisper_trunc.py <ane_mil_model 目录> <输出目录> N [N ...]
输出：<输出目录>/L<N>/model.mil，weights1.bin 为指向原文件的符号链接（截断后只引用前面的权重）。
结构：每层以两个 layer_norm 开头（注意力前、MLP 前），第 k 层（从 0 起）的注意力前 layer_norm 是全文第 2k 个；
它的输入 x 就是前 k 层的输出。截断时保留它之前的全部运算，再用原文件最后一行（tensor_to_tensor_buffer）把这个张量
转成输出 encoder_output_embeds。N = 32 即原模型（全部层加最后的 layer_norm）。
"""
import os
import re
import sys

src, out = sys.argv[1], sys.argv[2]
lines = open(os.path.join(src, "model.mil")).read().split("\n")
ln = [i for i, l in enumerate(lines) if "= layer_norm(" in l]
end = next(i for i, l in enumerate(lines) if l.strip().startswith("} -> ("))
conv = lines[end - 1]                                  # ... encoder_output_embeds = tensor_to_tensor_buffer<ios17>(input = X, ...)
assert "tensor_to_tensor_buffer" in conv, conv
nlayers = (len(ln) - 1) // 2
for n in map(int, sys.argv[3:]):
    d = os.path.join(out, f"L{n}")
    os.makedirs(d, exist_ok=True)
    if n >= nlayers:
        body = lines
    else:
        cut = ln[2 * n]
        x = re.search(r"layer_norm\(.*?x = ([A-Za-z0-9_]+)\)", lines[cut]).group(1)
        new_conv = re.sub(r"input = [A-Za-z0-9_]+", f"input = {x}", conv, count=1)
        body = lines[:cut] + [new_conv] + lines[end:]
    open(os.path.join(d, "model.mil"), "w").write("\n".join(body))
    w = os.path.join(d, "weights1.bin")
    if not os.path.lexists(w):
        os.symlink(os.path.abspath(os.path.join(src, "weights1.bin")), w)
    ops = sum(1 for l in body if re.search(r"= [a-z_0-9]+(<[a-z0-9]+>)?\(", l))
    print(f"L{n}: {ops} ops, {len(body)} lines")
