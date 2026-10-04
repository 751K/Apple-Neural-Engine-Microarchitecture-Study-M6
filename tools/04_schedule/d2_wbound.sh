#!/bin/zsh
# D2 的读权重受限版本（验证 10.7 节）：两个进程分别占用两个 ANE 时，读权重受限的模型合计吞吐是否仍约 1.8 倍。
# 三个只用 ANE0 的模型，每个测三种情况：单个进程；两个进程同一个模型文件；两个进程各用一份模型文件（先各跑一次预编译）。
#   主测  k1x9_c256_h4w32_L80：1×9 卷积、256 通道、4×32、80 层、共享权重，每层约 17 µs ≈ 2.53 MB ÷ 150 GB/s
#   中间  k1x9_c256_h8w32_L80：同上，8×32（实测与 4×32 同样受读权重限制）
#   对照  sweep/k1x1_512_h1w128_L384：D2 原模型，权重常驻片上
# 以 root 运行时同时用 kdebug 记录固件任务起止（61b0125 / 61b0126，带 cpu 列区分 ANE0 / ANE1），得到每个引擎的单个任务时长。
# 用法（M6）：cd ~/anehal/hwx && sudo ./d2_wbound.sh
# 输出：d2_wb/run.txt（每段的 bondrun 输出）、d2_wb/marks.txt、d2_wb/trace.txt（root 时）
cd "$(dirname "$0")"
out=d2_wb
mkdir -p $out
MODELS=(gt/k1x9_c256_h4w32_L80.mlmodelc gt/k1x9_c256_h8w32_L80.mlmodelc sweep/k1x1_512_h1w128_L384.mlmodelc)
N=3000
U=${SUDO_USER:-$USER}
run() { sudo -u "$U" ./bondrun "$@"; }
for M in $MODELS; do                      # 第二份文件：复制后各跑一次，让编译缓存就绪
  C=${M:h}/copy_${M:t}
  [[ -d $C ]] || cp -R $M $C
  run $M 50 > /dev/null 2>&1; run $C 50 > /dev/null 2>&1
done
KT=
if (( EUID == 0 )); then
  ktrace trace -t -N -f S0x061b -T $(( ${#MODELS} * 75 + 30 )) |
    awk '$3 ~ /^61b012[56]$/ {print $1, $3, $(NF-1)}' > $out/trace.txt &
  KT=$!
  sleep 1
fi
: > $out/run.txt; : > $out/marks.txt
for M in $MODELS; do
  C=${M:h}/copy_${M:t}
  for case in single same copies; do
    sleep 3
    echo "${M:t:r} $case $(date +%s)" >> $out/marks.txt
    echo "== ${M:t:r} $case" >> $out/run.txt
    case $case in
      single) run $M $N >> $out/run.txt 2>&1 ;;
      same)   run $M $N > $out/a.txt 2>&1 & A=$!; run $M $N > $out/b.txt 2>&1; wait $A
              cat $out/a.txt $out/b.txt >> $out/run.txt ;;
      copies) run $M $N > $out/a.txt 2>&1 & A=$!; run $C $N > $out/b.txt 2>&1; wait $A
              cat $out/a.txt $out/b.txt >> $out/run.txt ;;
    esac
  done
done
rm -f $out/a.txt $out/b.txt
[[ -n $KT ]] && { pkill -INT -x ktrace; wait $KT; }
chown -R "$U" $out
echo "完成，结果在 $(pwd)/$out"
