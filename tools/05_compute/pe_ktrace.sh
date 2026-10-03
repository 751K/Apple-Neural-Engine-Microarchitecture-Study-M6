#!/bin/zsh
# PE 吞吐（H53 第 2 步补测，第三轮：256 通道 32²–64² 回归）：用固件任务起止时间戳（kdebug 61b0125 / 61b0126）测每次调用里每个 ANE 的任务时长，
# 排除主机侧开销。只读：只记录事件。
# 用法（M6）：cd ~/anehal/hwx && sudo ./pe_ktrace.sh
# 输出：pe_kt/<模型名>.txt（每行：mach 时间 debug-id cpu）；分析：KGLOB='pe_*.txt' python3 ks4_engines.py pe_kt
cd "$(dirname "$0")"
out=pe_kt
mkdir -p $out
names=()
for h in 32 40 48 56 64; do for op in add sc; do for L in 32 96; do names+=(pe_${op}_c256_h${h}w${h}_L$L); done; done; done
for name in $names; do
  [[ -s $out/$name.txt ]] && continue
  sudo -u "$SUDO_USER" ./bondrun pem/$name.mlmodelc 200000 > $out/$name.bondrun.txt 2>&1 &
  bp=$!
  sleep 4
  ktrace trace -t -N -f S0x061b -T 1 > $out/raw.txt 2>> $out/ktrace_err.txt
  grep -E " 61b012[56] | 61b01a9 " $out/raw.txt | awk '{print $1, $3, $(NF-1)}' > $out/$name.txt
  rm -f $out/raw.txt
  pkill -f "[b]ondrun pem/$name.mlmodelc"; wait $bp 2>/dev/null
  echo "$name 事件 $(wc -l < $out/$name.txt)"
done
chown -R "$SUDO_USER" $out
echo "完成，结果在 $(pwd)/$out"
