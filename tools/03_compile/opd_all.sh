#!/bin/zsh
# Air 上一次跑完：生成两套模型 → 逐个跑 compute plan（串行）
cd ~/opdispatch
PY=/opt/miniconda3/envs/mps/bin/python
$PY opdispatch_gen.py iso > gen_iso.log 2>&1
$PY opdispatch_gen.py --ctx ctx > gen_ctx.log 2>&1
./opdispatch_run.sh cpune plan_iso_cpune.tsv iso/*.mlpackage 2> run_iso_cpune.log
./opdispatch_run.sh all plan_iso_all.tsv iso/*.mlpackage 2> run_iso_all.log
./opdispatch_run.sh cpune plan_ctx_cpune.tsv ctx/*.mlpackage 2> run_ctx_cpune.log
echo ALLDONE > done.txt
