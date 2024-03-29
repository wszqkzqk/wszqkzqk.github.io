#!/bin/bash
cd `dirname $0`; pwd

# 指定仓库地址(注意：对于gitee仓库应当用小写字母)
repoinfo="wszqkzqk/wszqkzqk.github.io.git"
mirrorrepoinfo="wszqkzqk/wszqkzqk.git"

# 添加更改
echo "正在添加变更文件……"
git add *
git add .gitignore
git commit -S -m 'Updated by update.sh'

# 合并远端更改
echo "正在合并远端更改……"
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
echo "正在向主仓库推送……"
git push origin
echo "正在向镜像仓库推送……"
git push mirror
