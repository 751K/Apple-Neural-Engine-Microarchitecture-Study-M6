#!/bin/zsh
# Whisper large-v3-turbo（WhisperKit 的 Core ML 包）各子模型的 ANE 编译代价：用 anecc 在本进程里调用 ANECCompile，
# 分别按 h18（M6）和 h16（M4）编译，每秒记录可用空间，得到编译用时、临时空间峰值和产物大小。
# 背景：M6 上 whisperkit-cli 加载全 ANE 组合要编译 20 多分钟，8 分钟内吃掉约 30 GB 临时空间；M4 上加载不到 1 秒。
# 安全：可用空间低于 15 GB 时结束 anecc 并跳过该次。不需要 root。
# 用法（M6）：cd ~/anehal/hwx && ./whisper_compile.sh <模型目录> [子模型名 ...]
# 输出：wcomp/results.txt（模型 架构 退出码 用时s 空间峰值GB 产物MB）、wcomp/free_<模型>_<架构>.txt（每秒可用空间 KB）
cd "$(dirname "$0")"
MD=$1; shift
if (( $# )); then NAMES=("$@"); else NAMES=(MelSpectrogram TextDecoderContextPrefill TextDecoder AudioEncoder); fi
out=wcomp; mkdir -p $out
free_kb() { df -k / | awk 'NR==2 {print $4}'; }
for n in $NAMES; do
  for arch in h18 h16; do
    o=/tmp/wcomp_${n}_$arch; rm -rf $o
    f0=$(free_kb); lo=$f0; t0=$(date +%s)
    ./anecc $MD/$n.mlmodelc $o $arch > $out/log_${n}_$arch.txt 2>&1 &
    P=$!; aborted=0
    : > $out/free_${n}_$arch.txt
    while kill -0 $P 2>/dev/null; do
      f=$(free_kb); (( f < lo )) && lo=$f
      echo "$(( $(date +%s) - t0 )) $f" >> $out/free_${n}_$arch.txt
      if (( f < 15 * 1024 * 1024 )); then kill $P; aborted=1; fi
      sleep 1
    done
    wait $P; rc=$?
    dt=$(( $(date +%s) - t0 ))
    sz=$(du -sk $o 2>/dev/null | awk '{print $1}')
    printf "%s %s rc=%s aborted=%s %ds peak_GB=%.1f out_MB=%.1f\n" $n $arch $rc $aborted $dt \
      $(( (f0 - lo) / 1048576.0 )) $(( ${sz:-0} / 1024.0 )) | tee -a $out/results.txt
    rm -rf $o
    sleep 5
  done
done
