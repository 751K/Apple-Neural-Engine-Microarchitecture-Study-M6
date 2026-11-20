#!/bin/zsh
# NE 内部组织实验的计时（与 wfmt2_time.sh 相同的方法）：每个模型先预热（bondrun 内部另有 1 s 预热），再按正序、倒序各测一轮，每次 N 次调用。不需要 root。
# 每次 bondrun 限时 TMO 秒（默认 60），超时记为 TIMEOUT：深度超过约 386 层的链会使 Core ML 加载无限期挂起（报告缺陷 A1/A2）。
# 用法：./run_time.sh <输出文件> <mlmodelc> [...]
cd "$(dirname "$0")"
out=$1; shift; N=${N:-300}; M=($@); TMO=${TMO:-60}
run() { perl -e 'alarm shift; exec @ARGV' $TMO ./bondrun "$@" && return
  echo "TIMEOUT/失败：$1" | tee -a ${out}.err >&2; exit 3; }   # 一个超时多半说明 aned 被堵住，后面的都会超时，直接停
for m in $M; do run $m 20 > /dev/null; done
: > $out
for r in fwd rev; do
  L=($M); [[ $r == rev ]] && L=(${(Oa)M})
  for m in $L; do echo "== $r ${m:t:r}" >> $out; run $m $N >> $out 2>&1; sleep 1; done
done
