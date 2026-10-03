#!/bin/zsh
# CLPC 阶跃响应（H54 §7）：单 ANE 模型（L384，共享权重），调用间隔在两种之间来回切换，
# 用固件任务起止时间戳（kdebug 61b0125 / 61b0126）读出每个任务的档位随时间的变化；bondrun 记录每次切换的 mach 时间。只读：只记录事件。
# 用法（M6）：cd ~/anehal/hwx && sudo ./gov_step.sh
# 输出：gov_step/tasks.txt（tick id）、gov_step/phases_<名>.txt（切换时刻 tick、新间隔 us）、gov_step/<名>.txt
cd "$(dirname "$0")"
out=gov_step
mkdir -p $out && chown "$SUDO_USER" $out   # bondrun 以发起 sudo 的用户身份写 phases 文件
M=sweep/k1x1_512_h1w128_L384.mlmodelc
ktrace trace -t -N -f S0x061b -T 80 > $out/raw.txt 2>&1 &
KT=$!
sleep 1
# A：满频 ↔ 下限（间隔 0 ↔ 1000 us），每段约 1.5 s，6 个来回
sudo -u "$SUDO_USER" env BONDRUN_WARM=0.5 BONDRUN_SLEEP_SEQ="1000:270,0:900" BONDRUN_PHASES=$out/phases_A.txt ./bondrun $M 7020 > $out/A.txt 2>&1
sleep 3
# B：满频 ↔ 中间档（间隔 0 ↔ 200 us），每段约 1.5 s，5 个来回
sudo -u "$SUDO_USER" env BONDRUN_WARM=0.5 BONDRUN_SLEEP_SEQ="200:440,0:900" BONDRUN_PHASES=$out/phases_B.txt ./bondrun $M 6700 > $out/B.txt 2>&1
sleep 3
# C：长空闲后的恢复——间隔 0 连续 300 次后空闲 20/50/100/200/500 ms 再连续调用（用 usleep 的大间隔模拟）
sudo -u "$SUDO_USER" env BONDRUN_WARM=0.5 BONDRUN_SLEEP_SEQ="0:300,20000:1,0:300,50000:1,0:300,100000:1,0:300,200000:1,0:300,500000:1" BONDRUN_PHASES=$out/phases_C.txt ./bondrun $M 1505 > $out/C.txt 2>&1
wait $KT
grep -E " 61b01(25|26|a9) " $out/raw.txt | awk '{print $1, $3}' > $out/tasks.txt
rm -f $out/raw.txt
chown -R "$SUDO_USER" $out
echo "完成：$(wc -l < $out/tasks.txt) 条事件，结果在 $(pwd)/$out"
