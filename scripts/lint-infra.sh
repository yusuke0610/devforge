#!/usr/bin/env bash
# infra（OpenTofu）の記述規約と層間 drift を検知する。
#
# 背景:
#   infra 層には従来 fmt（tofu fmt -check）と validate（tofu validate）しか無かった。
#   fmt は整形しか見ず、validate は provider の DL（ネットワーク）が必要なうえ
#   「構文と参照が通るか」しか見ないため、以下が素通りしていた:
#     - description が英語のまま（CLAUDE.md のコメント規約違反）／そもそも無い
#     - 同じ variable を environments/shared と devforge_stack で二重宣言していて
#       description の文言・宣言順が食い違う（実例: 英語/日本語で分裂していた）
#     - トークン類の variable に sensitive = true が付いていない
#   これらを機械検証して、レビューの目視に頼らずに済ませる。
#
# 検証内容:
#   (1) description 必須: すべての variable / output に description があるか。
#   (2) description 日本語: 全角句読点・括弧を除いたうえで日本語文字が残るか
#       （ASCII のみ = 英語とみなす）。末尾の 。 だけを足した英文を素通りさせない。
#       固有名詞だけで構成される正当なケースは DESC_ASCII_ALLOWLIST で除外する。
#   (3) sensitive: 名前が秘匿値パターン（token / secret / password / api_key /
#       private_key）に一致する variable に sensitive = true が付いているか
#       （tofu の plan / output に平文で出る事故の防止。.claude/rules/security.md）。
#   (4) 2 層同期: environments/shared/variables.tf と modules/devforge_stack/variables.tf は
#       同じ variable を二重宣言する（HCL の module 境界上、避けられない構造的重複）。
#       共通 variable の description / type / default / sensitive と、validation の
#       中身（condition / error_message）の一致、および宣言順の相対順序の一致を
#       検証する。片側専用の variable は LAYER_ONLY_* で除外。
#       validation は「ブロックの有無」だけでなく中身まで見る（両層にブロックがあるが
#       条件が違う、を見逃さないため）。
#   (5) tfvars: environments/<env>/terraform.tfvars のキーがすべて宣言済み variable か
#       （rename 時に tfvars 側へ旧名が残留する drift と typo を検知）。
#   (6) module 呼び出し: module ブロックに渡している引数が呼び出し先の variables.tf に
#       存在するか（正方向）、および default を持たない variable の渡し漏れが無いか（逆方向）。
#       validate と重複する検証だが、validate は provider DL が要るためローカルで回らない
#       ことがある。ネットワーク不要で同じ事故を先に止める。
#   (7) symlink 整合（双方向）: 正方向は environments/shared/*.tf が dev / stg / prod の
#       3 環境すべてから ../shared/<同名>.tf の symlink で参照されているか、実ファイルに
#       戻されていないか、各 symlink が .jscpd.json の ignore に登録されているか
#       （実体 1 ファイルを 3 回スキャンして 100% 重複と誤検知するため）。
#       逆方向は環境側に shared 対応の無い .tf が増えていないか（環境固有として
#       許容するのは ENV_LOCAL_TF のみ）。shared 化の片手落ちと ignore 追記漏れ、
#       環境ごとの野良ファイルを止める。.claude/rules/infra/opentofu.md
#
# 対象外（意図的）:
#   - resource ブロックの引数: provider スキーマが必要で、validate の担当。
#   - 命名規約（stack_name の組み立て等）: module ごとに正当な差異があり誤検知が多い。
#   - terraform.tfvars の値の妥当性: 環境依存のため機械判定できない。
#
# 依存: bash / awk / grep / sed のみ（tofu 不要・ネットワーク不要）。
#
# 正本: .claude/rules/infra/opentofu.md（記述規約・2 層同期）
#       .claude/rules/infra/test.md（infra の検証方針）
set -euo pipefail

cd "$(dirname "$0")/.."

INFRA_DIR="infra"
ENV_VARS="infra/environments/shared/variables.tf"
STACK_VARS="infra/modules/devforge_stack/variables.tf"

# (2) description が ASCII のみでも許容する variable / output 名。
#     固有名詞・型名だけで説明が成立するケースを想定。現状は空。
DESC_ASCII_ALLOWLIST=""

# (3) 秘匿値とみなす variable 名のパターン（拡張正規表現）。
SECRET_NAME_PATTERN='(^|_)(token|secret|password|api_key|private_key)(_|$)'

# (4) 片側専用として 2 層同期の対象外にする variable。
#     env 専用: provider の api_token（module へは渡さず provider ブロックが受ける）
#     stack 専用: env 側は main.tf の local から導出するため variable を持たない
LAYER_ONLY_ENV="cloudflare_api_token turso_api_token"
LAYER_ONLY_STACK="cors_origins callback_base_url"

