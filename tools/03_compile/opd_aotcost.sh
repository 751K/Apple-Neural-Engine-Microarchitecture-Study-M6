#!/bin/zsh
# 用 Espresso 的 AOT 编译器（aotdrv）以不同目标平台编译同一批单算子 / 上下文模型，注入 oslogtap 抓 [CostModelFeature]
# （各后端逐运算估计），并保留分段后的 IR（10_dumped_Segmenter.mil）。输出 aotcost/<平台>/<模型>.tap 与 .seg.mil
cd ~/opdispatch
PY=/opt/miniconda3/envs/mps/bin/python
PLAT=(${=PLAT:-H13G H14G H16G H17G H18G H19})
MODELS=(${=MODELS:-iso/conv3x3 iso/conv1x1 iso/matmul_dyn iso/sdpa iso/layer_norm_c iso/softmax_c iso/topk_w iso/add iso/upsample_bilinear iso/reduce_sum_c iso/gather_c iso/transpose_hw ctx/relu ctx/reduce_sum_c ctx/topk_w ctx/conv1x1})
defaults write -g espresso.e5compiler.log_cost_model -bool YES
for m in $MODELS; do
  n=${m:t}; s=${m:h}; c=mlcaot/$s/$n.mlmodelc
  if [[ ! -d $c ]]; then
    mkdir -p mlcaot/$s
    $PY -c "import coremltools as ct, shutil; p = ct.utils.compile_model('$m.mlpackage'); shutil.move(str(p), '$c')" > /dev/null 2>&1
  fi
  for P in $PLAT; do
    o=$PWD/aotcost/$P/$s.$n; rm -rf $o.bundle; mkdir -p ${o:h}
    DYLD_INSERT_LIBRARIES=$PWD/oslogtap.dylib ./aotdrv -i $PWD/$c/model.mil -o $o --e5-platforms $P --e5-compute-units ane,cpu --e5-dump-ir-only 2> $o.tap > /dev/null
    cp $o.bundle/*/10_dumped_Segmenter.mil $o.seg.mil 2>/dev/null
    rm -rf $o.bundle
  done
done
defaults delete -g espresso.e5compiler.log_cost_model
echo AOTDONE > aotcost/done.txt
