#!/bin/zsh
# 权重格式在读权重受限层上的收益（模型由 wfmt_gen.py 生成在 wfmt/）。
# 1. 每个模型用 anecc 编译成 HWX，记录所有 __KERN_<n>（权重和调色板）段的大小之和（hwx_kern.py；超过 128 MB 时拆成多个段）。
#    anecc 编译失败的格式，Core ML 会把整个模型放到 CPU 上执行。
# 2. 每个模型连续调用 T 秒，root 时用 kdebug 记录固件任务起止（61b0125 / 61b0126，带 cpu 列）和驱动提交（61b01a9），
#    得到每次调用的任务数和每个任务的时长；同时在运行中段用 iorlist 采样 SOC-NI 和 DCS BW 读带宽直方图
#    （M6 每个引擎 SOC-NI 两个端口、各到 64 GB/s，DCS BW 两条链路、各到 32 GB/s，读权重受限时只是下限）。
# 用法（M6）：cd ~/anehal/hwx && sudo ./wfmt.sh
# 输出：wfmt_out/kern_all.txt（字节数、段数）、run.txt（bondrun 输出）、ior_<模型>.txt、marks.txt、trace.txt
cd "$(dirname "$0")"
out=wfmt_out
mkdir -p $out
U=${SUDO_USER:-$USER}
MODELS=(wfmt/*.mlmodelc)
T=6
: > $out/kern_all.txt
for M in $MODELS; do
  n=${M:t:r}
  rm -rf /tmp/wfmt_hwx; sudo -u "$U" ./anecc $M /tmp/wfmt_hwx h18 > /dev/null 2>&1
  if [[ -f /tmp/wfmt_hwx/model.hwx ]]; then
    echo "$n $(python3 hwx_kern.py /tmp/wfmt_hwx/model.hwx)" >> $out/kern_all.txt
  else
    echo "$n failed 0" >> $out/kern_all.txt
  fi
done
typeset -A ITER                     # 预热一次（编译缓存就绪），按每次调用耗时算出跑 T 秒的调用次数
for M in $MODELS; do
  med=$(sudo -u "$U" ./bondrun $M 30 2>&1 | awk '/耗时 中位数/ {print $3}')
  ITER[$M]=$(( T * 1000000 / ${med%.*} ))
done
KT=
if (( EUID == 0 )); then
  ktrace trace -t -N -f S0x061b -T $(( ${#MODELS} * (T + 10) + 120 )) |
    awk '$3 ~ /^61b01(25|26|a9)$/ {print $1, $3, $(NF-1)}' > $out/trace.txt &
  KT=$!
  sleep 1
fi
: > $out/run.txt; : > $out/marks.txt
for M in $MODELS; do
  n=${M:t:r}
  sleep 3
  echo "$n $(date +%s)" >> $out/marks.txt
  echo "== $n" >> $out/run.txt
  sudo -u "$U" ./bondrun $M ${ITER[$M]} >> $out/run.txt 2>&1 &
  B=$!
  sleep 2
  ./iorlist "SOC-NI" 1 > $out/ior_$n.txt 2>&1
  ./iorlist "DCS BW" 1 >> $out/ior_$n.txt 2>&1
  wait $B
done
[[ -n $KT ]] && { pkill -INT -x ktrace; wait $KT; }
chown -R "$U" $out
echo "完成，结果在 $(pwd)/$out"
