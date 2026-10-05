#!/bin/zsh
# 每个模型用独立的 CFFIXED_USER_HOME 跑一次 computeplan，使 E5 编译不命中已有缓存，并把分段器写出的
# analytics.mil（每个运算的后端支持、各后端估计耗时、选中的后端；图级启动/切换代价）拷到 ana/<集合>/<模型>.mil
cd ~/opdispatch
for set in iso ctx; do
  mkdir -p ana/$set
  for m in $set/*.mlpackage; do
    n=${${m:t}%.mlpackage}
    [[ -f ana/$set/$n.mil ]] && continue
    h=$PWD/home/$set/$n; mkdir -p $h
    CFFIXED_USER_HOME=$h ./computeplan cpune $m > /dev/null 2>&1
    f=$(find $h -name analytics.mil | head -1)
    [[ -n $f ]] && cp $f ana/$set/$n.mil || echo "$set/$n no analytics" >> ana/missing.txt
  done
done
echo ANADONE > ana/done.txt
