#!/usr/bin/env bash
# TDD 対象（決定論的ロジック層）の実装変更にテスト差分が随伴しているかを検知する（ADR-0019）。
#
# 背景:
#   決定論的ビジネスロジックの変更は red→green→refactor（.claude/rules/common/tdd.md）で
#   行う方針だが、「テストを先に書いたか」自体は diff から検証できない。そこで検証可能な
#   必要条件（対象の実装変更にテスト差分が随伴していること）だけを機械ゲートにする。
#   少なくとも「テストなしの実装変更」は main に入らない（lint-env-keys.sh と同じ思想）。
#
# 検証内容:
#   (1) base（PR の base ブランチ / ローカルは origin/main）との merge-base から
#       作業ツリーまでの変更ファイル（未コミット・未追跡を含む）を列挙する。
#   (2) TDD 対象 glob に該当する実装ファイルの変更があるか判定する。
#       対象スコープの正本はミューテーションテスト設定（ADR-0017 と共有・ここに複製しない）:
#         - backend: backend/pyproject.toml の [tool.mutmut] only_mutate
#         - web:     web/stryker.conf.json の mutate（"!" は除外パターン）
#   (3) 対象の変更があるのに、同領域のテストファイル
#       （backend: backend/tests/** / web: web/src/**/*.test.ts(x), web/src/test/**）に
#       差分が無ければ fail する。
#
# 適用除外（escape hatch）:
#   振る舞いを変えない変更（リネーム・コメント修正・機械的リファクタ等）は、ブランチ内の
#   いずれかのコミットメッセージに `Tdd-Exempt: <理由>` トレーラーを付けると skip される。
#   理由の妥当性は PR レビューで担保する。コミット前のローカル実行では環境変数
#   `TDD_EXEMPT=1`（例: `TDD_EXEMPT=1 make ci`）で代用できる（CI はトレーラーのみ）。
#
# 限界（意図的に許容 / ADR-0019）:
#   - 「対象ファイルの変更 + 無関係なテストの差分」でも pass する（ファイル単位の
#     対応付けはコストが高く導入しない）。
#   - 実装後にテストを足しても pass する（テストファーストの証明ではない）。
set -euo pipefail

cd "$(dirname "$0")/.."

# ── base の決定（PR では GitHub Actions が GITHUB_BASE_REF を設定する） ────────
if [ -n "${GITHUB_BASE_REF:-}" ]; then
  BASE_REF="origin/${GITHUB_BASE_REF}"
else
  BASE_REF="${TDD_BASE_REF:-origin/main}"
fi

if ! git rev-parse --verify --quiet "$BASE_REF" >/dev/null; then
  echo "ERROR: base ref '$BASE_REF' を解決できません。'git fetch origin main' を実行してください。" >&2
  echo "（CI の場合は checkout の fetch-depth: 0 を確認すること）" >&2
  exit 1
fi

merge_base=$(git merge-base "$BASE_REF" HEAD)

# ── 適用除外の判定 ───────────────────────────────────────────────────────────
if git log --format=%B "$merge_base..HEAD" | grep -qiE '^tdd-exempt:[[:space:]]*[^[:space:]]'; then
  echo "lint-tdd: SKIP（コミットメッセージに Tdd-Exempt トレーラーあり。理由はレビューで確認）"
  exit 0
fi
if [ "${TDD_EXEMPT:-}" = "1" ]; then
  echo "lint-tdd: SKIP（TDD_EXEMPT=1。コミット時に Tdd-Exempt: <理由> トレーラーを付けること）"
  exit 0
fi

# ── 変更ファイルの列挙（コミット済み + 未コミット + 未追跡） ──────────────────
changed_files=$( { git diff --name-only "$merge_base"; git ls-files --others --exclude-standard; } | sort -u)

if [ -z "$changed_files" ]; then
  echo "lint-tdd: OK（変更ファイルなし）"
  exit 0
fi

