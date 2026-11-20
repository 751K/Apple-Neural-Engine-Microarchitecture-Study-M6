#!/bin/zsh
# 权重格式补充实验（wfmt2）的计时：每个模型用 bondrun（Core ML 公开接口）先预热一次，再按正序、倒序各测一轮，每次 N 次调用。
# 每层耗时取 32 层与 16 层调用耗时中位数之差除以 16。不需要 root。
# 用法：在放有 bondrun 的目录下，模型由 wfmt_gen.py 生成在 models/：./wfmt2_time.sh
cd "$(dirname "$0")"
N=${N:-400}
M=(models/m2048_{fp16,w8,p4,w4c,w4t,p4o2,p4o4}_L{16,32}.mlmodelc)
mkdir -p wfmt2_out; out=wfmt2_out/time.txt
for m in $M; do ./bondrun $m 20 > /dev/null 2>&1; done
for r in fwd rev; do
  L=($M); [[ $r == rev ]] && L=(${(Oa)M})
  for m in $L; do echo "== $r ${m:t:r}" >> $out; ./bondrun $m $N >> $out 2>&1; sleep 1; done
done
echo $out
