#!/bin/zsh
# 让单 ANE（nonbonded）程序真正执行：同一模型两个进程并发，内核把请求分别派到空闲的 ANE。
# 用 kdebug 任务起止时间戳（61b0125 / 61b0126，带 cpu 列）看每个任务落在哪个 ANE、持续多久。只读：只记录事件。
# 用法（M6）：cd ~/anehal/hwx && sudo ./hi2_ktrace.sh
# 输出：hi2_kt/<模型名>.txt；分析：python3 hi2_fit.py hi2_kt
cd "$(dirname "$0")"
out=hi2_kt
mkdir -p $out
names=()
for s in d1_k2_c256_h32w64 d1_k1_c256_h32w64 d1_k2_c128_h64w64; do for m in f16 q8; do for L in 4 12; do names+=(val3/${s}_L${L}_$m); done; done; done
for name in $names; do
  b=${name:t}
  [[ -s $out/$b.txt ]] && continue
  sudo -u "$SUDO_USER" ./bondrun $name.mlmodelc 200000 > /dev/null 2>&1 &
  p1=$!
  sudo -u "$SUDO_USER" ./bondrun $name.mlmodelc 200000 > /dev/null 2>&1 &
  p2=$!
  sleep 5
  ktrace trace -t -N -f S0x061b -T 2 > $out/raw.txt 2>> $out/ktrace_err.txt
  grep -E " 61b012[56] | 61b01a9 " $out/raw.txt | awk '{print $1, $3, $(NF-1)}' > $out/$b.txt
  rm -f $out/raw.txt
  pkill -f "[b]ondrun $name.mlmodelc"; wait $p1 $p2 2>/dev/null
  echo "$b 事件 $(wc -l < $out/$b.txt)"
done
chown -R "$SUDO_USER" $out
echo "完成，结果在 $(pwd)/$out"
