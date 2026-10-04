#!/bin/zsh
# 10.7 节：单个进程用异步或批量提交，能否得到双进程那样的吞吐提升（d2_wbound 的后续）。
# 两个只用 ANE0 的模型（读权重受限的 1×9、权重常驻的 D2 原模型），每个依次测：
#   同步逐个调用；异步保持 1 / 2 / 4 个在途；批量每批 2 / 8 个；两个进程各自异步 2 个在途（各用一份模型文件）。
# 每种跑 T 秒，共两轮。root 时用 kdebug 记录固件任务起止（带 cpu 列），得到每个引擎的忙碌比例和任务时长。
# 用法（M6）：cd ~/anehal/hwx && sudo ./d2_async.sh      （不用 sudo 也能跑，只是没有 kdebug）
# 工具：asyncrun（tools/common/asyncrun.m）。输出：d2_as/run.txt、marks.txt、trace.txt（root 时）
cd "$(dirname "$0")"
out=d2_as
mkdir -p $out
U=${SUDO_USER:-$USER}
MODELS=(gt/k1x9_c256_h4w32_L80.mlmodelc sweep/k1x1_512_h1w128_L384.mlmodelc)
CASES=("sync" "async 1" "async 2" "async 4" "batch 2" "batch 8" "2proc async 2")
T=8
run() { sudo -u "$U" ./asyncrun "$@"; }
for M in $MODELS; do                      # 第二份文件（两个进程时用）；各跑一次让编译缓存就绪
  C=${M:h}/copy_${M:t}
  [[ -d $C ]] || sudo -u "$U" cp -R $M $C
  run $M 1 sync > /dev/null 2>&1; run $C 1 sync > /dev/null 2>&1
done
KT=
if (( EUID == 0 )); then
  ktrace trace -t -N -f S0x061b -T $(( 2 * ${#MODELS} * ${#CASES} * (T + 6) + 120 )) |
    awk '$3 ~ /^61b012[56]$/ {print $1, $3, $(NF-1)}' > $out/trace.txt &
  KT=$!
  sleep 1
fi
: > $out/run.txt; : > $out/marks.txt
for round in 1 2; do
  for M in $MODELS; do
    C=${M:h}/copy_${M:t}
    for c in $CASES; do
      a=(${=c})
      sleep 3
      echo "${M:t:r} ${c// /_} $round $(date +%s)" >> $out/marks.txt
      echo "== ${M:t:r} ${c// /_} $round" >> $out/run.txt
      if [[ $a[1] == 2proc ]]; then
        run $M $T $a[2,-1] > $out/a.txt 2>&1 & A=$!
        run $C $T $a[2,-1] > $out/b.txt 2>&1; wait $A
        cat $out/a.txt $out/b.txt >> $out/run.txt
      else
        run $M $T $a >> $out/run.txt 2>&1
      fi
    done
  done
done
rm -f $out/a.txt $out/b.txt
[[ -n $KT ]] && { pkill -INT -x ktrace; wait $KT; }
chown -R "$U" $out
echo "完成，结果在 $(pwd)/$out"
