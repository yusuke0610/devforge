#!/usr/bin/env bash
# 領域跨ぎの SSoT drift を検知する。
#
# 背景:
#   環境変数名やエラーコードは「正本（backend）を変えたのに downstream（compose / FE）の
#   追従を忘れる」事故が起きやすい。これらは言語境界（Python / YAML / TS）上リテラルの
#   複製を消せないため、複製を消す代わりに「複製が正本と一致しているか」を機械検証する。
#
# 検証内容:
#   (1) env 名（正方向）: backend/app/core/env_keys.py の定数値（= 実 env 名）が
#       docker-compose.yml の environment ブロックにすべて存在するか
#       （ALLOWLIST で起動時内部フラグ等を除外）。rename / 削除時の同期忘れを CI で止める。
#   (2) env 名（逆方向）: docker-compose.yml / infra/modules/cloud_run/main.tf に
#       書かれた env 名がすべて env_keys.py に存在するか。rename / 削除時に downstream へ
#       旧名が残留する drift と typo を検知する。本番注入経路（cloud_run）は環境変数ごとに
#       注入要否が異なる（ローカル専用の OLLAMA_* 等がある）ため、正方向（すべて注入
#       されているか）は検証できず逆方向のみ検証する。
#   (3) リテラル参照禁止: backend/app が os.getenv("XXX") / os.environ["XXX"] /
#       os.environ.get("XXX") の文字列リテラルで env を参照していないか
#       （env_keys 定数経由を機械強制する。従来は規律のみだった）。
#   (4) エラーコード: backend/app/core/errors.py の ErrorCode 値集合と
#       web/src/constants/errorCodes.ts の ERROR_CODES が完全一致するか。
#       FE 側の型検査（Record<ErrorCodeKey,...>）は FE 内で完結するため、
#       BE が新コードを追加して FE 未反映の drift は型エラーにならない。それを補う。
#
# 対象外（意図的）:
#   - .github/workflows/ci.yml: 実 API を CI から呼ばないため（env_keys.py の
#     OPENAI_API_KEY コメント参照）
#   - docs/api.md の環境変数表: 手動同期のまま（doc drift は実害が小さい）
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
CLOUD_RUN_TF="infra/modules/cloud_run/main.tf"
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
# 抽出は grep -E / sed -E / awk のみで行う（PCRE / ripgrep に依存しない）。
# ripgrep は flake.nix の devshell にも GitHub ランナーにも入っていないため。
#
# env_keys.py からは定数の「文字列値」（= 実 env 名）を取る。symbol 名ではなく値が
# downstream の env 名になるため、`NAME = "VALUE"` の VALUE 側を比較対象にする
# （symbol だけ rename しても誤検知せず、値だけ変えた drift も取りこぼさない）。
env_names=$(grep -E '^[A-Z_]+[[:space:]]*=[[:space:]]*"[^"]+"' "$ENV_KEYS" \
  | sed -E 's/^[A-Z_]+[[:space:]]*=[[:space:]]*"([^"]+)".*/\1/' | sort -u)

# docker-compose.yml からは api サービスの environment ブロック内の env 名だけを取る。
# 全 YAML の大文字キーを拾うと、他サービス（libsql の SQLD_NODE 等）の名前で
# 「api に無い env 名」を誤って pass させてしまう（検知したい drift を隠す）。
compose_names=$(awk '
  /^  [a-z_]+:[[:space:]]*$/ { in_api = ($0 ~ /^  api:[[:space:]]*$/) }
  in_api && /^    environment:[[:space:]]*$/ { in_env = 1; next }
  in_api && in_env && /^    [^[:space:]]/ { in_env = 0 }
  in_api && in_env && /^      [A-Z_]+:/ {
    name = $0; sub(/^[[:space:]]+/, "", name); sub(/:.*/, "", name); print name
  }
' "$COMPOSE" | sort -u)

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

# ── (2) 逆方向: downstream の env 名 ⊆ env_keys.py ─────────────────────────
# rename / 削除時に compose / cloud_run へ旧名が残留する drift と typo を検知する。
#
# cloud_run の env 名は 2 形式から取る:
#   - 静的 env block:        name  = "XXX"
#   - secret env の locals:  XXX = "secret-name"（dynamic env の name は locals キーが正本）
cloud_run_names=$({
  grep -E 'name[[:space:]]+=[[:space:]]+"[A-Z_]+"' "$CLOUD_RUN_TF" \
    | sed -E 's/.*"([A-Z_]+)".*/\1/'
  grep -E '^[[:space:]]*[A-Z_]+[[:space:]]*=[[:space:]]*"' "$CLOUD_RUN_TF" \
    | sed -E 's/^[[:space:]]*([A-Z_]+).*/\1/'
} | sort -u)

unknown_in_compose=$(comm -23 <(printf '%s\n' "$compose_names") <(printf '%s\n' "$env_names"))
unknown_in_cloud_run=$(comm -23 <(printf '%s\n' "$cloud_run_names") <(printf '%s\n' "$env_names"))

if [ -n "$unknown_in_compose" ] || [ -n "$unknown_in_cloud_run" ]; then
  echo "ERROR: $ENV_KEYS に存在しない env 名が downstream に残っています:" >&2
  if [ -n "$unknown_in_compose" ]; then
    echo "  $COMPOSE:" >&2
    printf '    - %s\n' $unknown_in_compose >&2
  fi
  if [ -n "$unknown_in_cloud_run" ]; then
    echo "  $CLOUD_RUN_TF:" >&2
    printf '    - %s\n' $unknown_in_cloud_run >&2
  fi
  echo "" >&2
  echo "rename / 削除した env 名の旧名残留か typo です。downstream 側を追従してください。" >&2
  echo "" >&2
  fail=1
fi

# ── (3) backend のリテラル env 参照禁止（env_keys 定数経由を強制） ──────────
# env_keys.py 自身は docstring にリテラル例を含むため除外する。
literal_refs=$(grep -rnE 'os\.(getenv|environ\.get)\([[:space:]]*"|os\.environ\[[[:space:]]*"' \
  backend/app --include='*.py' | grep -v 'app/core/env_keys\.py' || true)

if [ -n "$literal_refs" ]; then
  echo "ERROR: backend/app に文字列リテラルでの env 参照があります:" >&2
  printf '%s\n' "$literal_refs" | sed 's/^/  /' >&2
  echo "" >&2
  echo "from app.core import env_keys した上で os.getenv(env_keys.XXX) を使ってください。" >&2
  echo "" >&2
  fail=1
fi

# ── (4) errors.py ErrorCode == errorCodes.ts ERROR_CODES ──────────────────
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

echo "lint-env-keys: OK（env 名 compose/cloud_run・リテラル参照・ErrorCode の SSoT drift なし）"
