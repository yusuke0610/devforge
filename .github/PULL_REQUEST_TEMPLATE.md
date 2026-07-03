## 変更概要

<!-- 何を変えたか・なぜ変えたかを 1〜3 行で -->

## セルフレビューチェックリスト

### 必須確認

- [ ] `make ci` が pass している（lint + test + build-web）
- [ ] コメント・ドキュメント・エラーメッセージは日本語で記述した

### 条件付き確認（該当する場合のみ N/A と記入）

- [ ] `app/schemas/` または `app/routers/` を変更した場合: `make codegen-types` を実行し `web/src/api/generated.ts` の差分をコミットした
- [ ] 新しいページ・認証・ナビゲーション・レイアウトを変更した場合: E2E を実行した（`nix develop --command bash -c "cd web && npm run test:e2e"`）
- [ ] 新規環境変数を追加した場合: `env_keys.py` / `docs/api.md` / `infra/modules/cloud_run/main.tf` / `docker-compose.yml` の 4 箇所を同期した
- [ ] `web/src/` で日本語メッセージを `web/src/constants/messages.ts` の定数経由で参照した（リテラル直書きなし）

### 破壊的変更

- [ ] 破壊的変更なし（API 契約・DB スキーマ・既存の公開インターフェースに変更なし）
- [ ] 破壊的変更あり → 概要: <!-- ここに記入 -->

### ADR（設計判断を伴う変更の場合のみ）

- [ ] 新しいライブラリ採用・アーキテクチャ変更を伴う場合、ADR を作成した（または既存 ADR が対応している）
- [ ] ADR を新規作成・ステータス変更した場合: `docs/adr/README.md` の索引（一覧・テーマ・決定系統図）を更新した（存在・ステータスは `make lint-adr-index` で検証される）

---

PR タイトル形式: `<type>: <内容>`（日本語）
type: `feat` / `fix` / `docs` / `refactor` / `test` / `chore` / `infra`
