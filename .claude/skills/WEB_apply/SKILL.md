---
name: WEB_apply
description: Use when applying the refactor plan produced by the WEB_refacter skill. Reads `report/WEB_report_<timestamp>.md` (latest by default, or a path passed as argument), confirms scope with the user, implements the changes against `web/`, runs lint/test/build, then writes a result report to `report/WEB_pr_<timestamp>.md`. Trigger on requests such as "WEB_apply 実行", "web のリファクタを適用", "FE レポートの内容を実装", "report の指摘を直して".
---

# Frontend Refactor Apply

`WEB_refacter` skill が生成したレビュー (`report/WEB_report_*.md`) を入力にして、実際のコード修正・検証・PR 用レポート作成までを行う skill。

## 先に読む

- `.claude/CLAUDE.md`
- `.claude/skills/WEB_refacter/SKILL.md`（出力フォーマットの参照元）
- `.claude/rules/web/architecture.md`
- `.claude/rules/web/typescript.md`
- `.claude/rules/web/test.md`

API 契約の変更を伴う場合は backend 側 (`backend/app/routers/*`, `backend/app/schemas.py`) も確認すること。

## 入力（対象レポートの選択）

引数で明示パスが渡されていればそれを使う。なければ `report/WEB_report_*.md` の中で最新（mtime 降順）を採用する。

```bash
# 明示
/WEB_apply report/WEB_report_20260516_1042.md

# 省略時 = 最新を自動採用
/WEB_apply
```

最初に必ずユーザーへ「採用したレポートのパス」を 1 行返す。

```text
採用レポート: report/WEB_report_20260516_1042.md
```

`report/` 配下に `WEB_report_*.md` が一つも無い場合はここで停止し、`/WEB_refacter` の実行を促す。

## 実装スコープの確認（必須）

レポートを読み込んだら、Findings を High / Medium / Low の件数だけ集計してユーザーへ提示し、どこまで実装するかを **毎回必ず聞く**。勝手に全件着手してはいけない。

提示例:

```text
採用レポート: report/WEB_report_20260516_1042.md
Findings: High 2 / Medium 4 / Low 6
Test Review: Remove 3 / Add 5
Structure: Oversized 2 / Directory 1

どこまで適用しますか？
  1) High のみ
  2) High + Medium
  3) Test Review (Remove/Add) も含める
  4) Structure (ディレクトリ移動・hook 切り出し) も含める
  5) 全部
  6) 個別に選ぶ（番号で指定）
```

`AskUserQuestion` で選ばせるのが望ましい。「個別」が選ばれた場合は、Findings の見出しを番号付きで列挙して再選択させる。

## 実装の進め方

1. **タスク化**: 採用した各項目を `TaskCreate` で 1 タスクずつ切り、`in_progress` → `completed` を必ず更新する。
2. **小さく分ける**: 「component 分割」「hook 切り出し」「テスト追加」「テスト削除」「ファイル移動」を別タスクにする。1 タスクあたりの diff は読める範囲に保つ。
3. **`web/` のコーディング規約を厳守**:
   - コメント・JSDoc は日本語
   - エラーメッセージ・トースト文言などユーザー向け表示は日本語
   - `any` は禁止。型を曖昧にせず適切に narrowing する
   - hook の責務を肥大化させない。「fetch + form state + 文言 + UI 判定」を 1 hook に詰めない
4. **Structure 変更（ファイル移動・分割・hook 切り出し）を含む場合**:
   - import パスの追従漏れに注意。`rg "from ['\"](\\.\\./)*<old_path>"` で参照を必ず洗う
   - CSS Module の path も追従する
   - 共通 → feature 配下へ降ろす場合、本当に他で使われていないか `rg` で確認してから移す
5. **テスト Add/Remove**:
   - Remove は「同じユーザー挙動を別テストが守っているか」をレポートの根拠と実 grep の両方で確認してから消す
   - Add は「守るユーザー挙動」をテスト名に書く（描画ではなく挙動を assert する）
   - snapshot の濫用を増やさない

## 検証（必須）

実装が一通り終わったら `make ci` 相当を回す。スキップ禁止。

```bash
make lint-web
make test-web
make build-web
```

または一括:

