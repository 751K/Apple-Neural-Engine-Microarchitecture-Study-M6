"""解开 .im4p 固件封装，取出数据部分（若为 LZFSE 压缩则用 macOS 的 compression_tool 解压）。只读分析用。

用法：python3 im4p_extract.py <输入.im4p> <输出.bin>
IM4P 结构（DER）：SEQUENCE { IA5String "IM4P", IA5String 类型, IA5String 描述, OCTET STRING 数据, [可选的 KBAG / 压缩信息] }
"""
import subprocess
import sys


def read_len(b, i):
    n = b[i]
    i += 1
    if n < 0x80:
        return n, i
    k = n & 0x7f
    return int.from_bytes(b[i:i + k], "big"), i + k


def items(b, i, end):
    out = []
    while i < end:
        tag = b[i]
        ln, j = read_len(b, i + 1)
        out.append((tag, b[j:j + ln]))
        i = j + ln
    return out


src, dst = sys.argv[1], sys.argv[2]
b = open(src, "rb").read()
assert b[0] == 0x30, "不是 DER SEQUENCE"
ln, i = read_len(b, 1)
parts = items(b, i, i + ln)
kind = parts[1][1].decode()
desc = parts[2][1].decode(errors="replace")
payload = parts[3][1]
print(f"类型 {kind}  描述 {desc}  数据 {len(payload)} 字节  开头 {payload[:4]!r}  其他字段 {len(parts) - 4}")
if payload[:4] in (b"bvx2", b"bvx1", b"bvxn", b"bvx-"):
    raw = dst + ".lzfse"
    open(raw, "wb").write(payload)
    subprocess.run(["compression_tool", "-decode", "-a", "lzfse", "-i", raw, "-o", dst], check=True)
    print("LZFSE 解压 →", dst)
else:
    open(dst, "wb").write(payload)
    print("未压缩 →", dst)
