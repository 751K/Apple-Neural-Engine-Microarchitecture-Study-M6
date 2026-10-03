#!/bin/zsh
# CLPC 的利用率目标是按固件任务时间定义，还是按驱动报告的作业区间定义（12.4 节的推断）。
# 三个单 ANE 的 1×1 卷积链，满频单次任务约 1.3 ms、5.4 ms、22 ms。前两个共享权重，权重留在片上；第三个 2048 通道，
# 8 MB 权重放不进片上，每层从 DRAM 读，时长不严格 ∝ 1/f（1024 通道 768 层以上编译器不放上 ANE，所以不用更多层）。
# 每个模型先连续调用（G = 0，得到满频时长），再选三个睡眠时间 G，使稳态档位落在 852–2580 MHz 之间。周期因此从约 2 ms 跨到约 70 ms。
# 若目标按驱动区间定义，每次调用固定多出的几十微秒在长周期里可以忽略，以固件时间算的忙碌比例应随周期变长而上升；
# 若目标按固件时间定义，各周期下都应保持约 77%。
# 用法（M6）：cd ~/anehal/hwx && sudo ./gov_target.sh
# 模型：sweep/k1x1_512_h1w128_L384；gt/k1_c1024_h1w128_L384、gt/k1_c2048_h1w128_L384（chain.py 生成）。
# 输出：gov_tg/trace.txt（时间 tick、debug-id；0x061b 类全部事件）、gov_tg/marks.txt（模型、G、开始时间）
cd "$(dirname "$0")"
out=gov_tg
mkdir -p $out
# 模型  满频估计周期 µs  G 列表
SEGS=(
  "sweep/k1x1_512_h1w128_L384.mlmodelc 1650 0 150 200 300"
  "gt/k1_c1024_h1w128_L384.mlmodelc 5800 0 1700 2600 3800"
  "gt/k1_c2048_h1w128_L384.mlmodelc 22300 0 8000 11600 16400"
)
T=16   # 每段时长（秒）
ktrace trace -t -N -f S0x061b -T 300 > $out/raw.txt 2>&1 &
KT=$!
sleep 1
: > $out/marks.txt
for s in $SEGS; do
  a=(${=s})
  M=$a[1]; P0=$a[2]
  for G in $a[3,-1]; do
    sleep 3
    # 稳态周期约为 (G + 384 µs) / 0.23；G = 0 时为满频周期
    if (( G == 0 )); then per=$P0; else per=$(( (G + 384) * 100 / 23 )); fi
    n=$(( T * 1000000 / per ))
    echo "$M $G $(date +%s)" >> $out/marks.txt
    sudo -u "$SUDO_USER" env BONDRUN_SLEEP_US=$G ./bondrun $M $n > $out/run_${M:t:r}_G$G.txt 2>&1
  done
done
wait $KT
grep -E " 61b0[0-9a-f]{3} " $out/raw.txt | awk '{print $1, $3}' > $out/trace.txt
rm -f $out/raw.txt
chown -R "$SUDO_USER" $out
echo "完成：$(wc -l < $out/trace.txt) 条事件，结果在 $(pwd)/$out"
