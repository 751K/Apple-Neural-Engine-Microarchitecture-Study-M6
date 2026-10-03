#!/bin/zsh
# bonded 两边切块数不对称：分别记录 ANE0 / ANE1 的固件任务起止时间（kdebug 61b0125 / 61b0126，cpu 列 36 = ANE0、33 = ANE1）。
# 只读：只记录事件。用法（M6）：cd ~/anehal/hwx && sudo ./asym_ktrace.sh
# 输出：asym_kt/<宽度>.txt（abstime debug-id cpu）、asym_kt/<宽度>.bondrun.txt
cd "$(dirname "$0")"
out=asym_kt
mkdir -p $out
Ls=(${@:-40})
for L in $Ls; do
for W in 6144 8192 12288 16384; do
  [ -d asym/k1_c256_h1w${W}_L$L.mlmodelc ] || continue
  tag=$W; [ "$L" != 40 ] && tag=${W}_L$L
  sudo -u "$SUDO_USER" ./bondrun asym/k1_c256_h1w${W}_L$L.mlmodelc 3000 > $out/$tag.bondrun.txt 2>&1 &
  sleep 2.5
  ktrace trace -t -N -f S0x061b -T 2 > $out/raw.txt 2> $out/ktrace_err.txt
  grep -E " 61b012[56] | 61b01a9 " $out/raw.txt | awk '{print $1, $3, $(NF-1)}' > $out/$tag.txt
  rm -f $out/raw.txt
  wait
  echo "$tag $(grep -h 中位数 $out/$tag.bondrun.txt | sed 's/  */ /g') 事件 $(wc -l < $out/$tag.txt)"
done
done
chown -R "$SUDO_USER" $out
echo "完成，结果在 $(pwd)/$out"
