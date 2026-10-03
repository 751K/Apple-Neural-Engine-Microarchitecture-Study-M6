#!/bin/zsh
# 验证编译器性能模型的"高档"乘加（FP16 512 / INT8 1024 每 NE 每周期）：用固件任务起止时间戳（kdebug 61b0125 / 61b0126 / 61b01a9）
# 读每次调用里每个 ANE 的忙碌时间，排除主机开销与双 ANE 切分的影响。只读：只记录事件。
# 用法（M6）：cd ~/anehal/hwx && sudo ./hi_ktrace.sh
# 输出：hi_kt/<模型名>.txt（mach 时间 debug-id cpu）；分析：python3 hi_fit.py hi_kt
cd "$(dirname "$0")"
out=hi_kt
mkdir -p $out
names=()
for s in d1_k2_c256_h32w64 d1_k2_c128_h64w64 d1_k1_c256_h32w64 d1_k1_c128_h64w64; do for m in f16 q8; do for L in 4 12; do names+=(val3/${s}_L${L}_$m); done; done; done
for name in $names; do
  b=${name:t}
  [[ -s $out/$b.txt ]] && continue
  sudo -u "$SUDO_USER" ./bondrun $name.mlmodelc 200000 > /dev/null 2>&1 &
  bp=$!
  sleep 4
  ktrace trace -t -N -f S0x061b -T 2 > $out/raw.txt 2>> $out/ktrace_err.txt
  grep -E " 61b012[56] | 61b01a9 " $out/raw.txt | awk '{print $1, $3, $(NF-1)}' > $out/$b.txt
  rm -f $out/raw.txt
  pkill -f "[b]ondrun $name.mlmodelc"; wait $bp 2>/dev/null
  echo "$b 事件 $(wc -l < $out/$b.txt)"
done
chown -R "$SUDO_USER" $out
echo "完成，结果在 $(pwd)/$out"
