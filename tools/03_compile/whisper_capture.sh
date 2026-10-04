#!/bin/zsh
# 抓出 Core ML 交给 ANE 编译器的模型（Whisper AudioEncoder），以便不经 Core ML、用 anecc 复现 M6 上的编译失控。
# 用新进程名加载编码器（强制编译）；编译开始后，e5rt 缓存里会出现
#   ~/Library/Caches/<进程名>/com.apple.e5rt.e5bundlecache/<build>/<哈希>/<哈希>.tmp.*.bundle/H18G.bundle/main/main_ane/ane_mil_model/
# 等其中的 weights 文件大小稳定（连续 5 s 不变）后，复制整个 H18G.bundle，并列出 aned 缓存目录
# （/Library/Caches/com.apple.aned/<build>/ModelAssetsCache/<进程名>_unsigned/）里的文件；然后结束加载进程和 ANECompilerService。
# 最多 MAXS 秒；可用空间低于 15 GB 时立即结束。需要 root（结束 ANECompilerService、读 aned 缓存）。
# 用法（M6）：cd ~/anehal/hwx && sudo ./whisper_capture.sh <AudioEncoder.mlmodelc> [MAXS = 300]
# 输出：whisper_capture/H18G.bundle/、aned_files.txt、e5rt_files.txt、free.txt、result.txt
cd "$(dirname "$0")"
M=$1; MAXS=${2:-300}
U=${SUDO_USER:-$USER}
H=$(eval echo ~$U)
out=whisper_capture; rm -rf $out; mkdir -p $out
free_kb() { df -k / | awk 'NR==2 {print $4}'; }
name=cmload_cap$(date +%s)
cp cmload ./$name; chown "$U" ./$name
t0=$(date +%s)
sudo -u "$U" ./$name $M ane > $out/load.txt 2>&1 &
P=$!
got=0; last=-1; same=0; why="time limit"
while kill -0 $P 2>/dev/null; do
  s=$(( $(date +%s) - t0 )); f=$(free_kb)
  echo "$s $f" >> $out/free.txt
  d=$(ls -d $H/Library/Caches/$name/com.apple.e5rt.e5bundlecache/*/*/*.bundle/H18G.bundle/main/main_ane/ane_mil_model 2>/dev/null | head -1)
  if [[ -n $d ]]; then
    sz=$(du -sk $d | cut -f1)
    if (( sz == last && sz > 0 )); then (( same++ )); else same=0; fi
    last=$sz
    if (( same >= 5 )); then
      b=${d%/main/main_ane/ane_mil_model}
      cp -R $b $out/ && got=1
      find $H/Library/Caches/$name -type f -exec ls -l {} + > $out/e5rt_files.txt 2>/dev/null
      find /Library/Caches/com.apple.aned -path "*${name}_unsigned*" -type f -exec ls -l {} + > $out/aned_files.txt 2>/dev/null
      why="captured at ${s}s"
      break
    fi
  fi
  if (( s >= MAXS )); then break; fi
  if (( f < 15 * 1024 * 1024 )); then why="free < 15 GB"; break; fi
  sleep 1
done
kill $P 2>/dev/null; killall -9 ANECompilerService 2>/dev/null; wait $P 2>/dev/null
sleep 5
echo "$why; got=$got; bundle: $(du -sh $out/H18G.bundle 2>/dev/null | cut -f1); free after cleanup $(( $(free_kb) / 1048576 )) GB" | tee $out/result.txt
find $out/H18G.bundle -maxdepth 4 2>/dev/null | head -40 | tee -a $out/result.txt
rm -rf ./$name $H/Library/Caches/$name
chown -R "$U" $out
