#!/bin/zsh
# 功耗与频率测试（B9 / E3）：每种负载连续跑约 10 s，期间用 powermetrics 采 6 个 1 s 样本。
# 需要 root：在 M6 上 cd ~/anehal/hwx && sudo ./power_suite.sh
# 输出：power_out/<负载>.txt（powermetrics 原文）和 power_out/<负载>.bondrun.txt（耗时、中断）
set -u
cd "$(dirname "$0")"
out=power_out
mkdir -p $out
pm() { powermetrics -s cpu_power,gpu_power,thermal --show-extra-power-info -i 1000 -n 6 > "$1" 2>&1; }

run() {  # run <标签> <mlmodelc> <调用次数>
  echo "== $1"
  sudo -u "$SUDO_USER" ./bondrun "$2" "$3" > "$out/$1.bondrun.txt" 2>&1 &
  sleep 3   # 预热 + 时钟爬升
  pm "$out/$1.txt"
  wait
  grep -h "中位数" "$out/$1.bondrun.txt"
}

echo "== idle（空闲基线）"
sleep 5
pm "$out/idle.txt"

run fp16_single_compute  sweep/k1x1_512_h1w128_L384.mlmodelc   7000   # 单 ANE，计算受限，约 20 TFLOPS
run fp16_dual_compute    sweep/k1x1_512_h1w256_L384.mlmodelc   7000   # 双 ANE，计算受限，约 40 TFLOPS
run fp16_dual_L48        chains/k1_c512_h32w32_L48_u.mlmodelc  11000  # 双 ANE，FP16，48 层独立权重
run w8a8_dual_L48        chains/k1_c512_h32w32_L48_u_q8.mlmodelc 15000 # 双 ANE，W8A8，同上
run fp16_single_weightbw chains/k1_c512_h1w16_L192_u.mlmodelc  10000  # 单 ANE，读权重受限（约 96 MiB 权重）

chown -R "$SUDO_USER" "$out"
echo "完成，结果在 $(pwd)/$out"
