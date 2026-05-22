# DevForge - Claude Code ガイドライン

## このファイルの読み方

- 本ファイルは全体ルールの索引。AI エージェント（Claude Code 含む）が最初に読むべき内容を集約している。
- 領域固有ルール（backend / frontend / infra）は `.claude/rules/<scope>/*.md` に分割済み。対象パスを編集する際に自動でロードされる。重複は避け、詳細は各 rule ファイルへ寄せる。

## AI エージェント実行方法

**原則: 開発ツールはすべて Nix devshell 経由で実行する。** ホスト側に Python / Node / ruff / tofu / WeasyPrint 用ネイティブライブラリは入っていない前提。

### 第一選択: `make` ターゲット

Makefile は `nix develop --command bash -c "..."` でラップ済み。AI は基本これを使う。**最新の一覧と詳細は `make help`** で確認する（本表は AI が即時参照する代表的なターゲットのみ）。

| 用途 | コマンド |
|---|---|
| CI 相当一括 | `make ci` （= `lint + test + build-frontend`） |
| Backend lint | `make lint-backend` |
| Backend test | `make test-backend` |
| Frontend lint | `make lint-frontend` |
| Frontend test | `make test-frontend` |
| Lint 自動修正 | `make lint-fix` |
| マイグレーション | `make migrate` / `make migrate-create MSG="..."` |
| インフラ validate | `make infra-validate` |
| コード重複検知 | `make dupe-check` （結果: `report/dupe/jscpd-report.json`） |

セットアップ詳細・各コマンドの目的は `docs/development.md` を参照。

### 第二選択: `nix develop --command` ラッパー

make に無い操作（特定ファイルだけ ruff したい等）の場合のみ使う:

```bash
nix develop --command bash -c "cd backend && .venv/bin/python -m ruff check app/services/tasks/handlers/blog_summarize.py"
nix develop --command bash -c "cd backend && .venv/bin/python -m pytest tests/test_worker_extended.py -q"
nix develop --command bash -c "cd frontend && npm run test:e2e"
```

### 禁止: 生シェルでの直接実行

`cd backend && .venv/bin/python -m pytest ...` を nix の外で叩くと、`LD_LIBRARY_PATH` / `DYLD_LIBRARY_PATH` が未設定で WeasyPrint のインポートが `OSError: cannot load library 'libgobject-2.0-0'` で落ちる。AI は nix wrap を必ず通す。

### Sandbox と nix の競合（重要）

Claude Code の sandbox は `~/.cache/nix/fetcher-locks/*.lock` への書き込みを拒否する。`make lint-backend` / `make test-backend` を sandbox 有効で実行すると次のエラーになる:

```text
error: opening lock file "~/.cache/nix/fetcher-locks/...lock": Operation not permitted
```

この場合は sandbox を無効化して再実行する（Bash ツールの `dangerouslyDisableSandbox: true`）。nix の lock 書き込みは安全な操作なので例外として許容してよい。

## コーディング規約（共通）

- **コメント・ドキュメント**: コード内コメント・docstring・JSDoc はすべて**日本語**で記述する。
- **エラーメッセージ**: HTTPException の `detail` 等、ユーザーに返すメッセージはすべて**日本語**。
- **エラーメッセージのハードコード禁止**: ts/tsx でリテラル日本語を直接書かない（`throw new Error("...")` / `setError("...")` / `toast.error("...")` 等）。frontend 完結のメッセージは `frontend/src/constants/messages.ts` の定数を参照、API 経由のエラーは backend の `messages.json` 由来の `AppErrorResponse.message` を表示する。詳細: `.claude/rules/frontend/messages.md`
- **例外の握りつぶし禁止**: `except SomeException: pass` は禁止。最低でも `logger.debug/warning/error` でログを残す。補助処理（通知生成など）で抑制する場合も `logger.warning` でログを出すこと。
- **過剰な抽象化を避ける**: PEP8 を守るな、PEP8 を理解した上で抽象化しろ。

言語別の詳細ルールは `.claude/rules/{backend,frontend,infra}/` を参照。
領域横断の共通ルール（DRY / 重複検知）は `.claude/rules/common/duplication.md` を参照。

## CI 確認ルール

アプリケーションの改修後は、ローカルで CI 相当を pass させてから完了報告する。

```bash
# 一括（最速・推奨）
make ci
```

詳細なローカル CI 手順・個別コマンドは `docs/development.md`「テスト・リント」セクションを参照。

### E2E テストのトリガー

以下のいずれかに該当する変更を行った場合、E2E を必ず実行する:

- 新しいページまたはルートの追加
- 認証・ナビゲーション・レイアウトの変更
- 通知ベルなどサイドバーコンポーネントの変更
- バックエンド API の追加・変更で、フロントエンドの UI フローに影響するもの

```bash
nix develop --command bash -c "cd frontend && npm run test:e2e"
```

CI 定義: `.github/workflows/ci.yml`

## 失敗から学んだ知見

過去の手戻り・障害から導いた再発防止ルール。

- **テストで DB をモックしない**: 統合テストは実 DB（テスト用 SQLite セッション）に当てる。モック/本番乖離でマイグレーション失敗を見落とした実績がある。
- **新規ブランチは `origin/dev` 起点で切る**: `main` 起点だと不要差分が大量に乗る。
- **契約変更時は既存テストの assert を必ず見直す**: 戻り値・例外仕様を変える時、旧契約を固定化したテスト（例: `test_no_cache_returns_early` のような silent-return アサーション）が残ると修正の意図が後退する。テスト名と本体の両方を更新する。
- **`IntegrityError` 後の再 SELECT は `None` を判定する**: ユニーク制約衝突後の再取得で他セッションが先に commit したケースを想定し、`None` ならば明示的に `RuntimeError` を上げる。戻り値型が non-Optional な関数で握りつぶさないこと。
- **タスクハンドラの「黙って return」は禁止**: 失敗パスでは `NonRetryableError` / `RetryableError` を `raise` し、worker に `dead_letter` / `retrying` 遷移と通知発行を任せる。早期 return は呼び出し側に completed として観測される。
- **lint 失敗時は当該ファイルだけ確認**: `make lint-backend` が他ファイルの I001 等で落ちる場合、自分の変更分は `nix develop --command bash -c "cd backend && .venv/bin/python -m ruff check <touched_file>"` で個別検証してから進める（既存違反を巻き込まない）。

## 命名規約

| 種別 | 名前 |
|---|---|
| 職務経歴書（career history） | `Resume` / `resumes` テーブル |

## 環境変数

**正本**:
- 環境変数名の定数定義: `backend/app/core/env_keys.py`
- 用途と注入経路の一覧: `docs/api.md`「環境変数」セクション
- 本番（Cloud Run）の env block: `infra/modules/cloud_run/main.tf`
- ローカル開発の env: `docker-compose.yml`

backend 内で `os.getenv("XXX")` のように文字列リテラル直接参照は禁止。`from app.core import env_keys` した上で `os.getenv(env_keys.XXX)` を使う。新規環境変数を追加するときは env_keys.py のコメントに記載の手順（4 箇所同期）を必ず実行する。

## ADR（Architecture Decision Record）

技術選定・アーキテクチャ判断を行う際は必ず `docs/adr/` を確認し、既存の判断と矛盾しない実装を行うこと。

新たに重要な技術判断を行う場合は `CONTRIBUTING.md` の ADR 運用ルールに従い、ADR を作成してから実装を開始する。

- ADR 一覧: `docs/adr/`
- テンプレート: `docs/adr/0000-template.md`
- 運用ルール: `CONTRIBUTING.md`
