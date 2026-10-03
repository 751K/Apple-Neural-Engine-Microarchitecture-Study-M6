#!/bin/zsh
# 汇总 sw_ktrace.sh 的结果：每个 debug-id 每次调用出现几次（以 61b01a9 计调用次数），各标签并排。
# 用法（M6）：cd ~/anehal/hwx && ./sw_ktrace_sum.sh
cd "$(dirname "$0")/sw_kt"
for f in *.txt(N); do
  [[ $f == *.bondrun.txt ]] && continue
  awk -v tag=${f%.txt} 'NR>2 && $3 ~ /^61b|^105/ {c[$3]++} END {n=c["61b01a9"]; for (k in c) printf "%s %s %.2f\n", tag, k, c[k]/n}' $f
done > /tmp/sw_sum.txt
tags=($(awk '{print $1}' /tmp/sw_sum.txt | sort -u))
printf "%-10s" id; for t in $tags; printf "%9s" $t; echo
for id in $(awk '{print $2}' /tmp/sw_sum.txt | sort -u); do
  printf "%-10s" $id
  for t in $tags; printf "%9s" $(awk -v t=$t -v i=$id '$1==t && $2==i {print $3}' /tmp/sw_sum.txt)
  echo
done
