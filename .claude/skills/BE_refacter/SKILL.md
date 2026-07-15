---
name: BE_refacter
description: Use when reviewing or planning refactors for the DevForge FastAPI backend, especially for maintainability, redundant or missing unit tests, oversized modules or classes, responsibility separation, and directory structure changes. Trigger on requests such as “backend のリファクタリングを見て”, “保守性を確認”, “不要な単体テスト”, “単体テストは十分か”, “責務分離”, or “構成見直し”.
---

# Backend Refactor Review

## 先に読む

- `.claude/CLAUDE.md`
- `.claude/rules/backend/architecture.md`
- `.claude/rules/backend/python.md`
- `.claude/rules/backend/database.md`
- `.claude/rules/backend/auth-security.md`
- `.claude/rules/common/duplication.md`（DRY / 重複検知ポリシー）
- `report/dupe/jscpd-report.json` が存在すれば最新を読み込み、backend に該当する clone を抽出して Duplication Findings の素材にする

## 対象

- `backend/app/**`
- `backend/tests/**`
- `backend/alembic_migrations/**`
- 必要に応じて `backend/scripts/**`, `backend/Dockerfile`, `backend/requirements.txt`

## 成果物の出力先（必須）

レビュー本文はターミナルに垂れ流さず、必ずファイルへ保存する。スクロールで流れて読み返せなくなるのを防ぐためのルール。

- 保存先: `report/BE_report_<YYYYMMDD_HHMM>.md`
  - 例: `report/BE_report_20260516_1042.md`
  - `report/` が無ければ作成する (`mkdir -p report`)
  - タイムスタンプはレビュー開始時刻のローカルタイム (`date +%Y%m%d_%H%M`)
- ファイル中身は本ドキュメント末尾の「推奨出力フォーマット」に従う
- 既存の `BE_report_*.md` は削除しない（履歴として残す）

### ターミナルへの出力ルール

- レポート本文を assistant メッセージへ貼らない（ファイルにだけ書く）
- ターミナルには以下だけを返す:
  1. 保存先パス（`report/BE_report_YYYYMMDD_HHMM.md`）
  2. `Verdict` セクションの 3-5 行サマリのみ
  3. 次に取るべきアクション（あれば 1-2 行）
- Findings / Test Review / Structure Review / Refactor Plan などの詳細セクションはファイル参照に留める

## 目的

この skill の目的は、単なる感想ではなく「どこが保守しづらいか」「どのテストが低価値か」「どのテストが足りないか」「どの責務を分離すべきか」を、根拠付きでレビューすることです。

必ず以下を区別してください。

- 低価値テスト: 価値は低いが残しても害が少ない
- 不要テスト: 他のテストで十分に守られており、保守コストが勝つ
- テスト不足: バグが入りやすいのにカバーされていない
- 設計問題: モジュール分割や責務境界が悪く、変更容易性を落としている

## 調査の進め方

### 1. インベントリ

- `rg --files backend/app backend/tests backend/alembic_migrations`
- 大きいファイルを洗う: `rg --files backend/app backend/tests | xargs wc -l | sort -nr | head -n 30`
- まず以下の境界で構造を把握する
  - router: HTTP 入出力、認証、rate limit、エラー変換
  - service: ビジネスロジック、外部 API、PDF/Markdown 生成
  - repository: 永続化と問い合わせ
  - schema/model: API 契約、DB 契約
  - tests: ルータ、サービス、純粋関数、外部依存のモック

### 2. 保守性レビュー

以下のどれかに当てはまれば、責務分離候補として扱います。

- router が入力検証に加えて、ドメイン判断、永続化、外部 API 制御まで持っている
- service が I/O、ビジネスルール、整形、キャッシュ更新を同時に持つ
- repository が複数 aggregate の知識を横断しすぎている
- schema/model の変更理由が複数あり、1つの変更で広範囲に波及する
- 例外変換やメッセージ解決が各所に分散し、統一ルールが崩れている

サイズの目安は補助指標です。行数だけで断定しないこと。

- module が 400 行超で責務が複数ある
- class が 200 行超で状態と振る舞いが混在している
- router 関数が 40 行超で分岐や外部依存が多い
- service 関数が 60 行超で「問い合わせ」「判定」「整形」「保存」を連続で行う

### 3. 単体テストレビュー

不要と判定する条件:

- 同一分岐を別名で重複テストしている
- framework やライブラリの既知動作しか見ていない
- 実装詳細のモックや call count に強く依存し、仕様変更なしで壊れやすい
- 単純な schema/dto の受け渡しだけで、ドメイン価値を守っていない
- より上位のテストが同じ失敗を十分に検知できる

不要と断定してはいけない条件:

- 単純でも境界条件や回帰バグを実際に防いでいる
- セキュリティ、認可、例外変換、外部 API 失敗時の挙動を守っている
- SQLite 制約、ユニーク制約、子テーブル cascade など壊れやすい契約を守っている

不足と判定する観点:

