---
name: XR_refacter
description: Use when reviewing duplication that crosses backend / web / infra boundaries — DTO 二重定義 (backend schemas ↔ web types), エラーコードの BE/FE 同期, 環境変数名の infra/backend/CI 散在, README/CLAUDE.md/docs の手順重複. Triggers: "領域横断の重複を見て", "BE と FE の DTO 重複", "infra と backend で env 名がズレてる", "XR_refacter 実行", "クロスリポ重複レビュー".
---

# Cross-Realm Refactor Review (BE ↔ FE ↔ infra ↔ docs)

各領域内 (BE / FE / infra) の重複は `BE_refacter` / `WEB_refacter` / `INFRA_refacter` が見る。
この skill は **境界を跨ぐ重複だけ** に集中する。各領域内の問題は本 skill では扱わない。

## 先に読む

- `.claude/CLAUDE.md`
- `.claude/rules/common/duplication.md`
- `.claude/rules/backend/architecture.md`
- `.claude/rules/web/architecture.md`
- `.claude/rules/infra/opentofu.md`
- `report/dupe/jscpd-report.json`（存在すれば）

## 対象

境界を跨ぐ重複として、以下を主な対象とする。

| 観点 | BE 側 | FE 側 | infra/CI 側 |
|---|---|---|---|
| DTO / 型 | `backend/app/schemas/**` | `web/src/types.ts`, `formTypes.ts` | — |
| エラーコード | `backend/app/core/errors.py` | `web/src/utils/appError.ts` | — |
| API パス | `backend/app/routers/**` | `web/src/api/**` | — |
| 環境変数名 | `backend/app/core/settings.py` | `web/.env*`, `vite.config.*` | `infra/modules/cloud_run/main.tf` の `env` ブロック、`.github/workflows/ci.yml`、`docker-compose.yml` |
| 領域共通の値（region / image / project_id） | `core/settings.py` | — | `infra/environments/<env>/terraform.tfvars` |
| 手順説明 | `backend/README.md` | `web/README.md` | `infra/README.md` |
| プロジェクト概要 | — | — | `README.md`, `CLAUDE.md`, `AGENT.md`, `docs/**` |

## 成果物の出力先（必須）

- 保存先: `report/XR_report_<YYYYMMDD_HHMM>.md`
  - 例: `report/XR_report_20260516_1042.md`
  - `report/` が無ければ作成する (`mkdir -p report`)
- 既存の `XR_report_*.md` は削除しない（履歴として残す）

### ターミナルへの出力ルール

- レポート本文を assistant メッセージへ貼らない
- ターミナルには以下だけ返す:
  1. 保存先パス
  2. `Verdict` の 3-5 行サマリ
  3. 次に取るべきアクション 1-2 行

## 目的

「同じ意味を持つ情報が複数領域に重複して定義されている」状態を可視化し、Single Source of Truth (SSoT) を決めて他領域からはそこを参照する設計に寄せる。
領域跨ぎは「片方を変えてもう片方の変更を忘れる」のが最大のリスク。本 skill は **どの境界に SSoT 違反があるか** を明確にする。

## 調査の進め方

### 1. インベントリ収集

最初に `make dupe-check` を sandbox 無効で実行し `report/dupe/jscpd-report.json` を最新化する。

そのうえで以下を grep ベースで横断的に洗う:

- DTO の二重定義
  - `rg -n "class \w+\(BaseModel\)" backend/app/schemas/`
  - `rg -n "^(export )?(interface|type) \w+" web/src/types.ts web/src/formTypes.ts`
- API パスの散在
  - `rg -n "['\"]/api/" web/src/api/`
  - backend 側のパスは `routers/**` の `@router.<method>("/...")` を抽出
- 環境変数名の散在
  - `rg -n "os\.environ\[" backend/app/`
  - `rg -n "VITE_\w+" web/`
  - `rg -n "env\s*=\s*\[" infra/modules/`
  - `.github/workflows/*.yml` の `env:` / `with:` ブロック
- エラーコード
  - `backend/app/core/errors.py` の `ErrorCode` enum
  - `web/src/utils/appError.ts` のマップ定義
- 手順書
  - `README.md`, `CLAUDE.md`, `AGENT.md`, `docs/**`, `backend/README.md`, `web/README.md`, `infra/README.md` の見出し列を比較

