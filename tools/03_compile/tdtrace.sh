#!/bin/zsh
# 动态跟踪 ANE 编译器生成 TD 的过程：lldb 在 ZinAneTd<24u>（M6 / h18g 的 TD 版本）的每个方法上设断点，
# 记录参数、调用者、层级和调用前后 TD 对象中各寄存器字的变化（tdtrace_lldb.py）。
# 前提：anecc 要带 get-task-allow 权限才能被 lldb 跟踪（不需要打开开发者模式）：
#   codesign -s - -f --entitlements tdtrace_ent.plist ./anecc
# 用法：cd <工具目录> && ./tdtrace.sh <模型目录> [名字[@选项=值,选项=值] ...]   输出：tdtrace/<运行名>.jsonl、.hwx、log.txt
#   带编译选项时运行名为 <名字>@<选项>（anecc 的额外参数，如 EnableIntermediateCompression=true）
# 2 层的小模型每个约 0.5–2 分钟；32 层的模型约 8 分钟（tdtrace_gen.py 生成模型）。
cd "$(dirname "$0")"
SRC=$1; shift
out=tdtrace; mkdir -p $out
if (( $# )); then NAMES=("$@"); else NAMES=(${SRC}/*.mlmodelc(:t:r)); fi
for spec in $NAMES; do
  m=${spec%%@*}; opts=(); [[ $spec == *@* ]] && opts=(${(s:,:)${spec#*@}})
  n=${spec//=/-}; n=${n//,/+}
  [[ -s $out/$n.jsonl && -f $out/$n.hwx ]] && continue
  rm -rf /tmp/tdtrace_hwx
  t0=$(date +%s)
  lldb --batch -o "command script import tdtrace_lldb.py" -o "dt_run $out/$n.jsonl" -- \
    ./anecc $SRC/$m.mlmodelc /tmp/tdtrace_hwx h18g $opts > $out/$n.lldb.txt 2>&1
  [[ -f /tmp/tdtrace_hwx/model.hwx ]] && cp /tmp/tdtrace_hwx/model.hwx $out/$n.hwx
  echo "$n $(( $(date +%s) - t0 ))s 调用 $(wc -l < $out/$n.jsonl | tr -d ' ') $(grep -o 'ANECCompile returned [0-9-]*' $out/$n.lldb.txt)" | tee -a $out/log.txt
done
