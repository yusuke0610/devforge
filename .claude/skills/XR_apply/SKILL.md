---
name: XR_apply
description: Use when applying the cross-realm refactor plan produced by the XR_refacter skill. Reads `report/XR_report_<timestamp>.md` (latest by default, or a path passed as argument), confirms scope with the user, implements SSoT consolidation across backend / web / infra / docs in a single PR, runs the impacted validations, then writes a result report to `report/XR_pr_<timestamp>.md`. Trigger on requests such as "XR_apply 実行", "領域横断のリファクタを適用", "XR レポートの内容を実装", "BE/FE/infra の SSoT 統合を実装".
---

# Cross-Realm Refactor Apply

`XR_refacter` skill が生成したレビュー (`report/XR_report_*.md`) を入力にして、領域跨ぎ (BE / FE / infra / docs) の SSoT 統合を **1 PR で扱う** ための skill。

各領域単独の修正は `BE_apply` / `WEB_apply` / `INFRA_apply` に委ねる。本 skill は「複数領域に同時に手を入れないと意味がない」変更だけを扱う。

## 先に読む

- `.claude/CLAUDE.md`
- `.claude/skills/XR_refacter/SKILL.md`（出力フォーマットの参照元）
- `.claude/rules/common/duplication.md`
- `.claude/rules/backend/architecture.md`
- `.claude/rules/web/architecture.md`
- `.claude/rules/infra/opentofu.md`

影響範囲に応じて backend/web/infra 各 rules も追加で読む。

## 入力（対象レポートの選択）

引数で明示パスが渡されていればそれを使う。なければ `report/XR_report_*.md` の中で最新（mtime 降順）を採用する。

```bash
/XR_apply report/XR_report_20260516_1042.md
/XR_apply
```

最初に必ずユーザーへ「採用したレポートのパス」を 1 行返す。

```text
採用レポート: report/XR_report_20260516_1042.md
```

`report/` 配下に `XR_report_*.md` が無い場合は停止し、`/XR_refacter` の実行を促す。

## 実装スコープの確認（必須）

レポートを読み込んだら、SSoT Violations を High / Medium / Low の件数と Documentation Duplication の件数で集計してユーザーへ提示し、どこまで適用するかを **毎回必ず聞く**。勝手に全件着手してはいけない。

提示例:

```text
採用レポート: report/XR_report_20260516_1042.md
SSoT Violations: High 2 / Medium 4 / Low 3
Documentation Duplication: 5
Allowed Duplication: 7（記録のみ・実装変更なし）

どこまで適用しますか？
  1) High のみ
  2) High + Medium
  3) Documentation Duplication も含める
  4) 全部
  5) 個別に選ぶ（番号で指定）
```

`AskUserQuestion` で選ばせるのが望ましい。

## 実装の進め方

1. **タスク化**: 採用した各 SSoT Violation を `TaskCreate` で 1 タスクずつ切る。1 SSoT = 1 タスク（BE / FE / infra をまたいでも 1 タスクとして扱う）。
2. **領域ごとの規約厳守**:
   - backend: コメント・docstring 日本語、例外握りつぶし禁止
   - web: コメント・JSDoc 日本語、any 禁止
   - infra: modules の variable 化、env 別値は tfvars で
3. **SSoT 統合パターン**:
   - **環境変数名**: backend `settings.py` を正本に。infra の `cloud_run/main.tf` と `.github/workflows/ci.yml`、`docker-compose.yml` を順に書き換える。コメントで「正本: backend/app/core/settings.py の `Settings.XXX`」と明記
   - **エラーコード**: backend `core/errors.py` の `ErrorCode` 列挙を正本に。web `utils/appError.ts` のマップを手で同期。OpenAPI codegen は本 PR の対象外（別 PR）
   - **API パス**: web `api/<scope>.ts` に定数 `const ENDPOINTS = { ... }` を作り、コンポーネントからは定数経由でのみ参照させる
   - **DTO**: backend が正本。web `types.ts` / `formTypes.ts` を手動同期し、対応コメントを残す
   - **ドキュメント手順**: 正本に決めたファイルだけ残し、他は `> 手順は [<正本パス>](<相対 path>) を参照` の 1 行に置換
