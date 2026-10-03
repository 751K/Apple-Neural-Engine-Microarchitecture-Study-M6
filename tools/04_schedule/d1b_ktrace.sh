#!/bin/zsh
# D1b："任务以外每层约 0.48 µs"的来源。两组模型（层数相差 4 倍、任务时长重叠），记录每次调用的固件 / 驱动事件（只读）。
# A = k1_c512_h1w128_L{16..384}，B = k1_c1024_h1w128_L{4..96}（每层计算量是 A 的 4 倍）；
# 另对 A 的 L16 / L96 / L384 在 12 个 nice 20 空转进程下各测一次（CPU 无法深睡）。
# 用法（M6）：cd ~/anehal/hwx && sudo ./d1b_ktrace.sh
# 输出：d1b_kt/<模型名>[_spin].txt（abstime debug-id arg1 cpu）。bondrun 抓完即结束（模型需先预热，见 d1b_names.txt）
cd "$(dirname "$0")"
out=d1b_kt
mkdir -p $out
run() {  # $1 模型名，$2 输出名
  sudo -u "$SUDO_USER" ./bondrun d1b/$1.mlmodelc 30000 > $out/$2.bondrun.txt 2>&1 &
  bp=$!
  sleep 2.5
  ktrace trace -t -N -f S0x061b -T 2 > $out/raw.txt 2>> $out/ktrace_err.txt
  grep -E " 61b(0125|0126|00b8|0020|00a0|0170|0024|01a9) " $out/raw.txt | awk '{print $1, $3, $4, $(NF-1)}' > $out/$2.txt
  rm -f $out/raw.txt
  pkill -f "[b]ondrun d1b/$1.mlmodelc"; wait $bp 2>/dev/null
  echo "$2 事件 $(wc -l < $out/$2.txt)"
}
for n in $(cat d1b_names.txt); do run $n $n; done
pids=()
for i in {1..12}; do nice -n 20 sh -c 'while :; do :; done' & pids+=($!); done
sleep 1
for L in 16 96 384; do run k1_c512_h1w128_L$L k1_c512_h1w128_L${L}_spin; done
kill $pids
chown -R "$SUDO_USER" $out
echo "完成，结果在 $(pwd)/$out"
