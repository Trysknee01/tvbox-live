#!/usr/bin/env bash
# 一键推到 GitHub (Trysknee01/tvbox-live)
# 用法:
#   1) 先去 GitHub 生成 PAT (勾 repo 权限): https://github.com/settings/tokens
#   2) export GHTOKEN=ghp_xxxx你的token
#   3) bash push.sh
set -e
cd "$(dirname "$(readlink -f "$0")")"

: "${GHTOKEN:?请先 export GHTOKEN=你的GitHub_PAT}"
USER=Trysknee01
REPO=tvbox-live

git init -q 2>/dev/null || true
git branch -M main 2>/dev/null || true
git config user.email "tvbox@local"
git config user.name "$USER"
git add .
git commit -q -m "tvbox live source: $(date -u +%Y-%m-%d)" || echo "  (无新改动)"

# 用 token 嵌入 URL 推送（仅本次，不写进 .git/config 明文之外）
URL="https://${GHTOKEN}@github.com/${USER}/${REPO}.git"
git remote remove origin 2>/dev/null || true
git remote add origin "$URL"
git push -u origin main

echo "=============================================="
echo " 推送完成 ✅"
echo " 1) 去仓库 Settings -> Pages -> Source 选 main /(root) -> Save"
echo " 2) 约 1 分钟后 TVBox 填:"
echo "      https://${USER}.github.io/${REPO}/live.txt"
echo "=============================================="
