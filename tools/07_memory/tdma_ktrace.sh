#!/bin/zsh
# Tile DMA 路数（第 2 步）：用固件任务起止时间戳（kdebug 61b0125 / 61b0126）测每次调用里每个 ANE 的任务时长，
# 排除主机侧开销。只读：只记录事件。
# 用法（M6）：cd ~/anehal/hwx && sudo ./tdma_ktrace.sh
# 输出：tdma_kt/<模型名>.txt（每行：mach 时间 debug-id cpu）；分析：KGLOB='*_s*.txt' python3 ks4_engines.py tdma_kt
cd "$(dirname "$0")"
out=tdma_kt
mkdir -p $out
names=(mul add2 self mulab two add3 add4)
for h in 128 192 256; do for k in $names; do
  name=${k}_s$h
  [[ -s $out/$name.txt ]] && continue
  sudo -u "$SUDO_USER" ./bondrun tdma/$name.mlmodelc 1000 > $out/$name.bondrun.txt 2>&1 &
  bp=$!
  sleep 4
  ktrace trace -t -N -f S0x061b -T 1 > $out/raw.txt 2>> $out/ktrace_err.txt
  grep -E " 61b012[56] | 61b01a9 " $out/raw.txt | awk '{print $1, $3, $(NF-1)}' > $out/$name.txt
  rm -f $out/raw.txt
  pkill -f "[b]ondrun tdma/$name.mlmodelc"; wait $bp 2>/dev/null
  echo "$name 事件 $(wc -l < $out/$name.txt)"
done; done
chown -R "$SUDO_USER" $out
echo "完成，结果在 $(pwd)/$out"
