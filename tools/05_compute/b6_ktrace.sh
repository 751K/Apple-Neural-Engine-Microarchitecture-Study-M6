#!/bin/zsh
# "FP16 在 32 层时反常地慢"：用固件任务起止时间戳（kdebug 61b0125 / 61b0126）把每次调用拆成 ANE 任务时长和其余部分。
# 只读：只记录事件。用法（M6）：cd ~/anehal/hwx && sudo ./b6_ktrace.sh
# 输出：b6_kt/<层数>.txt（任务开始 / 结束事件）、b6_kt/<层数>.bondrun.txt；ktrace 的错误输出在 b6_kt/ktrace_err.txt
cd "$(dirname "$0")"
out=b6_kt
mkdir -p $out
for L in 16 20 24 28 30 32 34 36 40 48; do
  m=b6x/k1_c512_h32w32_L$L.mlmodelc
  sudo -u "$SUDO_USER" ./bondrun $m 4000 > $out/$L.bondrun.txt 2>&1 &
  sleep 2.5
  ktrace trace -t -N -f S0x061b -T 2 > $out/raw.txt 2> $out/ktrace_err.txt
  grep -E " 61b012[56] | 61b01a9 " $out/raw.txt | awk '{print $1, $3, $(NF-1)}' > $out/$L.txt
  rm -f $out/raw.txt
  wait
  echo "L$L $(grep -h 中位数 $out/$L.bondrun.txt | sed 's/  */ /g') 事件 $(wc -l < $out/$L.txt)"
done
chown -R "$SUDO_USER" $out
echo "完成，结果在 $(pwd)/$out"
