#!/bin/zsh
# DRAM 档位与总带宽复测（不需要 sudo）：ANE 读权重（24 × 2 MiB 独立权重）与 GPU 只读带宽测试（1 GiB）同时运行，
# 同一段时间里用 IOReport 采样内存控制器档位驻留（DCS_F*）与 PMP 的 DRAM 带宽直方图。
# 用法（M6）：cd ~/anehal/hwx && ./dramco.sh
# 输出：dramco/{alone_ane,alone_gpu,co}_{iorep,ane,gpu}.txt
cd "$(dirname "$0")"
out=dramco
mkdir -p $out
m=chains/k1_c1024_h1w16_L24_u.mlmodelc
run() {  # $1 名字；$2 是否跑 ANE；$3 是否跑 GPU（两者都让其自然跑完：程序只在结束时输出）
  pids=()
  [[ $3 == 1 ]] && { MEMBW_DUMP=1 ./membw 1024 700 > $out/$1_gpu.txt 2>&1 & pids+=($!); }
  [[ $2 == 1 ]] && { ./bondrun $m 14000 > $out/$1_ane.txt 2>&1 & pids+=($!); }
  sleep 1.5
  ./iorlist DCS 2 > $out/$1_iorep.txt 2>&1
  wait $pids
  sleep 2
}
run alone_ane 1 0
run alone_gpu 0 1
run co 1 1
echo "完成：$(pwd)/$out"
