#!/bin/zsh
# PE 跑在哪个时钟（H53，第二版：加 L32 模型，用 L96 − L32 的差消去不随时钟变化的固定部分）：卷积模型与 PE 模型轮流从空闲开始连续调用，用固件任务起止时间戳（kdebug 61b0125 / 61b0126，
# 带 cpu 列区分 ANE0 / ANE1）记录升频过程中每个任务的时长。卷积任务的台阶给出升频经过的 NE 档位；
# PE 任务的台阶再分别按"NE 时钟"和"L2 时钟（编译器 GetMapNEToL2Frequencies 映射）"拟合。只读：只记录事件。
# 用法（M6）：cd ~/anehal/hwx && sudo ./pefreq_ktrace2.sh
# 输出：pefreq_kt2/trace.txt（mach 时间 debug-id cpu）、pefreq_kt2/order.txt（每轮的模型）
cd "$(dirname "$0")"
out=pefreq_kt2
mkdir -p $out
CONV=sweep/k1x1_512_h1w128_L384.mlmodelc
PE=pem/pe_sc_c256_h64w64_L96.mlmodelc
PE32=pem/pe_sc_c256_h64w64_L32.mlmodelc
: > $out/order.txt
ktrace trace -t -N -f S0x061b -T 70 > $out/raw.txt 2>&1 &
KT=$!
sleep 1
for r in 1 2 3 4 5; do
  for m in $PE32 $PE $CONV; do
    sleep 2.5
    echo "$r $m" >> $out/order.txt
    sudo -u "$SUDO_USER" env BONDRUN_WARM=0 ./bondrun $m 700 > /dev/null 2>&1
  done
done
wait $KT
grep -E " 61b012[56] " $out/raw.txt | awk '{print $1, $3, $(NF-1)}' > $out/trace.txt
rm -f $out/raw.txt
chown -R "$SUDO_USER" $out
echo "完成：$(wc -l < $out/trace.txt) 条任务事件，结果在 $(pwd)/$out"