### 2. 重複の分類

検出した重複を 3 つに分類する。

- **SSoT 違反**（要修正）: 同じ意味の情報が複数領域に独立して定義されており、片方の変更で他方が壊れる
  - 例: `User` DTO が backend と web で別個に定義され、フィールド追加時に同期忘れする
  - 例: `TURSO_DATABASE_URL` という名前が `settings.py` / `cloud_run/main.tf` / `ci.yml` / `docker-compose.yml` に文字列で散在
- **意図的な複製**（許容）: 言語境界やデプロイ境界で物理的に同期できないが、それぞれの正本がある
  - 例: Pydantic schema と TypeScript interface（言語が違うので別定義は不可避、ただし生成元 OpenAPI など SSoT 経路は検討余地あり）
  - 例: `terraform.tfvars` の env 別値（環境差分なので冗長ではない）
- **記述の重複**（統合候補）: README や docs の手順説明が複数ファイルに同じ手順を貼り付けている
  - 例: 「Nix devshell の入り方」を README.md と CLAUDE.md と docs/setup.md に貼っている
  - → 正本を 1 つに決めて他はリンク参照に置き換える

### 3. SSoT 候補の選定

SSoT 違反に対して、どこを正本にするかを提案する:

- **エラーコード**: `backend/app/core/errors.py` を正本とし、web は OpenAPI から型生成するか、enum を別途同期する運用ルールを明文化
- **環境変数名**: `backend/app/core/settings.py` の `Settings` モデルのフィールド名を正本とし、infra / CI はそれを参照（コメントで対応関係を明記）
- **API パス**: backend の router がパスの正本。web は API クライアントモジュール 1 箇所に定数化してから呼ぶ
- **DTO**: 短期は backend `schemas/` を正本として web は手動同期、中期は OpenAPI → TypeScript 型生成パイプラインを検討

### 4. 構造変更の提案

提案するときは以下をセットで出す:

- 現状の SSoT 違反箇所と影響範囲
- どの領域を正本に据えるか
- 他領域からの参照方法（手動同期 / 自動生成 / リンク）
- 移行時の互換性配慮（旧定義削除のタイミング、PR 分割の単位）

## レビューの厳しさ

- 「形が似ている」だけで SSoT 違反と断定しない。**変更理由が同じ**ことを確認する
- ドキュメント重複は「リンク参照に置換」だけで済む。コードと違って慎重になりすぎない
- DTO 自動生成（OpenAPI codegen 等）は重い投資。現状の手動同期が破綻していない場合は提案を Medium / Low に留める

## 推奨出力フォーマット

下記テンプレートを `report/XR_report_<YYYYMMDD_HHMM>.md` に書き込む。

````markdown
# Cross-Realm Refactor Review

## Verdict
- 領域横断の重複の総評を 3-5 行で要約

## SSoT Violations
### High（即時対応推奨）
- **観点**: <DTO / エラーコード / env 名 / API パス>
- **重複箇所**: [BE path:line] ↔ [FE path:line] ↔ [infra path:line]
- **リスク**: 何を変えると何が壊れるか
- **提案する SSoT**: どこを正本にするか
- **他領域の参照方法**: 手動同期 / 自動生成 / リンク参照

### Medium
- ...

### Low
- ...

## Allowed Duplication
- [path] 言語境界・物理境界で同期不可能なため許容する重複。記録のみ。

## Documentation Duplication
- [path1] と [path2] と [path3] に同じ手順 "<セクション名>" が貼られている。
- 正本候補: <path>。他はリンク参照に置換。

## Refactor Plan
1. まずどの SSoT を確定するか
2. 次にどの参照を置き換えるか（PR 単位の提案）
3. 最後にどの検証を回すか（BE / FE / infra の影響範囲）

## Validation
- 実行したコマンド（`make dupe-check`, `make lint-backend`, `make lint-web`, `make infra-validate` など）
- 未実行ならその理由
````

## 最低限の検証コマンド

- `make dupe-check`（sandbox 無効化必要）
- 影響範囲に応じて `make lint-backend` / `make lint-web` / `make infra-validate`
- 構造提案だけの場合は実装変更が無いので、grep / find の結果と jscpd レポートの抜粋を Validation に記録する

実装変更は `XR_apply` skill が担う。本 skill はレビューと提案までで止める。