fail=0

err() {
  echo "ERROR: $*" >&2
  fail=1
}

# ── HCL のトップレベルブロックを TSV へ展開する awk プログラム ──────────────
# 出力: <kind>\t<name>\t<attr>\t<value>
#   attr は属性名そのもの、宣言順は @order、ネストブロックの有無は @block:<名前>、
#   ネストブロック内の属性は @<ブロック名>:<属性名>（例: @validation:condition）。
# 文字列リテラルは「同じ長さ」のマスクに置換してから解析する。長さを保つことで
# マスク列上で見つけた行末コメントの位置を、元の行にそのまま適用できる。
read -r -d '' AWK_BLOCKS <<'AWK' || true
# 文字列リテラルを同じ長さの X に潰す。これで brace の誤カウントと、
# description 内の # / // をコメントと誤認する事故の両方を防ぐ。
function mask(line,   out, i, c, inq, esc) {
  out = ""; inq = 0; esc = 0
  for (i = 1; i <= length(line); i++) {
    c = substr(line, i, 1)
    if (inq) {
      if (esc)          { esc = 0; out = out "X"; continue }
      if (c == "\\")    { esc = 1; out = out "X"; continue }
      if (c == "\"")     { inq = 0; out = out "\""; continue }
      out = out "X"
    } else {
      out = out c
      if (c == "\"") inq = 1
    }
  }
  return out
}
{
  raw = $0
  m = mask(raw)

  # 行末コメント（# / //）を除去する。OpenTofu は行末コメントを許すため、
  # 除去しないと `sensitive = true # 説明` の値が "true # 説明" になり、
  # コメント内の brace が深さ計算を壊す。
  if (match(m, /#|\/\//) > 0) {
    raw = substr(raw, 1, RSTART - 1)
    m   = substr(m, 1, RSTART - 1)
  }
  sub(/[[:space:]]+$/, "", raw)

  before = depth
  depth += gsub(/[{[]/, "&", m) - gsub(/[}\]]/, "&", m)

  if (before == 0 && raw ~ /^(variable|output|module)[[:space:]]+"/) {
    kind = raw; sub(/[[:space:]].*/, "", kind)
    name = raw; sub(/^[a-z]+[[:space:]]+"/, "", name); sub(/".*/, "", name)
    blk = ""
    order++
    print kind "\t" name "\t@order\t" order
    next
  }

  if (before == 1 && kind != "") {
    if (raw ~ /^[[:space:]]+[a-z_][a-z0-9_]*[[:space:]]*\{/) {
      blk = raw
      sub(/^[[:space:]]+/, "", blk)
      sub(/[[:space:]]*\{.*/, "", blk)
      print kind "\t" name "\t@block:" blk "\t1"
      next
    }
    if (raw ~ /^[[:space:]]+[a-z_][a-z0-9_]*[[:space:]]*=/) {
      key = raw
      sub(/^[[:space:]]+/, "", key)
      sub(/[[:space:]]*=.*/, "", key)
      val = raw
      sub(/^[^=]*=[[:space:]]*/, "", val)
      print kind "\t" name "\t" key "\t" val
      next
    }
  }

  # ネストブロック内（validation 等）の属性も拾う。中身を比較しないと
  # 「両層に validation はあるが condition が違う」を見逃す。
  if (before == 2 && kind != "" && blk != "" && raw ~ /^[[:space:]]+[a-z_][a-z0-9_]*[[:space:]]*=/) {
    key = raw
    sub(/^[[:space:]]+/, "", key)
    sub(/[[:space:]]*=.*/, "", key)
    val = raw
    sub(/^[^=]*=[[:space:]]*/, "", val)
    print kind "\t" name "\t@" blk ":" key "\t" val
    next
  }

  if (before >= 2 && depth <= 1) blk = ""
  if (depth == 0) { kind = ""; blk = "" }
}
AWK

blocks() { awk "$AWK_BLOCKS" "$1"; }

# 指定ブロックの属性値を取り出す（無ければ空文字）。
attr_of() { awk -F'\t' -v k="$2" -v n="$3" -v a="$4" '$1==k && $2==n && $3==a {print $4; exit}' "$1"; }

in_list() {
  local needle="$1"
  shift
  local item
  for item in $*; do
    [ "$item" = "$needle" ] && return 0
  done
  return 1
}

# ── 全 .tf を TSV 化してキャッシュ（symlink は実体 1 回だけ見る） ────────────
TMP_DIR=$(mktemp -d)
trap 'rm -rf "$TMP_DIR"' EXIT

tf_files=$(find "$INFRA_DIR" -name '*.tf' -not -type l | sort)

for f in $tf_files; do
  blocks "$f" > "$TMP_DIR/$(echo "$f" | tr '/' '_').tsv"
done

tsv_of() { echo "$TMP_DIR/$(echo "$1" | tr '/' '_').tsv"; }

# ── (1)(2) description の必須・日本語 ──────────────────────────────────────
for f in $tf_files; do
  tsv=$(tsv_of "$f")
  while IFS=$'\t' read -r kind name _ _; do
    [ "$kind" = "variable" ] || [ "$kind" = "output" ] || continue
    desc=$(attr_of "$tsv" "$kind" "$name" description)
    if [ -z "$desc" ]; then
      err "$f: $kind \"$name\" に description がありません（.claude/rules/infra/opentofu.md）。"
      continue
    fi
    in_list "$name" "$DESC_ASCII_ALLOWLIST" && continue
    # 全角句読点・括弧を除いたうえで非 ASCII が 1 つも無ければ英語とみなす。
    # 句読点を先に落とさないと "GCP project ID。" のように末尾の 。だけで
    # 素通りしてしまう（PR #615 で CodeRabbit が検出）。
    # grep -P は macOS の BSD grep に無いため使わず、LC_ALL=C でバイト評価する。
    body=$(printf '%s' "$desc" | sed 's/[。、（）「」・：〜]//g')
    if ! printf '%s' "$body" | LC_ALL=C grep -q '[^ -~]'; then
      err "$f: $kind \"$name\" の description が日本語ではありません: $desc"
    fi
  done < <(awk -F'\t' '$3=="@order"' "$tsv")
done

# ── (3) 秘匿値 variable の sensitive ───────────────────────────────────────
for f in $tf_files; do
  tsv=$(tsv_of "$f")
  while IFS=$'\t' read -r _ name _ _; do
    echo "$name" | grep -qE "$SECRET_NAME_PATTERN" || continue
    sens=$(attr_of "$tsv" variable "$name" sensitive)
    if [ "$sens" != "true" ]; then
      err "$f: variable \"$name\" は秘匿値の命名だが sensitive = true がありません（.claude/rules/security.md）。"
    fi
  done < <(awk -F'\t' '$1=="variable" && $3=="@order"' "$tsv")
done

# ── (4) environments/shared ↔ devforge_stack の 2 層同期 ────────────────────
env_tsv=$(tsv_of "$ENV_VARS")
stack_tsv=$(tsv_of "$STACK_VARS")

env_names=$(awk -F'\t' '$1=="variable" && $3=="@order"' "$env_tsv" | cut -f2)
stack_names=$(awk -F'\t' '$1=="variable" && $3=="@order"' "$stack_tsv" | cut -f2)

for n in $env_names; do
  in_list "$n" "$stack_names" && continue
  in_list "$n" "$LAYER_ONLY_ENV" && continue
  err "$ENV_VARS: variable \"$n\" が $STACK_VARS に存在しません（片側専用なら LAYER_ONLY_ENV に追記）。"
done

for n in $stack_names; do
  in_list "$n" "$env_names" && continue
  in_list "$n" "$LAYER_ONLY_STACK" && continue
  err "$STACK_VARS: variable \"$n\" が $ENV_VARS に存在しません（片側専用なら LAYER_ONLY_STACK に追記）。"
done

for n in $env_names; do
  in_list "$n" "$stack_names" || continue
  for a in description type default sensitive "@block:validation" "@validation:condition" "@validation:error_message"; do
    ev=$(attr_of "$env_tsv" variable "$n" "$a")
    sv=$(attr_of "$stack_tsv" variable "$n" "$a")
    if [ "$ev" != "$sv" ]; then
      err "variable \"$n\" の $a が 2 層で不一致: $ENV_VARS=[${ev:-なし}] / $STACK_VARS=[${sv:-なし}]。"
    fi
  done
done

# 共通 variable の相対順序が両ファイルで一致するか
common_env=$(for n in $env_names; do in_list "$n" "$stack_names" && echo "$n"; done || true)
common_stack=$(for n in $stack_names; do in_list "$n" "$env_names" && echo "$n"; done || true)
if [ "$common_env" != "$common_stack" ]; then
  err "$ENV_VARS と $STACK_VARS で共通 variable の宣言順が一致しません（.claude/rules/infra/opentofu.md）。"
  echo "  shared: $(echo "$common_env" | tr '\n' ' ')" >&2
  echo "  stack : $(echo "$common_stack" | tr '\n' ' ')" >&2
fi

# ── (5) terraform.tfvars のキーがすべて宣言済みか ───────────────────────────
for tfvars in "$INFRA_DIR"/environments/*/terraform.tfvars; do
  [ -f "$tfvars" ] || continue
  while read -r key; do
    [ -n "$key" ] || continue
    in_list "$key" "$env_names" && continue
    err "$tfvars: キー \"$key\" に対応する variable が $ENV_VARS にありません。"
  done < <(sed -nE 's/^[[:space:]]*([a-z_][a-z0-9_]*)[[:space:]]*=.*/\1/p' "$tfvars")
done

# ── (6) module 呼び出し ↔ 呼び出し先 variables.tf ───────────────────────────
for f in $tf_files; do
  tsv=$(tsv_of "$f")
  dir=$(dirname "$f")
  while IFS=$'\t' read -r _ mod _ _; do
    src=$(attr_of "$tsv" module "$mod" source)
    src=${src%\"}
    src=${src#\"}
    case "$src" in
      ./*|../*) ;;
      *) continue ;;  # レジストリ由来の module は対象外
    esac
    target="$dir/$src/variables.tf"
    if [ ! -f "$target" ]; then
      err "$f: module \"$mod\" の source \"$src\" に variables.tf がありません。"
      continue
    fi
    target_tsv=$(tsv_of "$(echo "$target" | sed 's#/\./#/#g')")
    [ -f "$target_tsv" ] || { blocks "$target" > "$TMP_DIR/mod_$mod.tsv"; target_tsv="$TMP_DIR/mod_$mod.tsv"; }

    declared=$(awk -F'\t' '$1=="variable" && $3=="@order"' "$target_tsv" | cut -f2)
    passed=$(awk -F'\t' -v m="$mod" '$1=="module" && $2==m && $3 !~ /^@/ && $3 != "source" && $3 != "depends_on" && $3 != "count" && $3 != "for_each" && $3 != "providers" {print $3}' "$tsv")

    for a in $passed; do
      in_list "$a" "$declared" && continue
      err "$f: module \"$mod\" に渡している \"$a\" が $target に宣言されていません。"
    done

    for d in $declared; do
      in_list "$d" "$passed" && continue
      if [ -z "$(attr_of "$target_tsv" variable "$d" default)" ]; then
        err "$f: module \"$mod\" が必須 variable \"$d\" を受け取っていません（$target に default なし）。"
      fi
    done
  done < <(awk -F'\t' '$1=="module" && $3=="@order"' "$tsv")
done

# ── (7) shared 化した .tf の symlink 整合と .jscpd.json ignore ──────────────
JSCPD=".jscpd.json"
ENVS="dev stg prod"
# 環境固有で symlink にしない .tf（state backend は環境ごとに prefix が違う）
ENV_LOCAL_TF="backend.tf"

for shared in "$INFRA_DIR"/environments/shared/*.tf; do
  [ -f "$shared" ] || continue
  name=$(basename "$shared")
  for env in $ENVS; do
    path="$INFRA_DIR/environments/$env/$name"
    if [ ! -e "$path" ]; then
      err "$path が存在しません（$shared を shared 化したなら 3 環境すべてに symlink を張る）。"
      continue
    fi
    if [ ! -L "$path" ]; then
      err "$path が symlink ではありません（../shared/$name への symlink が正）。"
      continue
    fi
    link=$(readlink "$path")
    if [ "$link" != "../shared/$name" ]; then
      err "$path の symlink 先が \"$link\" です（../shared/$name が正）。"
      continue
    fi
    if [ -f "$JSCPD" ] && ! grep -q "infra/environments/$env/$name\"" "$JSCPD"; then
      err "$path が $JSCPD の ignore にありません（symlink 経由の重複誤検知を防ぐため追記が必要）。"
    fi
  done
done

# 逆方向: 環境側に shared 対応の無い .tf が置かれていないか。
# 上の shared 起点のループは「shared にあるファイル」しか見ないため、
# 環境側だけに増えた実ファイルを検知できない（PR #615 で CodeRabbit が検出）。
for env in $ENVS; do
  for path in "$INFRA_DIR/environments/$env"/*.tf; do
    # -e は symlink を辿るため、リンク切れを拾えるよう -L も見る
    # （glob 未マッチのリテラルはどちらにも当たらず skip される）
    { [ -e "$path" ] || [ -L "$path" ]; } || continue
    name=$(basename "$path")
    in_list "$name" "$ENV_LOCAL_TF" && continue
    if [ ! -L "$path" ]; then
      err "$path が symlink ではありません（環境固有として許容するのは $ENV_LOCAL_TF のみ。shared 化して ../shared/$name への symlink にするか、ENV_LOCAL_TF に追記する）。"
      continue
    fi
    if [ ! -f "$INFRA_DIR/environments/shared/$name" ]; then
      err "$path の symlink 先 $INFRA_DIR/environments/shared/$name が存在しません。"
    fi
  done
done

if [ "$fail" -ne 0 ]; then
  echo "" >&2
  echo "infra lint に違反があります。上記を修正してください。" >&2
  exit 1
fi

echo "infra lint OK（description / sensitive / 2 層同期 / tfvars / module 引数 / symlink）"
