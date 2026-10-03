#!/bin/zsh
# 功耗测试（E3），用 SMC 读数，不需要 root。
# 每种负载：后台连续调用，3 s 后（预热、时钟爬升）用 smcpower 采 8 s。
# PP0b = ANE 电源轨（空闲时为 0），PSTR = 整机功率，其余为参考。
# 用法：cd ~/anehal/hwx && ./power_smc.sh > power_smc.txt
cd "$(dirname "$0")"
KEYS="PP0b PSTR PDTR PPMR PZC0 PZC1 PHPC"

measure() {  # measure <标签> <mlmodelc> <调用次数>
  ./bondrun "$2" "$3" > /tmp/ps_$1.txt 2>&1 &
  sleep 3
  echo "== $1"
  ./smcpower sample 8 ${=KEYS}
  wait
  grep -h "中位数" /tmp/ps_$1.txt
}

sleep 5
echo "== idle"
./smcpower sample 8 ${=KEYS}

measure fp16_single_compute  sweep/k1x1_512_h1w128_L384.mlmodelc     8000
measure fp16_dual_compute    sweep/k1x1_512_h1w256_L384.mlmodelc     8000
measure fp16_dual_L48        chains/k1_c512_h32w32_L48_u.mlmodelc    13000
measure w8a8_dual_L48        chains/k1_c512_h32w32_L48_u_q8.mlmodelc 18000
measure fp16_single_weightbw chains/k1_c512_h1w16_L192_u.mlmodelc    13000
measure fp16_single_small    sweep/k1x1_512_h1w128_L16.mlmodelc      60000
