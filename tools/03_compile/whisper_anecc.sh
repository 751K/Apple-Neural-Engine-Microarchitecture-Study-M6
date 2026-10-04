#!/bin/zsh
# 用 anecc 在本进程里编译抓出的 Whisper AudioEncoder ANE 模型（whisper_capture.sh 的产物：Core ML 转换后交给
# ANE 编译器的 model.mil + weights1.bin + options.plist），复现 M6 上的编译失控，并比较编译目标：
#   h16g（M4 目标）、h18（M6 单引擎目标，不生成双 ANE 程序）、h18g + Core ML 传的 EnableLowEffortCPAllocation、h18g 不加选项。
# 每秒记录 anecc 的内存（RSS）和可用空间；每 30 s 记录 anecc 打开的大文件（找交换文件）。
# 超过时限或可用空间低于 15 GB 时结束 anecc（本进程，不需要 root）。
# 用法（M6）：cd ~/anehal/hwx && ./whisper_anecc.sh <ane_mil_model 目录> [配置名 ...]
# 输出：wanecc/<配置>/model.hwx（成功时）、wanecc/<配置>.mon（秒 可用KB RSS_KB）、<配置>.lsof_<秒>、results.txt
cd "$(dirname "$0")"
SRC=$1; shift
typeset -A ARGS LIMIT
ARGS=(h16g "h16g" h18 "h18" h18g_lowcp "h18g h18g.EnableLowEffortCPAllocation=true" h18g "h18g")
LIMIT=(h16g 600 h18 600 h18g_lowcp 300 h18g 300)
if (( $# )); then CFGS=("$@"); else CFGS=(h16g h18 h18g_lowcp h18g); fi
out=wanecc; mkdir -p $out
free_kb() { df -k / | awk 'NR==2 {print $4}'; }
for c in $CFGS; do
  o=$out/$c; rm -rf $o
  t0=$(date +%s); f0=$(free_kb); lo=$f0; peak=0; why=done
  ./anecc $SRC $o ${=ARGS[$c]} > $out/$c.log 2>&1 &
  P=$!
  : > $out/$c.mon
  while kill -0 $P 2>/dev/null; do
    s=$(( $(date +%s) - t0 )); f=$(free_kb); r=$(ps -o rss= -p $P 2>/dev/null | tr -d ' ')
    (( f < lo )) && lo=$f; (( ${r:-0} > peak )) && peak=${r:-0}
    echo "$s $f ${r:-0}" >> $out/$c.mon
    (( s > 0 && s % 30 == 0 )) && lsof -p $P 2>/dev/null | awk '$5=="REG" && $7 > 100000000' > $out/$c.lsof_$s
    if (( s >= LIMIT[$c] )); then why="time limit ${LIMIT[$c]}s"; kill $P; break; fi
    if (( f < 15 * 1024 * 1024 )); then why="free < 15 GB"; kill $P; break; fi
    sleep 1
  done
  wait $P 2>/dev/null; rc=$?
  sleep 3
  hwx=$o/model.hwx
  k=$([[ -f $hwx ]] && python3 hwx_kern.py $hwx || echo "- -")
  printf "%-11s %s rc=%s %ds peak_rss=%.1fGB disk_peak=%.1fGB kern=%s hwx=%s after=%.1fGB\n" $c "$why" $rc $(( $(date +%s) - t0 )) \
    $(( peak / 1048576.0 )) $(( (f0 - lo) / 1048576.0 )) "${k% *}" "$([[ -f $hwx ]] && stat -f %z $hwx || echo -)" \
    $(( $(free_kb) / 1048576.0 )) | tee -a $out/results.txt
done
