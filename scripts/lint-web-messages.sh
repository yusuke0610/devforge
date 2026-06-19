#!/usr/bin/env bash
# web の ts/tsx で「ユーザー向けの関数にリテラル日本語を渡す」パターンを検知する。
# 検知対象:
#   - setError("...") / setErrorMessage("...") / setAccountError("...")
#   - setSuccess("...") / setInfo("...") / setMessage("...")（成功・情報トースト）
#   - toast.error("...") / alert("...")
#   - toAppError(e, "...")（fallback メッセージをヘルパー第2引数に直書きするケース）
# のいずれかに日本語リテラルを直接渡しているケース。
#
# ESLint の no-restricted-syntax は throw new Error の AST しか拾えないため、
# 関数呼び出し系はこのスクリプトで補完する。
#
# 詳細: .claude/rules/web/messages.md
set -euo pipefail

cd "$(dirname "$0")/../web"

# Rust regex (ripgrep -P) で Unicode プロパティを使って ひらがな・カタカナ・漢字 を検出する。
# ダブルクォート文字列とバッククォート文字列の両方をカバー（フロントエンドはダブルクォート慣習）。
#
# (1) set*Error* / set*Success* / set*Info* / set*Message* と toast.error / alert に
#     リテラルを直接渡すケース。
SETTER_PATTERN='(set\w*(Error|Success|Info|Message)\w*|toast\.error|alert)\(\s*["`][^"`]*[\p{Hiragana}\p{Katakana}\p{Han}]'
# (2) toAppError(firstArg, "リテラル") のように fallback を第2引数へ直書きするケース。
TOAPPERROR_PATTERN='toAppError\([^,)]+,\s*["`][^"`]*[\p{Hiragana}\p{Katakana}\p{Han}]'

# 検出。一致が無くても exit 1 にならないよう `|| true`。
matches=$(
  rg -nP \
    -g 'src/**/*.ts' \
    -g 'src/**/*.tsx' \
    -g '!src/**/*.test.*' \
    -g '!src/test/**' \
    -g '!src/constants/messages.ts' \
    -e "$SETTER_PATTERN" \
    -e "$TOAPPERROR_PATTERN" \
    src \
    || true
)

if [ -n "$matches" ]; then
  echo "$matches"
  echo ""
  echo "ERROR: setError / setSuccess / toAppError 等に日本語リテラルを直接渡しています。"
  echo "web/src/constants/messages.ts の定数を参照してください。"
  echo "詳細: .claude/rules/web/messages.md"
  exit 1
fi