4. **import / 参照パスの追従**: ファイル移動や定数化を含む場合、`rg` で全参照を洗ってから着手
5. **コミット粒度**: SSoT 1 つ = 1 コミットを目安に。BE/FE/infra 同時変更が必要な場合でも、レビュアブルな単位に分ける

## 検証（必須）

実装した領域に応じて、該当する検証コマンドを **すべて** 回す。スキップ禁止。

```bash
# 影響範囲に応じて
make lint-backend
make test-backend
make lint-web
make test-web
make build-web
make infra-fmt-check
make infra-validate
make dupe-check
```

または一括:

```bash
make ci
```

sandbox が `~/.cache/nix/fetcher-locks/*.lock` で落ちる場合は `dangerouslyDisableSandbox: true` で再実行する（CLAUDE.md の既知の例外）。

UI フローに影響する API 変更を含む場合は E2E も回す:

```bash
nix develop --command bash -c "cd web && npm run test:e2e"
```

検証 fail を残したまま PR レポートを書かない。`--no-verify` 等で hook を skip しない。

## 成果物の出力先（必須）

- 保存先: `report/XR_pr_<YYYYMMDD_HHMM>.md`
- 既存 `XR_pr_*.md` は履歴として残す。上書き禁止
- 採用元レポートのパスを冒頭に明記

### ターミナルへの出力ルール

- 詳細はファイルにだけ書く
- ターミナルへ返すのは:
  1. 採用レポートのパス
  2. PR レポートのパス
  3. `Summary` 3-5 行
  4. 検証結果（領域ごとに pass / fail）
  5. 残タスク 1-2 行

## PR レポートのフォーマット

````markdown
# Cross-Realm Refactor PR Report

- 採用レポート: report/XR_report_YYYYMMDD_HHMM.md
- 実装ブランチ: <git branch>
- 適用スコープ: <High のみ / 全部 など>

## Summary
- 何を SSoT として統合したかを 3-5 行で要約

## SSoT Consolidations
### High
- **観点**: <env 名 / エラーコード / DTO / API パス>
- **SSoT に据えた場所**: [path:line]
- **更新した参照元**: [BE path], [FE path], [infra path]
- **互換性配慮**: <旧定義の deprecation や PR 分割の有無>

### Medium
- ...

### Low
- ...

## Documentation Consolidations
- 正本: [path]
- リンク参照に置換した箇所: [path1], [path2], ...

## Skipped
- 採用しなかった SSoT Violation と理由（影響範囲大、別 PR、自動生成導入待ちなど）

## Validation
- `make lint-backend`: pass / fail
- `make test-backend`: pass / fail
- `make lint-web`: pass / fail
- `make test-web`: pass / fail
- `make build-web`: pass / fail
- `make infra-fmt-check` / `make infra-validate`: pass / fail
- `make dupe-check`: 重複率の before / after
- E2E: 実行有無と結果

## Follow-ups
- 次の PR で対応すべき項目（OpenAPI codegen 導入、別 SSoT 統合など）
````

## 進め方の流れ（チェックリスト）

1. 採用レポートを決定し、パスをユーザーへ提示
2. SSoT / Documentation 集計を提示し、`AskUserQuestion` で適用スコープを選ばせる
3. 採用項目を `TaskCreate` で 1 つずつ切る
4. 各タスクを `in_progress` にして実装、終わったら `completed`
5. 影響範囲に応じた検証コマンドを全部回す
6. `make dupe-check` で before/after の重複率を比較
7. fail があれば直す。pass まで PR レポートを書かない
8. `report/XR_pr_<YYYYMMDD_HHMM>.md` を書く
9. ターミナルにはパスとサマリだけ返す
