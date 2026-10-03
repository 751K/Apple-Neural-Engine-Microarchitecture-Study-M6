#!/bin/zsh
# 卷积核形状扫描第 4 轮：用固件任务起止时间戳（kdebug 61b0125 / 61b0126）测每次调用的 ANE 任务时长，
# 同时由事件的 cpu 列（36 = ANE0，33 = ANE1）判断实际用了几个 ANE。只读：只记录事件。
# 用法（M6）：cd ~/anehal/hwx && sudo ./ks4_ktrace.sh [列表文件=ks4_list.txt]
# 列表文件每行：<模型名> <调用次数>（次数按预热时的单次耗时取，使运行约 3 s）
# 输出：ks4_kt/<模型名>.txt（每行：mach 时间 debug-id cpu）
cd "$(dirname "$0")"
list=${1:-ks4_list.txt}
out=ks4_kt
mkdir -p $out
n=0; tot=$(wc -l < $list)
while read name cnt; do
  n=$((n + 1))
  [[ -s $out/$name.txt ]] && continue
  sudo -u "$SUDO_USER" ./bondrun ks4/$name.mlmodelc $cnt > $out/$name.bondrun.txt 2>&1 &
  sleep 1.5
  ktrace trace -t -N -f S0x061b -T 1 > $out/raw.txt 2>> $out/ktrace_err.txt
  grep -E " 61b012[56] | 61b01a9 " $out/raw.txt | awk '{print $1, $3, $(NF-1)}' > $out/$name.txt
  rm -f $out/raw.txt
  wait
  echo "[$n/$tot] $name 事件 $(wc -l < $out/$name.txt)"
done < $list
chown -R "$SUDO_USER" $out
echo "完成，结果在 $(pwd)/$out"
