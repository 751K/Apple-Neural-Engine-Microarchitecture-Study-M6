#!/bin/zsh
# 把本仓库 tools/ 下各子目录的工具平铺同步到 M6 的 ~/anehal/hwx/（实验在那里运行，脚本按 ./bondrun 等相对路径调用）。
# 先按 shasum 比对，只传内容不同或 M6 上没有的文件；不删除 M6 上的任何东西，不同步编译产物和模型。
# （macOS 自带的 openrsync 在这种用法下只列清单、不实际传输，所以不用 rsync。）
# 用法：M6_HOST=user@host tools/deploy_m6.sh      同步
#       M6_HOST=user@host tools/deploy_m6.sh -n   预演，只列出会传的文件
# 同步后在 M6 上按需重新编译改动过的 C / Objective-C 工具（编译命令见各文件开头注释）。
set -e
cd "$(dirname "$0")"
M6=${M6_HOST:?set M6_HOST, e.g. export M6_HOST=user@m6-host.local}
typeset -A here
for f in */*; do
  [[ -f $f && $f != *__pycache__* && $f != *.pyc ]] || continue
  here[${f:t}]=$f
done
remote=$(ssh ${M6} "cd ~/anehal/hwx && shasum ${(k)here} 2>/dev/null" || true)
todo=()
for n in ${(k)here}; do
  l=$(shasum ${here[$n]} | cut -c1-40)
  r=$(print -r -- "$remote" | awk -v n="$n" '$2==n {print $1}')
  [[ $l == $r ]] || todo+=(${here[$n]})
done
print "需要同步 ${#todo} 个文件"
for f in $todo; do print "  $f"; done
[[ ${1:-} == -n || ${#todo} -eq 0 ]] && exit 0
scp -q $todo "${M6}:anehal/hwx/"   # 注意要写 ${M6}：zsh 会把 "$M6:a…" 里的 :a 当成路径修饰符
print "已同步到 ${M6}:~/anehal/hwx/"
