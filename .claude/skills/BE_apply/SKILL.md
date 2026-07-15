---
name: BE_apply
description: Use when applying the refactor plan produced by the BE_refacter skill. Reads `report/BE_report_<timestamp>.md` (latest by default, or a path passed as argument), confirms scope with the user, implements the changes against `backend/`, runs lint/tests, then writes a result report to `report/BE_pr_<timestamp>.md`. Trigger on requests such as "BE_apply 実行", "backend のリファクタを適用", "BE レポートの内容を実装", "report の指摘を直して".
---

# Backend Refactor Apply

`BE_refacter` skill が生成したレビュー (`report/BE_report_*.md`) を入力にして、実際のコード修正・検証・PR 用レポート作成までを行う skill。

## 先に読む

- `.claude/CLAUDE.md`
- `.claude/skills/BE_refacter/SKILL.md`（出力フォーマットの参照元）
- `.claude/rules/backend/architecture.md`
- `.claude/rules/backend/python.md`
- `.claude/rules/backend/database.md`
- `.claude/rules/backend/auth-security.md`
- `.claude/rules/backend/test.md`

## 入力（対象レポートの選択）

引数で明示パスが渡されていればそれを使う。なければ `report/BE_report_*.md` の中で最新（mtime 降順）を採用する。

```bash
# 明示
/BE_apply report/BE_report_20260516_1042.md

# 省略時 = 最新を自動採用
/BE_apply
```

最初に必ずユーザーへ「採用したレポートのパス」を 1 行返す。

```text
採用レポート: report/BE_report_20260516_1042.md
```

`report/` 配下に `BE_report_*.md` が一つも無い場合はここで停止し、`/BE_refacter` の実行を促す。

## 実装スコープの確認（必須）

レポートを読み込んだら、Findings を High / Medium / Low の件数だけ集計してユーザーへ提示し、どこまで実装するかを **毎回必ず聞く**。勝手に全件着手してはいけない。

提示例:

```text
採用レポート: report/BE_report_20260516_1042.md
Findings: High 3 / Medium 5 / Low 8
Test Review: Remove 2 / Add 4
Structure: Oversized 2 / Directory 1

どこまで適用しますか？
  1) High のみ
  2) High + Medium
  3) Test Review (Remove/Add) も含める
  4) Structure (ディレクトリ移動) も含める
  5) 全部
  6) 個別に選ぶ（番号で指定）
```

`AskUserQuestion` で選ばせるのが望ましい。「個別」が選ばれた場合は、Findings の見出しを番号付きで列挙して再選択させる。

## 実装の進め方

1. **タスク化**: 採用した各項目を `TaskCreate` で 1 タスクずつ切り、`in_progress` → `completed` を必ず更新する。
2. **小さく分ける**: 「責務分離」「ファイル分割」「テスト追加」「テスト削除」を別タスクにする。1 タスクあたりの diff は読める範囲に保つ。
3. **`backend/` のコーディング規約を厳守**:
   - コメント・docstring は日本語
   - HTTPException の `detail` は日本語
   - `except: pass` 禁止、最低限 `logger.warning`
   - 黙って return 禁止。失敗パスは `NonRetryableError` / `RetryableError` を `raise`
   - 統合テストで DB をモックしない（実 DB セッションを使う）
4. **Structure 変更（ファイル移動・分割）を含む場合**:
   - import パスの追従漏れに注意。`rg "from app\.<old_path>"` で参照を必ず洗う
   - `repositories.py` のような単一ファイル → package 化は、`__init__.py` で旧 API を再エクスポートするか、import 側を全部追従するかのどちらかを決めてから着手
5. **テスト Add/Remove**:
   - Remove は「同じ仕様を別テストが守っているか」をレポートの根拠と実 grep の両方で確認してから消す
   - Add は「守る仕様」をテスト名に書き、回帰時に意味が読める名前にする

## 検証（必須）

