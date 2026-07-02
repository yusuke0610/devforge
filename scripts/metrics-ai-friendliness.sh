#!/usr/bin/env bash
# AI フレンドリーさの推移指標を GitHub 履歴から集計し、ダッシュボード md を再生成する。
#
# 背景:
#   本リポジトリは「AI エージェントが不変条件を壊さず開発できるアーキテクチャ」を
#   主目的の一つとしている（scoped rules / SSoT lint / codegen drift 検知）。
#   その効果を「そう感じる」で終わらせず、PR 履歴から観測可能な代理指標の月次推移で追う。
#
# 指標（いずれも月次・マージ済み PR ベース。bot PR は母数から除外）:
#   (1) 手戻りコミット率: PR 内コミットのうち REWORK_PATTERN（review(...) 等の
#       レビュー/CI 対応 prefix）に一致する割合。squash merge 運用のため main の
#       git log からは復元できず、GitHub API で PR ごとの生コミットを取得する。
#   (2) CodeRabbit 指摘数 / PR: PR の inline review comments のうち CodeRabbit による件数。
#   (3) ルール追記コミット数: .claude/rules / CLAUDE.md（旧 AGENTS.md）に触れたコミット数。
#       「不変条件が壊れて再発防止ルールを足した」の代理指標（構成整理も含む proxy）。
#
# データの正本とキャッシュ:
#   - PR ごとの計測値は docs/metrics/ai-friendliness-data.json に保持する。
#     マージ済み PR は不変なので、既取得の PR は再取得しない（差分のみ API を叩く）。
#   - docs/metrics/ai-friendliness.md は本スクリプトが全体を再生成する生成物。手で編集しない。
#   - 判定パターン変更後など全再取得したい場合は --full を付ける（data JSON を作り直す）。
#
# 依存: gh（認証済み）/ jq / git。ホスト側で実行する（nix devshell 不要）。
set -euo pipefail

cd "$(dirname "$0")/.."

DATA="docs/metrics/ai-friendliness-data.json"
OUT="docs/metrics/ai-friendliness.md"

# 手戻りコミット判定（コミットメッセージ先頭行に適用）。
# コミット規約: review(scope): は CodeRabbit / レビュー指摘対応、fix(ci) は CI こけ対応。
REWORK_PATTERN='^review[(:]|^fix\(ci\)|[Cc]ode[Rr]abbit'
# 集計対象外の bot author（依存更新 PR 等は AI 開発の観測対象ではない）
BOT_PATTERN='renovate|dependabot|coderabbit|github-actions'

for cmd in gh jq git; do
  command -v "$cmd" >/dev/null 2>&1 || { echo "ERROR: $cmd が必要です" >&2; exit 1; }
done

if [ "${1:-}" = "--full" ]; then
  rm -f "$DATA"
fi
mkdir -p docs/metrics
[ -f "$DATA" ] || echo "[]" > "$DATA"

REPO=$(gh repo view --json nameWithOwner -q .nameWithOwner)

