#!/bin/bash
cd `dirname $0`; pwd
git add *
git add .gitignore
git commit -m 'Updated by update.sh'
git pull git@github.com:wszqkzqk/wszqkzqk.github.io.git
git push -u git@gitee.com:wszqkzqk/wszqkzqk.git
git push -u git@github.com:wszqkzqk/wszqkzqk.github.io.git