- 純粋関数の分岐、スコア計算、日付処理、マッピング
- router の認証、認可、validation、HTTP status、エラーメッセージ変換
- repository の upsert、一意制約、削除 cascade、ユーザー境界
- 外部 API の timeout / unavailable / partial failure
- マイグレーション後の不変条件
- セキュリティ設定: cookie, CSRF, GitHub OAuth state, rate limit

### 4. 重複検知レビュー（Duplication Findings）

`make dupe-check` で `report/dupe/jscpd-report.json` を生成し、backend 配下の clone を抽出する。
生成されていない場合は `make dupe-check` を sandbox 無効で 1 回回してから本セクションに進む。

抽出した clone を以下の 3 分類でラベリングする（`.claude/rules/common/duplication.md` の基準に従う）。

- **本質的重複**（抽出すべき）: ドメインロジック / バリデーション / スコア計算 / エラーマッピング / API パスや env 名リテラル / DTO 変換ロジック
- **偶発的重複**（抽出しない）: SQLAlchemy の `created_at` / `updated_at` 定義などの boilerplate、Pydantic schema の field 列、pytest fixture の minimal scaffolding、import 文の塊
- **意味的重複**（jscpd では拾えない）: 変数名やシグネチャは違うが「同じ判断・同じ整形・同じ I/O パターン」を行うコード。grep + 目視で別途探す。例: 似た Cloud Tasks エンキューロジック、似たエラー → HTTPException 変換

本質的重複は「3 回目で抽出（Rule of Three）」を守る。2 箇所だけの重複は **記録するが、抽出は次の重複出現時まで保留**。

抽出先は `.claude/rules/common/duplication.md` の「Backend (FastAPI)」ヒエラルキーに従う:

1. 同一サブパッケージ内 → `_utils.py` / `_helpers.py`
2. ドメイン横断 → `backend/app/services/shared/`
3. 永続化 → `repositories/base.py`
4. HTTP 入出力 → `routers/<scope>/_responses.py`
5. モデル / DTO → `schemas/shared.py`

### 5. ディレクトリ構成レビュー

以下を見ます。

- `routers/`, `services/`, `repositories.py`, `models.py`, `schemas.py` の分割単位が適切か
- 1ファイルに複数ドメインの知識が混ざっていないか
- `services/` 配下が機能別サブパッケージで分けられるか
- `repositories.py` の肥大化を package 化で抑えるべきか
- PDF / Markdown / Intelligence / Blog のような機能境界がディレクトリ境界に反映されているか

構成変更を提案するときは、必ず次をセットで出します。

- 何が今の問題か
- どのファイルをどこへ分けるか
- 分けた後に依存方向がどう単純化されるか
- 今は見送るべき変更は何か

## レビューの厳しさ

- 「巨大だから分割」ではなく、「変更理由が複数だから分割」で判断する
- 「テスト数が少ない」ではなく、「高リスク経路が無防備」で判断する
- 「ディレクトリが気に入らない」ではなく、「探索コストや依存関係が悪い」で判断する

## 推奨出力フォーマット

下記テンプレートを `report/BE_report_<YYYYMMDD_HHMM>.md` に書き込む。ターミナルには貼らない。

````markdown
# Backend Refactor Review

## Verdict
- 保守性の総評を 3-5 行で要約

## Findings
### High
- [path/to/file.py:line] 問題点。なぜ危険か。どう分割または整理するか。

### Medium
- ...

### Low
- ...

## Test Review
### Remove or Merge
- [path] なぜ低価値か。削除しても何がカバーされるか。

### Add
- [path or module] どのケースを追加すべきか。守る仕様は何か。

## Duplication Findings
### High（本質的重複・抽出強く推奨）
- [path1:line] ↔ [path2:line] (jscpd: N tokens) 何が重複しているか。本質的な理由。抽出先候補（`services/shared/<name>.py` など）

### Medium（意味的重複・要検討）
- [path1] と [path2] の処理パターンが同義。差分は X のみ。共通ヘルパに切り出すと差分が明示できる。

### Allowed Duplication（記録のみ・抽出しない）
- [path:line] SQLAlchemy boilerplate などの偶発的重複。jscpd で検出されたが規約上抽出しない理由。

## Structure Review
### Oversized Modules or Classes
- [path] 責務が何個あるか。どう切るか。

### Directory Changes
- 提案する target 構成

```text
backend/app/
  routers/
  services/
  repositories/
  ...
```

## Refactor Plan
1. まず何を分けるか
2. 次にどのテストを整理するか
3. 最後に何を検証するか

## Validation
- 実行したコマンド
- 未実行ならその理由
````

## 最低限の検証コマンド

- `make lint-backend`
- `make test-backend`
- `make dupe-check`（重複検知。`report/dupe/jscpd-report.json` を生成。sandbox は無効化して実行）

特定ファイルだけ検証したい場合は `nix develop --command bash -c "cd backend && ruff check <path>"` を使う（devshell の Nix build 環境から PATH 解決 / ADR-0021 Phase 1）。生シェルで python / ruff を直接叩くのは禁止（backend の Python 環境が PATH に無く、WeasyPrint の動的ライブラリも解決できない）。

コード変更を含む場合は、少なくとも影響範囲のテストを回し、必要なら全件を回してください。
