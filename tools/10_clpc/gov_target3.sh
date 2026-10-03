#!/bin/zsh
# CLPC 第三轮（gov_target2 的后续），两个问题：
#   1. 忙碌比例随空闲间隙变长而下降（1–7 ms：77% → 56%），而第一轮 12–24 ms 间隙又回到 61–67%：曲线是否不单调。
#      用两个 ANE 并行、权重在片上的宽 512（满频 2.6 ms）和宽 1024（5.2 ms）模型，把间隙从约 1 ms 扫到约 30 ms。
#   2. 宽 256（满频 1.4 ms）在 G = 1050 µs 时稳定在 2540 MHz、忙碌比例只有 35%：能否复现、从哪个 G 开始。
#      在 G = 800–1300 µs 之间细扫，G = 1050 重复三次。
# 每段固定运行 T 秒。用法（M6）：cd ~/anehal/hwx && sudo ./gov_target3.sh
# 输出：gov_tg3/trace.txt（时间 tick、debug-id、cpu 列；只保留 61b0125/0126/01a9/00a0/0071）、gov_tg3/marks.txt
cd "$(dirname "$0")"
out=gov_tg3
mkdir -p $out
SEGS=(
  "gt/k1_c512_h1w512_L384.mlmodelc 0 600 1500 2500 4000 6000 9000 13000 18000 25000"
  "gt/k1_c512_h1w1024_L384.mlmodelc 0 1000 2500 4000 6000 9000 13000 18000 25000"
  "gt/k1_c512_h1w256_L384.mlmodelc 0 800 900 1000 1050 1100 1200 1300 1050 1050"
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
