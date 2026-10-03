#!/bin/zsh
# PE 速度与 SOC 档位（H53）：kdebug 任务时长（61b0125 / 61b0126）与 IOReport SOC 档位（socsamp，约 25 ms 一个窗口，
# 同一 mach 时基）同时记录，按时间对齐。只读：只记录事件。
# 轮次（每轮前空闲 3 s）：A 只跑 PE L96 冷启动 ×4；B 只跑卷积 ×3；C GPU 读内存（membw）先跑 1.5 s 再冷启动 PE ×3。
# 用法（M6）：cd ~/anehal/hwx && sudo ./socpe_ktrace.sh
# 输出：socpe_kt/trace.txt（mach 时间 debug-id cpu）、socpe_kt/soc.txt（socsamp）、socpe_kt/marks.txt（每轮开始的 mach 时间与类型）
cd "$(dirname "$0")"
out=socpe_kt
mkdir -p $out
PE=pem/pe_sc_c256_h64w64_L96.mlmodelc
CONV=sweep/k1x1_512_h1w128_L384.mlmodelc
: > $out/marks.txt
ktrace trace -t -N -f S0x061b -T 75 > $out/raw.txt 2>&1 &
KT=$!
sudo -u "$SUDO_USER" ./socsamp 74 5 > $out/soc.txt 2> $out/soc_err.txt &
SP=$!
sleep 1
# 每轮开始时刻：CLOCK_UPTIME_RAW 的纳秒数 × 24 / 1000 = mach tick（24 MHz）
mark() { echo "$(python3 -c 'import time;print(time.clock_gettime_ns(time.CLOCK_UPTIME_RAW)*24//1000)') $1" >> $out/marks.txt; }
for r in 1 2 3 4; do sleep 3; mark A; sudo -u "$SUDO_USER" env BONDRUN_WARM=0 ./bondrun $PE 600 > /dev/null 2>&1; done
for r in 1 2 3; do sleep 3; mark B; sudo -u "$SUDO_USER" env BONDRUN_WARM=0 ./bondrun $CONV 400 > /dev/null 2>&1; done
for r in 1 2 3; do
  sleep 3
  sudo -u "$SUDO_USER" ./membw 1024 600 > /dev/null 2>&1 &
  g=$!
  sleep 1.5
  mark C
  sudo -u "$SUDO_USER" env BONDRUN_WARM=0 ./bondrun $PE 600 > /dev/null 2>&1
  wait $g
done
wait $KT
wait $SP
grep -E " 61b012[56] " $out/raw.txt | awk '{print $1, $3, $(NF-1)}' > $out/trace.txt
rm -f $out/raw.txt
chown -R "$SUDO_USER" $out
echo "完成：任务事件 $(wc -l < $out/trace.txt) 条，SOC 采样 $(wc -l < $out/soc.txt) 个"
