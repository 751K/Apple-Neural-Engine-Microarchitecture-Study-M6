#!/bin/zsh
# Whisper AudioEncoder 经 Core ML 加载到 ANE 时，ANECompilerService 写了什么、写在哪里（whisper_load.sh 的后续：
# M6 上编码器编译 7 分钟、44 GB 仍未完成）。用新进程名加载编码器（强制编译），每秒记录可用空间；
# 每 30 s 列出编译开始后新建或改动的、大于 100 MB 的文件，以及各自所在目录的总大小，并记录 ANECompilerService 打开的文件。
# 最多运行 MAXS 秒，或可用空间低于 MINGB 时结束：结束加载进程和 ANECompilerService（需要 root），让临时文件释放。
# 用法：sudo ./whisper_tmp.sh <AudioEncoder.mlmodelc> [最长秒数 = 240] [最低可用 GB = 15]
#       M4 内置盘空间小，用：sudo ./whisper_tmp.sh <模型> 180 6
# 输出：wtmp_<机器>/free.txt（秒 可用KB 编译服务CPU）、files_<秒>.txt、lsof_<秒>.txt、result.txt
cd "$(dirname "$0")"
M=$1; MAXS=${2:-240}; MINGB=${3:-15}
U=${SUDO_USER:-$USER}
out=wtmp_$(sysctl -n hw.model | tr ',' '_'); rm -rf $out; mkdir -p $out
free_kb() { df -k / | awk 'NR==2 {print $4}'; }
mark=$out/.start; touch $mark
exe=./cmload_t$(date +%s); cp cmload $exe; chown "$U" $exe
f0=$(free_kb); lo=$f0; t0=$(date +%s)
sudo -u "$U" $exe $M ane > $out/load.txt 2>&1 &
P=$!
why="loaded"
while kill -0 $P 2>/dev/null; do
  s=$(( $(date +%s) - t0 )); f=$(free_kb); (( f < lo )) && lo=$f
  c=$(ps -axo %cpu,comm | awk '/ANECompilerService/ {s+=$1} END {print s+0}')
  echo "$s $f $c" >> $out/free.txt
  if (( s > 0 && s % 30 == 0 )); then
    find /private/var/folders /private/tmp /Users/$U/Library -xdev -type f -newer $mark -size +100M 2>/dev/null |
      while read -r x; do echo "$(du -k "$x" | cut -f1) $x"; done | sort -rn | head -30 > $out/files_$s.txt
    awk '{print $2}' $out/files_$s.txt | xargs -n1 dirname 2>/dev/null | sort -u |
      while read -r dd; do echo "$(du -sk "$dd" 2>/dev/null | cut -f1) $dd"; done | sort -rn > $out/dirs_$s.txt
    for p in $(pgrep -x ANECompilerService); do lsof -p $p 2>/dev/null; done | awk '$5=="REG"' | sort -k7 -rn | head -40 > $out/lsof_$s.txt
  fi
  if (( s >= MAXS )); then why="time limit ${MAXS}s"; break; fi
  if (( f < MINGB * 1024 * 1024 )); then why="free < ${MINGB} GB"; break; fi
  sleep 1
done
if kill -0 $P 2>/dev/null; then kill $P; killall -9 ANECompilerService 2>/dev/null; fi
wait $P 2>/dev/null
sleep 5
printf "%s %s: %ds, peak_GB=%.1f, free after cleanup %.1f GB, load: %s\n" "$(sysctl -n hw.model)" "$why" $(( $(date +%s) - t0 )) \
  $(( (f0 - lo) / 1048576.0 )) $(( $(free_kb) / 1048576.0 )) "$(tr '\n' ' ' < $out/load.txt)" | tee $out/result.txt
rm -f $exe $mark
chown -R "$U" $out
