#!/bin/zsh
# Whisper large-v3-turbo（WhisperKit Core ML 包）各子模型经 Core ML 加载到 ANE 的编译代价（ANECompilerService 编译）。
# anecc 直接编译这些包会失败（Core ML 先做自己的转换），所以用 cmload 走 Core ML 的正常加载路径。
# 每个子模型（从小到大）：
#   1. 复制 cmload 为新名字后加载（Core ML / aned 的缓存按进程名区分，新名字强制重新编译）
#   2. 用同一个名字再加载一次（检验编译结果是否被复用）
# 每秒记录可用空间和 ANECompilerService 的 CPU；可用空间低于 15 GB 时结束加载进程和 ANECompilerService，并跳过剩余模型。
# 同时用 log stream 记录 ANECompilerService 的系统日志。
# 用法（M6）：cd ~/anehal/hwx && sudo ./whisper_load.sh <模型目录> [子模型名 ...]
# 输出：wload/results.txt、wload/watch_<模型>_<轮>.txt（秒 可用KB 编译服务CPU）、wload/log_<模型>.txt
cd "$(dirname "$0")"
MD=$1; shift
if (( $# )); then NAMES=("$@"); else NAMES=(MelSpectrogram TextDecoderContextPrefill TextDecoder AudioEncoder); fi
U=${SUDO_USER:-$USER}
out=wload; mkdir -p $out; chown "$U" $out
free_kb() { df -k / | awk 'NR==2 {print $4}'; }
stop=0
for n in $NAMES; do
  (( stop )) && break
  exe=./cmload_w$(date +%s)_$n; cp cmload $exe; chown "$U" $exe
  log stream --style compact --predicate 'process == "ANECompilerService"' > $out/log_$n.txt 2>&1 &
  L=$!
  for round in fresh again; do
    f0=$(free_kb); lo=$f0; t0=$(date +%s)
    sudo -u "$U" $exe $MD/$n.mlmodelc ane > $out/load_${n}_$round.txt 2>&1 &
    P=$!
    : > $out/watch_${n}_$round.txt
    while kill -0 $P 2>/dev/null; do
      f=$(free_kb); (( f < lo )) && lo=$f
      c=$(ps -axo %cpu,comm | awk '/ANECompilerService/ {s+=$1} END {print s+0}')
      echo "$(( $(date +%s) - t0 )) $f $c" >> $out/watch_${n}_$round.txt
      if (( f < 15 * 1024 * 1024 )); then
        kill $P; killall -9 ANECompilerService; stop=1
        echo "$n $round 可用空间低于 15 GB，已结束加载和 ANECompilerService" >> $out/results.txt
      fi
      sleep 1
    done
    wait $P
    printf "%s %s %ds peak_GB=%.1f %s\n" $n $round $(( $(date +%s) - t0 )) $(( (f0 - lo) / 1048576.0 )) \
      "$(tr '\n' ' ' < $out/load_${n}_$round.txt)" | tee -a $out/results.txt
    (( stop )) && break
    sleep 5
  done
  kill $L 2>/dev/null
  rm -f $exe
done
chown -R "$U" $out
echo "完成，结果在 $(pwd)/$out"
