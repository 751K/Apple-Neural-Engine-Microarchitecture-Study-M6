#!/bin/zsh
# DRAM 总带宽：ANE 读权重（k1_c1024_h1w16_L24_u，24 层 × 2 MiB 独立权重）单独跑 / 与 GPU 只读带宽测试（membw）同时跑，
# 用固件任务结束事件（61b0126）和提交事件（61b01a9）得到 ANE 任务时长（只读）。
# 用法（M6）：cd ~/anehal/hwx && sudo ./bwco_ktrace.sh
# 输出：bwco_kt/{alone,co}.txt（abstime debug-id arg1 cpu）、bwco_kt/membw_{alone,co}.txt
cd "$(dirname "$0")"
out=bwco_kt
mkdir -p $out
m=chains/k1_c1024_h1w16_L24_u.mlmodelc
cap() {  # $1 输出名
  sudo -u "$SUDO_USER" ./bondrun $m 30000 > $out/$1.bondrun.txt 2>&1 &
  bp=$!
  sleep 2.5
  ktrace trace -t -N -f S0x061b -T 2 > $out/raw.txt 2>> $out/ktrace_err.txt
  grep -E " 61b(0126|01a9) " $out/raw.txt | awk '{print $1, $3, $4, $(NF-1)}' > $out/$1.txt
  rm -f $out/raw.txt
  pkill -f "[b]ondrun $m"; wait $bp 2>/dev/null
  echo "$1 事件 $(wc -l < $out/$1.txt)"
}
sudo -u "$SUDO_USER" ./membw 1024 300 > $out/membw_alone.txt
cap alone
sudo -u "$SUDO_USER" ./membw 1024 1200 > $out/membw_co.txt &
gp=$!
sleep 1
cap co
wait $gp
cat $out/membw_alone.txt $out/membw_co.txt
chown -R "$SUDO_USER" $out
echo "完成，结果在 $(pwd)/$out"
