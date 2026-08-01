---
name: RV
description: Use when reviewing the working diff after implementation and before stage — a diff-scoped review loop that detects bugs, contract violations, SSoT drift, and project rule violations, fixes High/Medium findings itself, and re-reviews until zero findings (max 3 rounds). Writes `report/RV_<timestamp>.md`. Trigger on requests such as "RV 実行", "/RV", "実装後レビュー", "差分をレビューして", "指摘がなくなるまで回して", "stage の前にレビュー".
---

# 実装後レビュー（RV）ループ

実装 → `make ci` green の後、`stage` の直前に回す**差分ベースのレビューループ**。
狙いは (1) レビュー観点を毎回同じ手順で当てる、(2) ループの経緯をレポートに残して後から追える、の 2 点。
PR 後の CodeRabbit まで指摘の発見が遅れるのを防ぐ。

**責務の境界**: RV は「今の差分が壊していないか」だけを見る。リポジトリ全体の保守性・重複の棚卸しは `*_refacter` 系 skill の担当であり、RV では扱わない。

## 先に読む

- `.claude/rules/common/review.md`（**レビュー観点・重大度の正本。必読**）
- `.claude/CLAUDE.md`
- 差分の領域に対応する rule（触れている領域のものだけ読む）
  - backend: `.claude/rules/backend/{architecture,layers,python,database,test,auth-security}.md`（agent 配下を触っていれば `agent.md` も）
  - web: `.claude/rules/web/{architecture,component-design,messages,typescript,test}.md`
  - infra: `.claude/rules/infra/{opentofu,test}.md`
- `.claude/rules/common/duplication.md` / `.claude/rules/common/tdd.md`

## レビュー対象の確定

```bash
git diff origin/main...HEAD --stat   # コミット済み
git diff --stat                      # 未コミット（unstaged）
git diff --cached --stat             # stage 済み
git ls-files --others --exclude-standard  # 未追跡（新規ファイル）
```

- 上記 3 つの差分と、未追跡ファイルの和集合を対象とする。`origin/main` が古いと差分を誤認するため、先に `git fetch origin main` する
- **未追跡ファイルの確認を省略しない**: RV は `git add` の前に走るため、新規追加したファイルは `git diff` 系のどれにも出てこない。新規ファイルこそレビュー価値が高いので、必ず本文を読む
  - `git status --porcelain` は使わない（新規ディレクトリを `?? path/` に畳んでしまい、中の個別ファイルが見えない）。`git ls-files --others --exclude-standard` はファイル単位で列挙し、gitignore 対象も除外する
  - 未追跡ファイルは全行が新規なので、行数は `wc -l` で数えて `+X` に合算する
- **差分が 1 件も無ければ「レビュー対象なし」とだけ返して即終了する**（レポートも作らない）
- 対象が確定したらターミナルに 1 行で返す: `対象: N files（うち新規 M）/ +X -Y lines`

## レビュー観点

**観点と重大度の正本は `.claude/rules/common/review.md`。** 本 skill は観点を持たない（二重管理を避ける）。
レビュー前に必ず review.md を読み、そこに列挙された観点（正しさ / 契約 / SSoT / ルール違反 / テスト随伴）を差分に当てる。

差分の行と、その行が依存・被依存する範囲だけを見る。差分に出てこないファイルの粗探しはしない。

## 修正ポリシー

重大度の定義と「自動修正しないもの」の線引きは `.claude/rules/common/review.md` に従う（High / Medium は自動修正、Low は記録のみ、設計判断・範囲逸脱はユーザー判断）。

- 修正対象が TDD スコープなら `.claude/rules/common/tdd.md` に従う（テストを先に赤くする）
- 修正したら `make ci` を回して green を確認してから次の Round に進む

## 観点のフィードバック（ループ終了時に必須）

