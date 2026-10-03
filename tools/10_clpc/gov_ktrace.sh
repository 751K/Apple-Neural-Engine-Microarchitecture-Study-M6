#!/bin/zsh
# ANE 调频（CLPC）规律：在不同调用间隔下，用固件任务起止时间戳（kdebug 61b0125 / 61b0126）读出每个任务的时长（→ 档位）
# 和任务之间的 ANE 空闲间隙。模型为单 ANE、共享权重的纯计算链（每任务周期数固定，时长 ∝ 1 / 频率）。只读：只记录事件。
# 用法（M6）：cd ~/anehal/hwx && sudo ./gov_ktrace.sh
# 输出：gov_kt/trace.txt（时间戳 tick、debug-id；保留 0x061b 类全部事件）、gov_kt/G<间隔>.txt（bondrun 输出）、gov_kt/marks.txt
cd "$(dirname "$0")"
out=gov_kt
mkdir -p $out
M=sweep/k1x1_512_h1w128_L384.mlmodelc
GS=(0 100 150 200 300 400 1000 3000)
ktrace trace -t -N -f S0x061b -T 75 > $out/raw.txt 2>&1 &
KT=$!
sleep 1
: > $out/marks.txt
for G in $GS; do
  sleep 3
  n=$(( 3500000 / (1650 + G) ))
  echo "$G $(date +%s)" >> $out/marks.txt
  sudo -u "$SUDO_USER" env BONDRUN_SLEEP_US=$G ./bondrun $M $n > $out/G$G.txt 2>&1
done
wait $KT
grep -E " 61b0[0-9a-f]{3} " $out/raw.txt | awk '{print $1, $3}' > $out/trace.txt
rm -f $out/raw.txt
chown -R "$SUDO_USER" $out
echo "完成：$(wc -l < $out/trace.txt) 条事件，结果在 $(pwd)/$out"
