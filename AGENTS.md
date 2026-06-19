# DevForge - AI エージェント向けガイド（Codex 用エントリポイント）

このファイルは Codex など `AGENTS.md` を読む AI エージェント向けのエントリポイント。
Claude Code は `.claude/CLAUDE.md` を自動で読むが、**Codex は CLAUDE.md やパス連動の rule 自動ロードを行わない**ため、ここに読むべきファイルを明示する。

## 最初に必ず読む

- [.claude/CLAUDE.md](./.claude/CLAUDE.md) — 全体ルールの索引（実行方法・コーディング規約・コミット/PR フロー・命名・環境変数・ADR）。**作業前に必読。**

## 作業領域に応じて読む（該当するものを必ず読む）

Claude Code では対象パス編集時に自動ロードされる領域別ルール。Codex は自動ロードされないので、触る領域のものを手動で開くこと。

### 共通（全領域）

- [.claude/rules/common/duplication.md](./.claude/rules/common/duplication.md) — DRY / コード重複ポリシー（Rule of Three・抽出先ヒエラルキー）
- [.claude/rules/security.md](./.claude/rules/security.md) — セキュリティ規約（秘密情報・入力検証・認可・IAM 等）

### backend（`backend/` を触るとき）

- [.claude/rules/backend/architecture.md](./.claude/rules/backend/architecture.md) — ディレクトリ構成・責務分離
- [.claude/rules/backend/python.md](./.claude/rules/backend/python.md) — Python コーディング規約
- [.claude/rules/backend/database.md](./.claude/rules/backend/database.md) — DB / マイグレーション
- [.claude/rules/backend/auth-security.md](./.claude/rules/backend/auth-security.md) — 認証・認可
- [.claude/rules/backend/test.md](./.claude/rules/backend/test.md) — テスト方針

### web（`web/` を触るとき）

- [.claude/rules/web/architecture.md](./.claude/rules/web/architecture.md) — ディレクトリ構成・責務分離
- [.claude/rules/web/typescript.md](./.claude/rules/web/typescript.md) — TypeScript コーディング規約
- [.claude/rules/web/messages.md](./.claude/rules/web/messages.md) — メッセージ管理（リテラル禁止・SSoT）
- [.claude/rules/web/test.md](./.claude/rules/web/test.md) — テスト方針

### infra（`infra/` を触るとき）

- [.claude/rules/infra/opentofu.md](./.claude/rules/infra/opentofu.md) — OpenTofu / modules / environments
- [.claude/rules/infra/test.md](./.claude/rules/infra/test.md) — infra validate / テスト

## メンテナンス

`.claude/rules/` にファイルを追加・削除したら、この一覧も更新すること（Claude Code 側はパス連動の自動ロードなので一覧不要だが、Codex 側はこの明示リストが正本）。
