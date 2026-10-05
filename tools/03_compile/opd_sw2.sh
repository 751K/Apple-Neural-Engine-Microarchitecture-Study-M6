#!/bin/zsh
# 第二轮边界扫描：逐个模型跑（独立缓存目录），记录 ANECompilerService（root 进程，所有进程合计）的峰值 RSS
cd ~/opdispatch
PY=/opt/miniconda3/envs/mps/bin/python
N=(${(f)"$($PY -c 'import sys;sys.path.insert(0,".");import opdispatch_gen as g;print("\n".join(n for n in g.CASES if n.startswith("sw_")))' 2>/dev/null | grep '^sw_')"})
$PY opdispatch_gen.py iso $N > gen_sw2.log 2>&1
: > sw2_mem.tsv
for n in sw_conv_k13 sw_conv_k16 $N; do
  [[ -f ana/iso/$n.mil && $n != sw_conv_k13 && $n != sw_conv_k16 ]] && continue
  h=$PWD/home/sw2/$n; rm -rf $h; mkdir -p $h
  CFFIXED_USER_HOME=$h ./computeplan cpune iso/$n.mlpackage > /dev/null 2>&1 &
  pid=$!; peak=0; t0=$SECONDS
  while kill -0 $pid 2>/dev/null; do
    s=$(ps -axo rss=,comm= | awk '/ANECompilerService/ {s += $1} END {print s + 0}'); (( s > peak )) && peak=$s
    sleep 0.5
  done
  f=$(find $h -name analytics.mil | head -1); [[ -n $f ]] && cp $f ana/iso/$n.mil
  echo "$n\t$((SECONDS - t0)) s\tANECompilerService peak $((peak / 1024)) MB" >> sw2_mem.tsv
done
echo SW2DONE >> sw2_mem.tsv
