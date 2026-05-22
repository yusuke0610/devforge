#!/usr/bin/env bash
# frontend の ts/tsx で「ユーザー向けの関数にリテラル日本語を渡す」パターンを検知する。
# 検知対象: setError("...") / setErrorMessage("...") / setAccountError("...") /
#           toast.error("...") / alert("...") に日本語リテラルを直接渡しているケース。
#
# ESLint の no-restricted-syntax は throw new Error の AST しか拾えないため、
# 関数呼び出し系はこのスクリプトで補完する。
#
# 詳細: .claude/rules/frontend/messages.md
set -euo pipefail

cd "$(dirname "$0")/../frontend"

# Rust regex (ripgrep -P) で Unicode プロパティを使って ひらがな・カタカナ・漢字 を検出する。
# シングルクォート文字列とバッククォート文字列の両方をカバー。
PATTERN='(set\w*Error\w*|toast\.error|alert)\(\s*["`][^"`]*[\p{Hiragana}\p{Katakana}\p{Han}]'

# 検出。一致が無くても exit 1 にならないよう `|| true`。
matches=$(
  rg -nP \
    -g 'src/**/*.ts' \
    -g 'src/**/*.tsx' \
    -g '!src/**/*.test.*' \
    -g '!src/test/**' \
    -g '!src/constants/messages.ts' \
    "$PATTERN" src \
    || true
)

if [ -n "$matches" ]; then
  echo "$matches"
  echo ""
  echo "ERROR: setError 等に日本語リテラルを直接渡しています。"
  echo "frontend/src/constants/messages.ts の定数を参照してください。"
  echo "詳細: .claude/rules/frontend/messages.md"
  exit 1
fi
