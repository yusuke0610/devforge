#!/usr/bin/env bash
# ADR 索引（docs/adr/README.md）と ADR ファイルの drift を検知する。
#
# 背景:
#   ADR の一覧・関係の正本は docs/adr/README.md の索引。以前は CONTRIBUTING.md に
#   一覧表を複製しており、ADR 追加・ステータス変更の追従漏れで陳腐化した
#   （0012〜0015・0017 の未掲載、0006 のステータス古い等）。複製は索引へ一本化した上で、
#   「索引 ↔ 実ファイル」の整合だけを機械検証する（lint-env-keys.sh と同じ思想）。
#
# 検証内容:
#   (1) 見出し番号: docs/adr/NNNN-*.md のファイル名 NNNN と 1 行目 `# ADR-NNNN:` が
#       一致するか（0011 が `# ADR-0009:` になっていた誤記の再発防止）。
#   (2) 正方向: すべての ADR ファイル（0000-template.md 除く）が索引の
#       「全 ADR 一覧」表に載っているか（新規 ADR の索引更新忘れを止める）。
#   (3) 逆方向: 「全 ADR 一覧」表の各行のリンク先ファイルが実在するか
#       （rename / 削除時の索引残留と typo を検知する）。
#   (4) ステータス突合: 各 ADR の「## ステータス」直後の値と索引のステータス列が
#       一致するか。加えて「現在有効な決定」表の集合が Accepted の集合と一致するか
#       （supersede / deprecate 時の索引更新忘れを止める）。
#
# 対象外（意図的）:
#   - テーマ・「置き換え・関連」列・決定系統図（Mermaid）: 人間の編集価値が本体で、
#     機械検証には Markdown / Mermaid の構文解析が必要になり過剰なため。
#
# 正本:
#   - 一覧・関係: docs/adr/README.md
#   - ステータス: 各 ADR ファイルの「## ステータス」節
set -euo pipefail

cd "$(dirname "$0")/.."

ADR_DIR="docs/adr"
INDEX="$ADR_DIR/README.md"

fail=0

if [ ! -f "$INDEX" ]; then
  echo "ERROR: $INDEX が存在しません。" >&2
  exit 1
fi

# ── (1) ファイル名 NNNN と見出し `# ADR-NNNN:` の一致 ──────────────────────
for f in "$ADR_DIR"/[0-9][0-9][0-9][0-9]-*.md; do
  num=$(basename "$f" | cut -c1-4)
  [ "$num" = "0000" ] && continue
  heading_num=$(head -1 "$f" | sed -nE 's/^# ADR-([0-9]{4}):.*/\1/p')
  if [ -z "$heading_num" ]; then
    echo "ERROR: $f の 1 行目が \`# ADR-NNNN: タイトル\` 形式ではありません。" >&2
    fail=1
  elif [ "$heading_num" != "$num" ]; then
    echo "ERROR: $f のファイル名（$num）と見出し番号（ADR-$heading_num）が一致しません。" >&2
    fail=1
  fi
done

# ── 索引の 2 つの表から ADR 番号を抽出 ──────────────────────────────────────
# セクション見出しで表を区別する（両表とも行は `| [ADR-NNNN](./file.md) | ...`）。
index_all_rows=$(awk '/^## 全 ADR 一覧/{flag=1; next} /^## /{flag=0} flag' "$INDEX" \
  | grep -E '^\| \[ADR-[0-9]{4}\]' || true)
index_accepted_nums=$(awk '/^## 現在有効な決定/{flag=1; next} /^## /{flag=0} flag' "$INDEX" \
  | grep -E '^\| \[ADR-[0-9]{4}\]' | sed -E 's/^\| \[ADR-([0-9]{4})\].*/\1/' | sort -u || true)

index_all_nums=$(printf '%s\n' "$index_all_rows" | sed -E 's/^\| \[ADR-([0-9]{4})\].*/\1/' | sort -u)
file_nums=$(ls "$ADR_DIR" | sed -nE 's/^([0-9]{4})-.*\.md$/\1/p' | grep -v '^0000$' | sort -u)

