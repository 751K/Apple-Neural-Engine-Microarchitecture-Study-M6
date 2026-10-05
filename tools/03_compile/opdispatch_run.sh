#!/bin/zsh
# 逐个模型跑 computeplan（每个模型一个进程，串行），带内存看门狗：computeplan 或 ANECompilerService 的 RSS
# 超过 LIMIT_MB 就杀掉，该模型记为 OOM。机器只有 16 GB，不要和其他 Core ML / coremltools 任务同时跑。
# 用法：opdispatch_run.sh <all|cpune> <输出.tsv> <模型.mlpackage> ... 2> <日志>（日志每个模型一行：耗时、两个进程的峰值内存）
# 输出文件里已有的模型跳过（可断点续跑）。
# 环境变量：CP=computeplan 可执行文件路径，LIMIT_MB（默认 10000），TMO 每个模型的超时秒数（默认 120）
mode=$1; out=$2; shift 2
CP=${CP:-./computeplan}; LIMIT_MB=${LIMIT_MB:-10000}; TMO=${TMO:-120}
for m in "$@"; do
  n=${${m:t}%.mlpackage}
  grep -q "^$n	" $out 2>/dev/null && continue
  $CP $mode $m >> $out 2>/dev/null &
  pid=$!; t=0; why=""; peak=0; speak=0
  while kill -0 $pid 2>/dev/null; do
    sleep 0.5; t=$((t + 1))
    rss=$(ps -o rss= -p $pid 2>/dev/null | tr -d ' '); rss=${rss:-0}
    svc=$(ps -axo rss=,comm= | awk '/ANECompilerService/ {s += $1} END {print s + 0}')
    (( rss > peak )) && peak=$rss; (( svc > speak )) && speak=$svc
    if (( rss / 1024 > LIMIT_MB || svc / 1024 > LIMIT_MB )); then why="OOM rss=$((rss/1024))MB svc=$((svc/1024))MB"; fi
    if (( t > TMO * 2 )); then why="TIMEOUT"; fi
    if [[ -n $why ]]; then
      kill -9 $pid 2>/dev/null
      pkill -9 -f ANECompilerService 2>/dev/null   # 编译服务会被 launchd 按需重新拉起
      echo "$n	-	$why	-	-	-	-" >> $out
      break
    fi
  done
  wait $pid 2>/dev/null
  echo "$n\t$((t / 2)) s\tpeak computeplan $((peak / 1024)) MB\tANECompilerService $((speak / 1024)) MB\t$why" >&2
done
