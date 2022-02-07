#!/bin/bash
cd `dirname $0`; pwd

# 指定仓库地址
repoinfo="wszqkzqk/wszqkzqk.github.io.git"

# 添加更改
git add *
git add .gitignore
git commit -m 'Updated by update.sh'

# 合并远端更改
git pull git@github.com:${repoinfo}

# 检测是否存在镜像仓库，如果不存在，进行添加
flag=1
for i in $(git remote);do
    if [[ ${i} == mirror ]];then
        flag=0
    fi
done

# 如果不存在镜像仓库，进行添加
if [[ ${flag} == 1 ]];then
    git remote add mirror git@gitee.com:${repoinfo}
fi

# 进行推送
git push origin
git push mirror
