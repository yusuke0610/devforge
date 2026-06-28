#!/usr/bin/env bash
# 領域跨ぎの SSoT drift を検知する。
#
# 背景:
#   環境変数名やエラーコードは「正本（backend）を変えたのに downstream（compose / FE）の
#   追従を忘れる」事故が起きやすい。これらは言語境界（Python / YAML / TS）上リテラルの
#   複製を消せないため、複製を消す代わりに「複製が正本と一致しているか」を機械検証する。
#
# 検証内容:
#   (1) env 名: backend/app/core/env_keys.py の定数値（= 実 env 名）が
#       docker-compose.yml の environment ブロックにすべて存在するか
#       （ALLOWLIST で起動時内部フラグ等を除外）。rename / 削除時の同期忘れを CI で止める。
#   (2) エラーコード: backend/app/core/errors.py の ErrorCode 値集合と
#       web/src/constants/errorCodes.ts の ERROR_CODES が完全一致するか。
#       FE 側の型検査（Record<ErrorCodeKey,...>）は FE 内で完結するため、
#       BE が新コードを追加して FE 未反映の drift は型エラーにならない。それを補う。
#
# 正本:
#   - env 名:        backend/app/core/env_keys.py
#   - エラーコード:  backend/app/core/errors.py の ErrorCode
#
# 詳細: .claude/rules/common/duplication.md / backend/app/core/env_keys.py の docstring
set -euo pipefail

cd "$(dirname "$0")/.."

ENV_KEYS="backend/app/core/env_keys.py"
COMPOSE="docker-compose.yml"
ERRORS_PY="backend/app/core/errors.py"
ERROR_CODES_TS="web/src/constants/errorCodes.ts"

# docker-compose に注入しない env_keys 定数（設定ではなくランタイム内部フラグ）。
# APP_BOOTSTRAPPED: backend/scripts/entrypoint.sh が export する起動ガードで、
#                   外部から注入する設定 env ではないため compose には現れない。
COMPOSE_ALLOWLIST=$(printf '%s\n' \
  "APP_BOOTSTRAPPED" \
  | sort -u)

fail=0

# ── (1) env_keys.py ⊆ docker-compose.yml ──────────────────────────────────
# 抽出は grep -E + sed -E のみで行う（PCRE / ripgrep に依存しない）。
# ripgrep は flake.nix の devshell にも GitHub ランナーにも入っていないため。
env_names=$(grep -E '^[A-Z_]+[[:space:]]*=[[:space:]]*"' "$ENV_KEYS" \
  | sed -E 's/^([A-Z_]+).*/\1/' | sort -u)
compose_names=$(grep -E '^[[:space:]]+[A-Z_]+:' "$COMPOSE" \
  | sed -E 's/^[[:space:]]+([A-Z_]+):.*/\1/' | sort -u)

# 正本から allowlist を除いた「compose に存在すべき env 名」
expected_in_compose=$(comm -23 <(printf '%s\n' "$env_names") <(printf '%s\n' "$COMPOSE_ALLOWLIST"))
missing_in_compose=$(comm -23 <(printf '%s\n' "$expected_in_compose") <(printf '%s\n' "$compose_names"))

if [ -n "$missing_in_compose" ]; then
  echo "ERROR: 次の env 名が $ENV_KEYS にあるが $COMPOSE の environment に未注入です:" >&2
  printf '  - %s\n' $missing_in_compose >&2
  echo "" >&2
  echo "$ENV_KEYS の定数を rename / 追加したら $COMPOSE も追従してください。" >&2
  echo "ローカル開発で意図的に不要な場合は scripts/lint-env-keys.sh の COMPOSE_ALLOWLIST に追記。" >&2
  echo "" >&2
  fail=1
fi

# ── (2) errors.py ErrorCode == errorCodes.ts ERROR_CODES ──────────────────
be_codes=$(grep -E '^[[:space:]]+[A-Z_]+[[:space:]]*=[[:space:]]*"[A-Z_]+"' "$ERRORS_PY" \
  | sed -E 's/.*=[[:space:]]*"([A-Z_]+)".*/\1/' | sort -u)
fe_codes=$(grep -E '^[[:space:]]+"[A-Z_]+",' "$ERROR_CODES_TS" \
  | sed -E 's/.*"([A-Z_]+)".*/\1/' | sort -u)

be_only=$(comm -23 <(printf '%s\n' "$be_codes") <(printf '%s\n' "$fe_codes"))
fe_only=$(comm -13 <(printf '%s\n' "$be_codes") <(printf '%s\n' "$fe_codes"))

if [ -n "$be_only" ] || [ -n "$fe_only" ]; then
  echo "ERROR: ErrorCode の集合が BE と FE で一致しません。" >&2
  if [ -n "$be_only" ]; then
    echo "  $ERRORS_PY にあるが $ERROR_CODES_TS に無い:" >&2
    printf '    - %s\n' $be_only >&2
  fi
  if [ -n "$fe_only" ]; then
    echo "  $ERROR_CODES_TS にあるが $ERRORS_PY に無い:" >&2
    printf '    - %s\n' $fe_only >&2
  fi
  echo "" >&2
  echo "errors.py の ErrorCode を正本に、errorCodes.ts と errorMessages.ts を追従してください。" >&2
  echo "" >&2
  fail=1
fi

if [ "$fail" -ne 0 ]; then
  exit 1
fi

echo "lint-env-keys: OK（env 名 / ErrorCode の SSoT drift なし）"
