#!/bin/zsh
# D1：拆分每次调用的固定开销。anemon 用 kdebug 固件事件得到 ANE 实际执行任务的时间，需要 root。
# 用法（M6）：cd ~/anehal/hwx && sudo ./d1_trace.sh
# 输出：d1_out/<标签>.json（anemon 每 2 s 一行）和 d1_out/<标签>.bondrun.txt
cd "$(dirname "$0")"
out=d1_out
mkdir -p $out
AN=/Users/$SUDO_USER/anemon-dev/.build/release/anemon

run() {  # run <标签> <mlmodelc> <调用次数>
  echo "== $1"
  sudo -u "$SUDO_USER" ./bondrun "$2" "$3" > "$out/$1.bondrun.txt" 2>&1 &
  sleep 3
  $AN --json --interval 2 --count 2 --no-power > "$out/$1.json" 2>&1
  wait
  grep -h "中位数" "$out/$1.bondrun.txt"
}

run small_L16   sweep/k1x1_512_h1w128_L16.mlmodelc   40000
run single_L384 sweep/k1x1_512_h1w128_L384.mlmodelc  6000
run dual_L384   sweep/k1x1_512_h1w256_L384.mlmodelc  6000
chown -R "$SUDO_USER" $out
echo "完成，结果在 $(pwd)/$out"