# ── 1. マージ済み PR 一覧（bot 除外） ────────────────────────────────────
prs=$(gh pr list --state merged --limit 1000 --json number,author,mergedAt \
  | jq --arg bot "$BOT_PATTERN" \
    '[ .[]
       | select((.author.is_bot | not) and (((.author.login // "") | test($bot; "i")) | not))
       | {number, mergedAt} ]')

# ── 2. 未取得 PR の詳細を API から取得して data JSON へ追記 ────────────────
new_numbers=$(jq -n --argjson prs "$prs" --slurpfile known "$DATA" \
  '(($prs | map(.number)) - ($known[0] | map(.number))) | sort | .[]')

total_new=$(printf '%s\n' "$new_numbers" | grep -c . || true)
echo "対象 PR: $(jq -n --argjson p "$prs" '$p | length') 件（新規取得: $total_new 件）"

i=0
for n in $new_numbers; do
  i=$((i + 1))
  merged_at=$(jq -rn --argjson prs "$prs" --argjson n "$n" \
    '$prs[] | select(.number == $n) | .mergedAt')
  # --paginate はページごとに JSON 配列を吐くため jq -s 'add' で結合する
  msgs=$(gh api "repos/$REPO/pulls/$n/commits" --paginate \
    | jq -s '[(add // [])[] | .commit.message | split("\n")[0]]')
  comments=$(gh api "repos/$REPO/pulls/$n/comments" --paginate \
    | jq -s '[(add // [])[] | select(((.user.login // "") | test("coderabbit"; "i")))] | length')
  record=$(jq -n --argjson n "$n" --arg m "$merged_at" --argjson msgs "$msgs" \
    --argjson c "$comments" --arg re "$REWORK_PATTERN" '
    {
      number: $n,
      merged_at: $m,
      commits_total: ([$msgs[] | select(startswith("Merge ") | not)] | length),
      commits_rework: ([$msgs[] | select(test($re))] | length),
      review_comments: $c
    }')
  jq --argjson r "$record" '. + [$r] | sort_by(.number)' "$DATA" > "$DATA.tmp" \
    && mv "$DATA.tmp" "$DATA"
  if [ $((i % 25)) -eq 0 ]; then
    echo "  ... $i / $total_new"
  fi
done

# ── 3. ルール追記コミット（git log から毎回全量を再計算） ──────────────────
rule_months=$(git log --format=%as -- .claude/rules .claude/CLAUDE.md AGENTS.md \
  | cut -c1-7 | sort | uniq -c \
  | awk '{printf "{\"month\":\"%s\",\"count\":%s}\n", $2, $1}' | jq -s '.')

# ── 4. 月次集計 ───────────────────────────────────────────────────────────
summary=$(jq --argjson rules "$rule_months" '
  group_by(.merged_at[:7])
  | map(
      {
        month: .[0].merged_at[:7],
        prs: length,
        commits: (map(.commits_total) | add),
        rework: (map(.commits_rework) | add),
        comments: (map(.review_comments) | add)
      }
      | . + {
          rework_rate: (if .commits > 0 then ((1000 * .rework / .commits | round) / 10) else 0 end),
          comments_per_pr: ((10 * .comments / .prs | round) / 10)
        }
      | . as $row
      | $row + {rule_commits: (($rules | map(select(.month == $row.month) | .count) | first) // 0)}
    )
  | sort_by(.month)' "$DATA")

# ── 5. ダッシュボード md を再生成 ─────────────────────────────────────────
# 観測開始月: レビュー対応コミット規約 / CodeRabbit が観測に現れた最初の月。
# それ以前の月の手戻り率・指摘数は「ゼロ」ではなく「観測不能」（比較対象外）。
observable_from=$(jq -r '[.[] | select(.rework > 0 or .comments > 0)] | first | .month // "N/A"' <<<"$summary")
months_q=$(jq -r '[.[].month | "\"" + . + "\""] | join(", ")' <<<"$summary")
rework_vals=$(jq -r '[.[].rework_rate] | join(", ")' <<<"$summary")
comment_vals=$(jq -r '[.[].comments_per_pr] | join(", ")' <<<"$summary")
pr_vals=$(jq -r '[.[].prs] | join(", ")' <<<"$summary")
rule_vals=$(jq -r '[.[].rule_commits] | join(", ")' <<<"$summary")
table_rows=$(jq -r '.[] | "| \(.month) | \(.prs) | \(.commits) | \(.rework) | \(.rework_rate) | \(.comments) | \(.comments_per_pr) | \(.rule_commits) |"' <<<"$summary")
generated_at=$(date '+%Y-%m-%d')

cat > "$OUT" <<EOF
# AI フレンドリーさダッシュボード

<!-- 本ファイルは scripts/metrics-ai-friendliness.sh が全体を再生成する生成物。手で編集しない。 -->

「AI エージェントが不変条件を壊さず開発できるアーキテクチャ」（scoped rules / SSoT lint /
codegen drift 検知）の効果を、GitHub 履歴から取れる代理指標の**月次推移**で観測する。

- 再生成: \`make metrics-ai-friendliness\`（判定パターン変更後は \`--full\` で全再取得）
- データ正本: [\`ai-friendliness-data.json\`](./ai-friendliness-data.json)（PR 単位の計測値。マージ済み PR は不変のため差分のみ取得）
- 最終生成日: $generated_at

## 指標の定義

| 指標 | 定義 | 望ましい向き |
|---|---|---|
| 手戻りコミット率 | PR 内コミット（Merge 除く）のうち \`review(...)\` / \`fix(ci)\` 等のレビュー・CI 対応コミットの割合 | 低いほど「一発で不変条件を守れている」 |
| CodeRabbit 指摘数 / PR | PR の inline review comments のうち CodeRabbit による件数の PR 平均 | 低いほど機械レビュー前に品質が担保されている |
| ルール追記コミット数 | \`.claude/rules\` / \`CLAUDE.md\`（旧 \`AGENTS.md\`）に触れたコミット数 | 事故由来の追記が減り漸近するのが理想（proxy） |

## 読み方の注意（交絡）

- **比較が有効なのは $observable_from 以降のみ**。レビュー対応コミット規約（\`review(...)\`）と CodeRabbit の導入以前の月は、手戻り率・指摘数が「ゼロ」に見えるが実際は**観測不能**（規約が無く squash 前の手戻りを識別できない）
- 期間中に **LLM モデル自体が世代交代**しており、改善がアーキテクチャ起因かモデル起因かは分離できない。**因果ではなく記述統計**として読む
- 作者のプロンプト習熟・タスク難度の変動も混ざる
- 直近月は PR 数が少なく率が暴れる（小標本）。月次 PR 数と併せて読む
- ルール追記コミットは構成整理・初期整備も含む proxy であり、すべてが「事故」ではない
- Renovate 等の bot PR は母数から除外している

## 手戻りコミット率（%）

\`\`\`mermaid
xychart-beta
    title "手戻りコミット率（% / 月）"
    x-axis [$months_q]
    y-axis "%"
    line [$rework_vals]
\`\`\`

## CodeRabbit 指摘数 / PR

\`\`\`mermaid
xychart-beta
    title "CodeRabbit 指摘数 / PR（月平均）"
    x-axis [$months_q]
    y-axis "件 / PR"
    line [$comment_vals]
\`\`\`

## 月次 PR 数（母数の文脈）

\`\`\`mermaid
xychart-beta
    title "マージ済み PR 数（bot 除く / 月）"
    x-axis [$months_q]
    y-axis "件"
    bar [$pr_vals]
\`\`\`

## ルール追記コミット数

\`\`\`mermaid
xychart-beta
    title "rules / CLAUDE.md 追記コミット数（月）"
    x-axis [$months_q]
    y-axis "件"
    bar [$rule_vals]
\`\`\`

## 月次データ

| 月 | PR 数 | コミット | 手戻り | 手戻り率 % | 指摘 | 指摘 / PR | ルール追記 |
|---|---|---|---|---|---|---|---|
$table_rows
EOF

echo ""
echo "生成完了:"
echo "  - $OUT"
echo "  - $DATA"
jq -r '.[-3:][] | "  \(.month): 手戻り率 \(.rework_rate)% / 指摘 \(.comments_per_pr) 件/PR（PR \(.prs) 件）"' <<<"$summary"