# ── TDD 対象 glob を mutation 設定から読み出す ────────────────────────────────
# bash/git/awk/sed のみに依存する（python/jq を要求しない）。
mutmut_globs=$(awk '/^only_mutate = \[/{flag=1; next} /^\]/{flag=0} flag' backend/pyproject.toml \
  | sed -nE 's/^[[:space:]]*"([^"]+)".*/\1/p')
stryker_globs=$(awk '/"mutate": \[/{flag=1; next} /\]/{flag=0} flag' web/stryker.conf.json \
  | sed -nE 's/^[[:space:]]*"([^"]+)",?.*/\1/p')

if [ -z "$mutmut_globs" ] || [ -z "$stryker_globs" ]; then
  echo "ERROR: mutation 設定から TDD 対象 glob を読み出せませんでした。" >&2
  echo "backend/pyproject.toml の [tool.mutmut] only_mutate / web/stryker.conf.json の mutate の形式を確認してください。" >&2
  exit 1
fi

stryker_includes=$(printf '%s\n' "$stryker_globs" | grep -v '^!' || true)
stryker_excludes=$(printf '%s\n' "$stryker_globs" | sed -n 's/^!//p')

# パターン集合（改行区切り）に対するファイルのマッチ判定。
# bash の case は `*` が `/` も跨いでマッチするため、`**/` は除去して等価に扱う
# （`src/utils/**/*.ts` はゼロ階層も許すため `src/utils/*.ts` に正規化する）。
matches_any() {
  local file="$1" patterns="$2" pat
  while IFS= read -r pat; do
    [ -z "$pat" ] && continue
    pat="${pat//\*\*\//}"
    # shellcheck disable=SC2254
    case "$file" in
      $pat) return 0 ;;
    esac
  done <<EOF
$patterns
EOF
  return 1
}

# ── 変更ファイルを分類する ────────────────────────────────────────────────────
backend_targets=""
web_targets=""
backend_test_changed=0
web_test_changed=0

while IFS= read -r f; do
  [ -z "$f" ] && continue
  case "$f" in
    backend/tests/*)
      backend_test_changed=1
      continue
      ;;
    web/src/test/* | web/src/*.test.ts | web/src/*.test.tsx)
      web_test_changed=1
      continue
      ;;
  esac
  case "$f" in
    backend/*)
      if matches_any "${f#backend/}" "$mutmut_globs"; then
        backend_targets="$backend_targets  - $f"$'\n'
      fi
      ;;
    web/*)
      rel="${f#web/}"
      if matches_any "$rel" "$stryker_includes" && ! matches_any "$rel" "$stryker_excludes"; then
        web_targets="$web_targets  - $f"$'\n'
      fi
      ;;
  esac
done <<EOF
$changed_files
EOF

# ── 判定 ─────────────────────────────────────────────────────────────────────
fail=0

if [ -n "$backend_targets" ] && [ "$backend_test_changed" -eq 0 ]; then
  echo "ERROR: TDD 対象（backend の決定論的ロジック層）に実装変更がありますが、backend/tests/ に差分がありません:" >&2
  printf '%s' "$backend_targets" >&2
  fail=1
fi

if [ -n "$web_targets" ] && [ "$web_test_changed" -eq 0 ]; then
  echo "ERROR: TDD 対象（web の決定論的ロジック層）に実装変更がありますが、テスト（*.test.ts(x) / src/test/）に差分がありません:" >&2
  printf '%s' "$web_targets" >&2
  fail=1
fi

if [ "$fail" -ne 0 ]; then
  echo "" >&2
  echo "TDD 対象の変更は red→green→refactor でテストを先に書いてください（.claude/rules/common/tdd.md / ADR-0019）。" >&2
  echo "振る舞いを変えない変更の場合はコミットメッセージに 'Tdd-Exempt: <理由>' トレーラーを付けてください。" >&2
  exit 1
fi

echo "lint-tdd: OK（TDD 対象の実装変更にテスト差分が随伴 / または対象変更なし）"