# ── (2) 正方向: ADR ファイル ⊆ 索引「全 ADR 一覧」 ─────────────────────────
missing_in_index=$(comm -23 <(printf '%s\n' "$file_nums") <(printf '%s\n' "$index_all_nums"))
if [ -n "$missing_in_index" ]; then
  echo "ERROR: 次の ADR が $INDEX の「全 ADR 一覧」に載っていません:" >&2
  printf '  - ADR-%s\n' $missing_in_index >&2
  echo "ADR を新規作成したら索引に行を追加してください。" >&2
  fail=1
fi

# ── (3) 逆方向: 索引の行 ⊆ ADR ファイル（リンク先の実在も確認） ─────────────
stale_in_index=$(comm -13 <(printf '%s\n' "$file_nums") <(printf '%s\n' "$index_all_nums"))
if [ -n "$stale_in_index" ]; then
  echo "ERROR: $INDEX の「全 ADR 一覧」に実在しない ADR の行があります:" >&2
  printf '  - ADR-%s\n' $stale_in_index >&2
  echo "ADR を rename / 削除したら索引の行も追従してください。" >&2
  fail=1
fi

while IFS= read -r link; do
  [ -z "$link" ] && continue
  if [ ! -f "$ADR_DIR/$link" ]; then
    echo "ERROR: $INDEX のリンク先 $ADR_DIR/$link が存在しません。" >&2
    fail=1
  fi
done <<EOF
$(printf '%s\n' "$index_all_rows" | sed -nE 's/^\| \[ADR-[0-9]{4}\]\(\.\/([^)]+)\).*/\1/p')
EOF

# ── (4) ステータス突合 ──────────────────────────────────────────────────────
# ADR ファイル側: 「## ステータス」直後の最初の非空・非 blockquote 行を実ステータスとする。
# 索引側: 「全 ADR 一覧」表の 3 列目。
accepted_file_nums=""
for num in $file_nums; do
  f=$(ls "$ADR_DIR/$num"-*.md)
  file_status=$(awk '/^## ステータス/{flag=1; next} /^## /{flag=0} flag && NF && !/^>/{print; exit}' "$f")
  # 行が索引に無い場合 grep が exit 1 になる（(2) が既に検知済み）ため || true で握る
  index_status=$(printf '%s\n' "$index_all_rows" \
    | grep -E "^\| \[ADR-$num\]" | awk -F'|' '{gsub(/^ +| +$/, "", $4); print $4}' || true)
  if [ -n "$index_status" ] && [ "$file_status" != "$index_status" ]; then
    echo "ERROR: ADR-$num のステータスが索引と一致しません（ファイル: '$file_status' / 索引: '$index_status'）。" >&2
    fail=1
  fi
  if [ "$file_status" = "Accepted" ]; then
    accepted_file_nums="$accepted_file_nums$num"$'\n'
  fi
done
accepted_file_nums=$(printf '%s' "$accepted_file_nums" | sort -u)

not_in_accepted_table=$(comm -23 <(printf '%s\n' "$accepted_file_nums") <(printf '%s\n' "$index_accepted_nums"))
stale_in_accepted_table=$(comm -13 <(printf '%s\n' "$accepted_file_nums") <(printf '%s\n' "$index_accepted_nums"))
if [ -n "$not_in_accepted_table" ]; then
  echo "ERROR: 次の Accepted な ADR が $INDEX の「現在有効な決定」に載っていません:" >&2
  printf '  - ADR-%s\n' $not_in_accepted_table >&2
  fail=1
fi
if [ -n "$stale_in_accepted_table" ]; then
  echo "ERROR: $INDEX の「現在有効な決定」に Accepted でない ADR が残っています:" >&2
  printf '  - ADR-%s\n' $stale_in_accepted_table >&2
  echo "supersede / deprecate したら「現在有効な決定」から行を外してください。" >&2
  fail=1
fi

if [ "$fail" -ne 0 ]; then
  exit 1
fi

echo "lint-adr-index: OK（ADR ファイル ↔ 索引の存在・ステータス・見出し番号の drift なし）"