検出した指摘のうち **`review.md` の既存観点で拾えなかったもの**は、`review.md` の該当カテゴリに 1 行追記する（追記ルールは review.md 末尾「観点の追記」）。
次回以降は観点として先に当たるようにするための工程で、**RV の成果物はコード修正だけではない**。

- 追記した場合はレポートの `観点の追記` セクションと、ターミナルの次アクションに明記する
- 既存観点で拾えた指摘は追記しない（観点の重複はノイズになる）

## ループ制御

1 周（Round）= **レビュー → 修正 → `make ci` → レポート追記 → 再レビュー**。

終了条件（いずれか）:

- **(a)** High / Medium がゼロ → 正常終了
- **(b)** Round 3 に到達 → 打ち切り
- **(c)** 同一の **High / Medium** 指摘が 2 周連続で解消しない → 打ち切り（修正が効いていないので機械的な再試行を止める）。Low は記録のみで意図的に残るため、判定に含めない

(b) / (c) で終わった場合は、**未解決の指摘をレポート冒頭に列挙し、ユーザーの判断を仰いで停止する**。勝手に stage へ進まない。

Round 2 以降のレビューは、前 Round の修正で新たに壊れていないかも見る（修正による回帰）。

## 成果物

- 保存先: `report/RV_<YYYYMMDD_HHMM>.md`
  - タイムスタンプは**ループ開始時刻で固定**する（`date +%Y%m%d_%H%M`）。Round ごとに**同じファイルへ追記**する
  - `report/` が無ければ作成する（`mkdir -p report`）
  - `report/` は gitignore 済みなのでコミットされない
- 既存の `RV_*.md` は削除しない（履歴として残す）

### ターミナルへの出力ルール

レポート本文を assistant メッセージへ貼らない。ターミナルに返すのは以下だけ:

1. レポートパス（`report/RV_YYYYMMDD_HHMM.md`）
2. 各 Round の High / Medium / Low 件数（1 行 1 Round）
3. `Verdict` の 3-5 行サマリ
4. 次アクション（stage へ進んでよい / ユーザー判断が要る指摘がある）

個別の指摘本文・修正差分はファイル参照に留める。

## 出力フォーマット

````markdown
# 実装後レビュー（RV）

- 対象: `origin/main...HEAD` + 未コミット差分 + 未追跡ファイル（N files（うち新規 M）/ +X -Y）
- 開始: YYYY-MM-DD HH:MM
- 終了理由: 指摘ゼロ / Round 3 到達 / 同一指摘が未解消

## 未解決の指摘（ユーザー判断待ち）
<!-- 正常終了時は「なし」。打ち切り時・自動修正しなかった指摘がある時のみ列挙 -->
- [重大度][path:line] 指摘。なぜ自動修正しなかったか（設計判断 / 範囲外）。対応案。

## Verdict
- 3-5 行の総評

## Round 1
### Findings
#### High
- [path:line] 何が問題か。どう壊れるか（具体的な入力・状態 → 誤った結果）。修正方針。
#### Medium
- ...
#### Low（記録のみ）
- ...

### Fixes
- [path:line] 何をどう直したか（1 行）

### Validation
- `make ci`: pass / fail（fail なら要点）

## Round 2
<!-- 同じ構成。前 Round の指摘がどう解消したかを明記する -->

## 観点の追記
<!-- review.md の既存観点で拾えなかった指摘があった場合のみ。無ければ「なし」 -->
- [.claude/rules/common/review.md の カテゴリ名] 追記した観点（1 行）。由来となった指摘。
````

## 注意

- **`/code-review` は Claude から起動できない**（組み込み CLI コマンドであり skill ではない）。差分レビューの手順は本 skill が内包する。ユーザーが手動で `/code-review` / `/code-review ultra` を併用するのは可
- 指摘が無いのに「一応直しておく」改変をしない。Round は差分を増やす場ではない
- リポジトリ全体のリファクタ提案は出さない（`*_refacter` の担当）。差分に閉じる