```bash
make ci
```

新規ページ・ルート追加、認証/ナビゲーション/レイアウト変更、サイドバーコンポーネント変更、UI フローに影響する API 変更を含む場合は E2E も回す:

```bash
nix develop --command bash -c "cd web && npm run test:e2e"
```

sandbox が `~/.cache/nix/fetcher-locks/*.lock` で落ちる場合は `dangerouslyDisableSandbox: true` で再実行する（CLAUDE.md の既知の例外）。

特定スクリプトだけ叩きたい場合のみ:

```bash
nix develop --command bash -c "cd web && npm run <script>"
```

lint / test / build に失敗したら、原因を直してから次の検証に進む。失敗を残したまま PR レポートを書かない。`--no-verify` 等で hook を skip しない。

## 成果物の出力先（必須）

実装と検証が完了したら、PR 用のサマリを必ずファイルへ書く。assistant メッセージに本文を貼らない。

- 保存先: `report/WEB_pr_<YYYYMMDD_HHMM>.md`
  - 例: `report/WEB_pr_20260516_1530.md`
  - `report/` が無ければ作成する (`mkdir -p report`)
  - タイムスタンプは **PR レポート書き出し時刻**（ローカル）。`date +%Y%m%d_%H%M`
- 既存 `WEB_pr_*.md` は履歴として残す。上書き禁止
- 採用元レポートのパスを冒頭に明記する

### ターミナルへの出力ルール

- 詳細はファイルにだけ書く
- ターミナルへ返すのは以下のみ:
  1. 採用レポートのパス
  2. PR レポートのパス（`report/WEB_pr_YYYYMMDD_HHMM.md`）
  3. `Summary` セクションの 3-5 行サマリ
  4. 検証結果（pass / fail）
  5. 残タスク（次に手をつけるべき項目があれば 1-2 行）

## PR レポートのフォーマット

下記テンプレートを `report/WEB_pr_<YYYYMMDD_HHMM>.md` に書き込む。

````markdown
# Frontend Refactor PR Report

- 採用レポート: report/WEB_report_YYYYMMDD_HHMM.md
- 実装ブランチ: <git branch>
- 適用スコープ: <High のみ / High+Medium / 全部 など>

## Summary
- 何を変えたかを 3-5 行で要約

## Applied Changes
### High
- [path/to/file.tsx:line] 何を直したか。元レポートの指摘番号や見出しを引用。

### Medium
- ...

### Low
- ...

## Test Changes
### Removed
- [path] 削除した理由。残った保護。

### Added
- [path] 追加したテストが守るユーザー挙動。

## Duplication Resolved
- [path] レポートの Duplication Findings (High/Medium) のうち何を統合したか。抽出先 (`hooks/useXxx.ts` / `utils/...` 等) と差分の吸収方法。
- 残した偶発的重複は Skipped へ。

## Structure Changes
- 変更前 / 変更後のディレクトリ構成や hook 切り出し（変更があった場合のみ）

```text
web/src/
  pages/
  components/
  hooks/
  ...
```

## Skipped
- 採用しなかった指摘と理由（後続 PR に回す、影響範囲が大きい、など）

## Validation
- `make lint-web`: pass / fail（fail なら抜粋）
- `make test-web`: pass / fail（fail なら抜粋、件数）
- `make build-web`: pass / fail
- E2E (`npm run test:e2e`): 実行有無と結果。実行しなかった場合は理由

## Follow-ups
- 次の PR で対応すべき項目
- 仕様判断が必要で保留にした項目
````

## 進め方の流れ（チェックリスト）

1. 採用レポートを決定し、パスをユーザーへ提示
2. Findings 集計を提示し、`AskUserQuestion` で適用スコープを選ばせる
3. 採用項目を `TaskCreate` で 1 つずつ切る
4. 各タスクを `in_progress` にして実装、終わったら `completed`
5. `make lint-web` / `make test-web` / `make build-web`（または `make ci`）を回す
6. UI フローに影響する変更なら E2E も回す
7. fail があれば直す。pass まで PR レポートを書かない
8. `report/WEB_pr_<YYYYMMDD_HHMM>.md` を書く
9. ターミナルにはパスとサマリだけ返す
