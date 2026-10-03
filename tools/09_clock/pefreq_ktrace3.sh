#!/bin/zsh
# PE 跑在哪个时钟（H53，第三版）：卷积、PE L32、PE L96 三个进程同时从空闲开始调用，任务在 ANE 上交错执行，
# 同一时刻经历同一个时钟档位。三者任务时长互不重叠（卷积 1267–3810 µs，L96 466–1193，L32 174–439），按时长区分；
# 每个 PE 任务取时间上最近的卷积任务得出当时的 NE 档位，L96 − L32 之差与时钟成反比且不含固定部分。只读：只记录事件。
# 第二版：先启 PE、延迟 0.1–0.6 s 再启卷积（第一版三者同时启动时，卷积加载最快，独自把时钟升满后 PE 才开始）。
# 用法（M6）：cd ~/anehal/hwx && sudo ./pefreq_ktrace3.sh
# 输出：pefreq_kt3/trace.txt（mach 时间 debug-id cpu）
cd "$(dirname "$0")"
out=pefreq_kt3
mkdir -p $out
CONV=sweep/k1x1_512_h1w128_L384.mlmodelc
PE96=pem/pe_sc_c256_h64w64_L96.mlmodelc
PE32=pem/pe_sc_c256_h64w64_L32.mlmodelc
ktrace trace -t -N -f S0x061b -T 50 > $out/raw.txt 2>&1 &
KT=$!
sleep 1
# 先启动两个 PE 进程（PE 单独跑时升频很慢，时钟会在低档停留几十毫秒），间隔 dly 秒后再启动卷积进程作为"档位探针"
for dly in 0.1 0.2 0.3 0.4 0.5 0.6; do
  sleep 3
  sudo -u "$SUDO_USER" env BONDRUN_WARM=0 ./bondrun $PE96 700 > /dev/null 2>&1 &
  b=$!
  sudo -u "$SUDO_USER" env BONDRUN_WARM=0 ./bondrun $PE32 1500 > /dev/null 2>&1 &
  c=$!
  sleep $dly
  sudo -u "$SUDO_USER" env BONDRUN_WARM=0 ./bondrun $CONV 500 > /dev/null 2>&1 &
  a=$!
  wait $a $b $c
done
wait $KT
grep -E " 61b012[56] " $out/raw.txt | awk '{print $1, $3, $(NF-1)}' > $out/trace.txt
rm -f $out/raw.txt
chown -R "$SUDO_USER" $out
echo "完成：$(wc -l < $out/trace.txt) 条任务事件，结果在 $(pwd)/$out"
