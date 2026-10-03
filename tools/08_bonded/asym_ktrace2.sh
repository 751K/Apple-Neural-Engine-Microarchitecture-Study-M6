#!/bin/zsh
# 同 asym_ktrace.sh，但模型由参数给出（asym/ 目录下的名字，不带 .mlmodelc）。只读：只记录事件。
# 用法（M6）：cd ~/anehal/hwx && sudo ./asym_ktrace2.sh k1_c128_h1w24576_L8 k1_c128_h1w24576_L40 ...
# 输出：asym_kt2/<模型名>.txt（abstime debug-id cpu）、同名 .bondrun.txt
cd "$(dirname "$0")"
out=asym_kt2
mkdir -p $out
for m in "$@"; do
  sudo -u "$SUDO_USER" ./bondrun asym/$m.mlmodelc 3000 > $out/$m.bondrun.txt 2>&1 &
  sleep 2.5
  ktrace trace -t -N -f S0x061b -T 2 > $out/raw.txt 2> $out/ktrace_err.txt
  grep -E " 61b012[56] | 61b01a9 " $out/raw.txt | awk '{print $1, $3, $(NF-1)}' > $out/$m.txt
  rm -f $out/raw.txt
  wait
  echo "$m $(grep -h 中位数 $out/$m.bondrun.txt | sed 's/  */ /g') 事件 $(wc -l < $out/$m.txt)"
done
chown -R "$SUDO_USER" $out
echo "完成，结果在 $(pwd)/$out"
