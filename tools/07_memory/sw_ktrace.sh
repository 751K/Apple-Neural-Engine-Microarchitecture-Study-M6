#!/bin/zsh
# 48 MiB 切换：两种状态下每次调用里固件发出的 kdebug 事件（类 0x06 IOKit，子类 0x1b ANE）是否不同。
# 同时抓 S0x0105（中断）用于对照中断次数。只读：只记录事件，不改任何设置。
# 用法（M6）：cd ~/anehal/hwx && sudo ./sw_ktrace.sh
# 输出：sw_kt/<标签>.txt（ktrace 原始事件）和 sw_kt/<标签>.bondrun.txt
cd "$(dirname "$0")"
out=sw_kt
mkdir -p $out

run() {  # run <标签> <mlmodelc>
  echo "== $1"
  sudo -u "$SUDO_USER" ./bondrun "$2" 8000 > "$out/$1.bondrun.txt" 2>&1 &
  sleep 2.5  # 越过预热
  ktrace trace -t -N -f S0x061b,S0x0105 -T 2 > "$out/$1.txt" 2>&1
  wait
  grep -h -E "中位数|ANE0:" "$out/$1.bondrun.txt" | sed "s/  */ /g" | cut -c1-70
}

run L96_a  chains/k1_c512_h1w16_L96_u.mlmodelc
run L104_a chains/k1_c512_h1w16_L104_u.mlmodelc
run L100_a chains/k1_c512_h1w16_L100_u.mlmodelc
run L96_b  chains/k1_c512_h1w16_L96_u.mlmodelc
run L104_b chains/k1_c512_h1w16_L104_u.mlmodelc
run L100_b chains/k1_c512_h1w16_L100_u.mlmodelc
chown -R "$SUDO_USER" $out
echo "完成，结果在 $(pwd)/$out"
