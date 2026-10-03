#!/bin/zsh
# ANE 实际运行频率：用固件的任务起止时间戳（kdebug 61b0125 / 61b0126）记录每个任务的时长。
# 模型是纯计算、共享权重（不读 DRAM）的单 ANE 链，每个任务的周期数固定，所以 任务时长 ∝ 1 / 频率。
# 每轮先空闲 2 s 让时钟降下来，再连续调用，记录从低频爬升到满频的全过程。只读：只记录事件。
# 用法（M6）：cd ~/anehal/hwx && sudo ./freq_ktrace.sh
# 输出：freq_kt/trace.txt（只保留任务开始 / 结束事件）、freq_kt/bondrun_<轮>.txt
cd "$(dirname "$0")"
out=freq_kt
mkdir -p $out
M=${1:-sweep/k1x1_512_h1w128_L384.mlmodelc}

ktrace trace -t -N -f S0x061b -T 40 > $out/raw.txt 2>&1 &
KT=$!
sleep 1
for r in 1 2 3 4 5 6; do
  sleep 2.5
  sudo -u "$SUDO_USER" env BONDRUN_WARM=0 ./bondrun $M 800 > $out/bondrun_$r.txt 2>&1
done
wait $KT
grep -E " 61b012[56] " $out/raw.txt | awk '{print $1, $3}' > $out/trace.txt
rm -f $out/raw.txt
chown -R "$SUDO_USER" $out
echo "完成：$(wc -l < $out/trace.txt) 条任务事件，结果在 $(pwd)/$out"
