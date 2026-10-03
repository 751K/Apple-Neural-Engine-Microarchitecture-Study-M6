#!/bin/zsh
# CLPC 第二轮（gov_target 的后续）：长任务时忙碌比例偏离 77%，是因为任务长，还是因为读 DRAM，还是因为时间尺度。
# 三组模型，各三种满频任务时长（约 1.4、2.7、5.4 ms），按"睡眠时间 G ÷ 满频任务时长"的同一组比例扫描：
#   S：单 ANE，权重在片上（512 通道，只有 1.3 ms 一种：更多层编译器不放上 ANE，更宽则拆到两个 ANE）
#   M：单 ANE，读 DRAM（1024 通道 96 / 192 / 384 层，权重每层从 DRAM 读）
#   B：两个 ANE 并行（bonded），权重在片上（512 通道 384 层，宽 256 / 512 / 1024）
# 每段固定运行 T 秒后结束 bondrun（调用次数给得足够大）。
# 用法（M6）：cd ~/anehal/hwx && sudo ./gov_target2.sh
# 模型由 chain.py 生成在 gt/（sweep/ 下为原有模型）。
# 输出：gov_tg2/trace.txt（时间 tick、debug-id、cpu 列，如 36(ANE0)；只保留 61b0125/0126/01a9/00a0/0071）、gov_tg2/marks.txt
cd "$(dirname "$0")"
out=gov_tg2
mkdir -p $out
# 模型  G 列表（µs）
SEGS=(
  "sweep/k1x1_512_h1w128_L384.mlmodelc 0 130 250 450"
  "gt/k1_c1024_h1w128_L96.mlmodelc 0 140 280 500 700 1050"
  "gt/k1_c1024_h1w128_L192.mlmodelc 0 265 530 930 1300 2000"
  "gt/k1_c1024_h1w128_L384.mlmodelc 0 530 1060 1850 2650 4000"
  "gt/k1_c512_h1w256_L384.mlmodelc 0 140 280 500 700 1050"
  "gt/k1_c512_h1w512_L384.mlmodelc 0 270 540 950 1350 2000"
  "gt/k1_c512_h1w1024_L384.mlmodelc 0 540 1080 1900 2700 4000"
)
T=12
total=0
for s in $SEGS; do a=(${=s}); (( total += (${#a} - 1) * (T + 4) )); done
ktrace trace -t -N -f S0x061b -T $(( total + 30 )) |
  awk '$3 ~ /^61b0(125|126|1a9|0a0|071)$/ {print $1, $3, $(NF-1)}' > $out/trace.txt &
KT=$!
sleep 1
: > $out/marks.txt
for s in $SEGS; do
  a=(${=s})
  M=$a[1]
  for G in $a[2,-1]; do
    sleep 3
    echo "$M $G $(date +%s)" >> $out/marks.txt
    sudo -u "$SUDO_USER" env BONDRUN_SLEEP_US=$G ./bondrun $M 1000000 > /dev/null 2>&1 &
    B=$!
    sleep $T
    kill $B 2>/dev/null; wait $B 2>/dev/null
  done
done
wait $KT
chown -R "$SUDO_USER" $out
echo "完成：$(wc -l < $out/trace.txt) 条事件，结果在 $(pwd)/$out"
