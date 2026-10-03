#!/bin/zsh
# 对目录里给定名字的 mlmodelc 逐个跑 bondrun，每行输出：名字 中位数us p10us ANE0中断/调用 ANE1中断/调用 ANE0计算时钟开启us/调用
# 用法：./runall.sh <目录> <次数> <名字> [<名字> ...]
dir=$1; n=$2; shift 2
for name in "$@"; do
  out=$(./bondrun "$dir/$name.mlmodelc" "$n" 2>&1)
  med=$(echo "$out" | sed -n 's/.*中位数 \([0-9.]*\) us  p10 \([0-9.]*\).*/\1 \2/p')
  a0=$(echo "$out" | sed -n 's/.*ANE0: 中断 *[0-9]*（\([0-9.]*\) 次.*/\1/p')
  a1=$(echo "$out" | sed -n 's/.*ANE1: 中断 *[0-9]*（\([0-9.]*\) 次.*/\1/p')
  dpe=$(echo "$out" | sed -n 's/.*计算时钟开启 \([0-9.]*\) us.*/\1/p')
  echo "$name $med $a0 $a1 $dpe"
done
