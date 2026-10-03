#!/bin/zsh
# ANE 调频（CLPC）黑盒实验：同一单 ANE 模型（L384，共享权重，满频约 1646 us/次），每次调用前睡眠 G 微秒，
# 记录逐次耗时序列（BONDRUN_SERIES），看稳态档位与间隔（利用率）的关系、是否振荡。不需要 root。
# 用法（M6）：cd ~/anehal/hwx && ./gov_sweep.sh > gov_sweep_run.txt；序列在 gov/<G>.txt
cd "$(dirname "$0")"
mkdir -p gov
M=sweep/k1x1_512_h1w128_L384.mlmodelc
for G in 0 50 100 150 200 250 300 400 600 1000 2000 3000; do
  sleep 4
  n=$(( 5000000 / (1650 + G) ))
  BONDRUN_SLEEP_US=$G BONDRUN_SERIES=gov/$G.txt ./bondrun $M $n | grep 中位数 | sed "s/^/G=$G /"
done
