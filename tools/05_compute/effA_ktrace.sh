#!/bin/zsh
# 效应 A：层数增加时主机侧开销从约 166 µs 涨到约 350 µs，拆成各阶段。
# 记录 kdebug 子类 0x061b 中与一次调用相关的事件（只读）。用法（M6）：cd ~/anehal/hwx && sudo ./effA_ktrace.sh
# 输出：effA_kt/<层数>.txt（abstime debug-id arg1 cpu）、effA_kt/<层数>.bondrun.txt
cd "$(dirname "$0")"
out=effA_kt
mkdir -p $out
for L in 16 20 24 28 36 48; do
  sudo -u "$SUDO_USER" ./bondrun b6x/k1_c512_h32w32_L$L.mlmodelc 4000 > $out/$L.bondrun.txt 2>&1 &
  sleep 2.5
  ktrace trace -t -N -f S0x061b -T 2 > $out/raw.txt 2> $out/ktrace_err.txt
  grep -E " 61b(0125|0126|00b8|0020|00a0|0170|0024|01a9) " $out/raw.txt | awk '{print $1, $3, $4, $(NF-1)}' > $out/$L.txt
  rm -f $out/raw.txt
  wait
  echo "L$L $(grep -h 中位数 $out/$L.bondrun.txt | sed 's/  */ /g') 事件 $(wc -l < $out/$L.txt)"
done
chown -R "$SUDO_USER" $out
echo "完成，结果在 $(pwd)/$out"