実装が一通り終わったら `make ci` 相当を回す。スキップ禁止。

```bash
make lint-backend
make test-backend
```

または一括:

```bash
make ci
```

sandbox が `~/.cache/nix/fetcher-locks/*.lock` で落ちる場合は `dangerouslyDisableSandbox: true` で再実行する（CLAUDE.md の既知の例外）。

特定ファイルだけ確認したい場合のみ:

```bash
nix develop --command bash -c "cd backend && ruff check <touched_file>"
nix develop --command bash -c "cd backend && python -m pytest <touched_test> -q"
```

lint / test に失敗したら、原因を直してから次の検証に進む。失敗を残したまま PR レポートを書かない。`--no-verify` 等で hook を skip しない。

## 成果物の出力先（必須）

実装と検証が完了したら、PR 用のサマリを必ずファイルへ書く。assistant メッセージに本文を貼らない。

- 保存先: `report/BE_pr_<YYYYMMDD_HHMM>.md`
  - 例: `report/BE_pr_20260516_1530.md`
  - `report/` が無ければ作成する (`mkdir -p report`)
  - タイムスタンプは **PR レポート書き出し時刻**（ローカル）。`date +%Y%m%d_%H%M`
- 既存 `BE_pr_*.md` は履歴として残す。上書き禁止
- 採用元レポートのパスを冒頭に明記する

### ターミナルへの出力ルール

- 詳細はファイルにだけ書く
- ターミナルへ返すのは以下のみ:
  1. 採用レポートのパス
  2. PR レポートのパス（`report/BE_pr_YYYYMMDD_HHMM.md`）
  3. `Summary` セクションの 3-5 行サマリ
  4. 検証結果（pass / fail）
  5. 残タスク（次に手をつけるべき項目があれば 1-2 行）

## PR レポートのフォーマット

下記テンプレートを `report/BE_pr_<YYYYMMDD_HHMM>.md` に書き込む。

````markdown
# Backend Refactor PR Report

- 採用レポート: report/BE_report_YYYYMMDD_HHMM.md
- 実装ブランチ: <git branch>
- 適用スコープ: <High のみ / High+Medium / 全部 など>

## Summary
- 何を変えたかを 3-5 行で要約

## Applied Changes
### High
- [path/to/file.py:line] 何を直したか。元レポートの指摘番号や見出しを引用。

### Medium
- ...

### Low
- ...

## Test Changes
### Removed
- [path] 削除した理由。残った保護。

### Added
- [path] 追加したテストが守る仕様。

## Duplication Resolved
- [path] レポートの Duplication Findings (High/Medium) のうち何を統合したか。抽出先 (`services/shared/...` 等) と差分の吸収方法。
- 残した偶発的重複は Skipped へ。

## Structure Changes
- 変更前 / 変更後のディレクトリ構成（変更があった場合のみ）

```text
backend/app/
  routers/
  services/
  ...
```

## Skipped
- 採用しなかった指摘と理由（後続 PR に回す、影響範囲が大きい、など）

## Validation
- `make lint-backend`: pass / fail（fail なら抜粋）
- `make test-backend`: pass / fail（fail なら抜粋、件数）
- 追加で回したコマンドがあれば列挙

## Follow-ups
- 次の PR で対応すべき項目
- 仕様判断が必要で保留にした項目
````

## 進め方の流れ（チェックリスト）

1. 採用レポートを決定し、パスをユーザーへ提示
2. Findings 集計を提示し、`AskUserQuestion` で適用スコープを選ばせる
3. 採用項目を `TaskCreate` で 1 つずつ切る
4. 各タスクを `in_progress` にして実装、終わったら `completed`
5. `make lint-backend` と `make test-backend`（または `make ci`）を回す
6. fail があれば直す。pass まで PR レポートを書かない
7. `report/BE_pr_<YYYYMMDD_HHMM>.md` を書く
8. ターミナルにはパスとサマリだけ返す
