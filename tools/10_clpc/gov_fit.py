"""gov_ktrace.sh 的结果（H54）：各调用间隔下 ANE 任务的档位、空闲间隙，以及"任务结束时下一个请求是否已提交"。

用法：python3 gov_fit.py <trace.txt> [每段丢弃的前 N 秒 = 2.0]
trace.txt 每行：mach 时间（24 MHz tick） debug-id。用到：61b0125 任务开始、61b0126 任务结束（固件），61b01a9 驱动收到提交。
相邻任务相隔 > 2 s 视为新的一段（脚本里每种间隔之间空闲 3 s）；每段对应 marks.txt 中的一个 G。
档位：任务时长 = C / f + D，C = 3.25e6 周期、D ≈ 8 µs（power.md §6.5 拟合），f 取设备树 32 档中最接近者。
"""
import sys

import numpy as np

DT = [804, 828, 852, 960, 996, 1032, 1092, 1128, 1188, 1248, 1308, 1368, 1404, 1476, 1548, 1632,
      1716, 1788, 1872, 1908, 1968, 2052, 2112, 2196, 2280, 2352, 2364, 2436, 2448, 2484, 2508, 2580]
C, D = 1267.5 - 8.0, 8.0  # 满频 2580 MHz 时 1267.5 µs → C/f 部分（µs·GHz 归一）
SKIP = float(sys.argv[2]) if len(sys.argv) > 2 else 2.0
GS = [0, 100, 150, 200, 300, 400, 1000, 3000]

st, en, sub = [], [], []
cur = None
for l in open(sys.argv[1]):
    p = l.split()
    if len(p) < 2:
        continue
    t, i = int(p[0]) / 24.0, p[1]
    if i == "61b0125":
        cur = t
    elif i == "61b0126" and cur is not None:
        st.append(cur); en.append(t); cur = None
    elif i == "61b01a9":
        sub.append(t)
st, en, sub = np.array(st), np.array(en), np.array(sub)
cuts = [0] + [k for k in range(1, len(st)) if st[k] - en[k - 1] > 2e6] + [len(st)]
print(f"任务 {len(st)}，分成 {len(cuts) - 1} 段")


def mhz(dur):
    f = C * 2580 / (dur - D)
    return min(DT, key=lambda x: abs(x - f))


print(f"{'G µs':>6} {'任务数':>6} {'任务时长中位':>10} {'档位中位 MHz':>12} {'档位分布(前 3)':>28} {'ANE 空闲间隙中位':>14} {'ANE 忙比例':>9} "
      f"{'结束时已排队':>10}")
for r in range(len(cuts) - 1):
    a, b = cuts[r], cuts[r + 1]
    s, e = st[a:b], en[a:b]
    keep = s >= s[0] + SKIP * 1e6
    if keep.sum() < 20:
        continue
    s, e = s[keep], e[keep]
    dur = e - s
    gap = s[1:] - e[:-1]
    lv = np.array([mhz(x) for x in dur])
    vals, cnt = np.unique(lv, return_counts=True)
    top = sorted(zip(cnt, vals), reverse=True)[:3]
    busy = dur.sum() / (e[-1] - s[0])
    # 任务 k 结束时，是否已有一次提交发生在 (任务 k 开始, 任务 k 结束) 之间 → 下一个请求已排队
    q = np.mean([np.any((sub > s[k]) & (sub < e[k])) for k in range(len(s) - 1)])
    g = GS[r] if r < len(GS) else -1
    print(f"{g:6d} {len(s):6d} {np.median(dur):10.1f} {np.median(lv):12.0f} "
          f"{' '.join(f'{v}:{c * 100 // len(lv)}%' for c, v in top):>28} {np.median(gap):14.1f} {busy:9.0%} {q:10.0%}")
