# 開発ガイド

ローカル環境のセットアップ、開発サーバー起動、テスト・リント実行までを扱います。

## セットアップ

### Nix devshell（必須）

開発ツール（Python 3.13 / Node.js 22 / ruff / tofu / WeasyPrint ネイティブライブラリ等）はすべて [Nix](https://nixos.org/download/) devshell で提供する。ホスト OS への直接インストールは想定していない。

```bash
# フレーク機能を有効化（初回のみ）
# ~/.config/nix/nix.conf または /etc/nix/nix.conf に以下を追加
# experimental-features = nix-command flakes

nix develop
```

#### direnv で自動起動

[direnv](https://direnv.net/) がインストール済みであれば、`.envrc` が同梱されているためディレクトリに移動するだけで Nix devshell が自動起動する。

```bash
direnv allow   # 初回のみ許可が必要
```

### ローカル開発

> **前提**: 開発ツール（Python / Node / ruff / tofu / WeasyPrint 用ネイティブライブラリ）はすべて Nix devshell で提供する。ホスト側に直接インストールしない方針のため、コマンドは `make` 経由（内部で `nix develop --command` ラップ）で実行する。

#### 初回セットアップ

```bash
nix develop          # devshell に入る（または direnv で自動）
make setup           # git hooks + backend (Nix devshell が依存を提供 / .venv なし) + web (npm ci)
make generate-keys   # JWT RS256 鍵ペアを生成
touch backend/.env   # 環境変数を設定する（必要な変数一覧: docs/api.md「環境変数」セクション参照）
```

#### Docker 起動（推奨: FastAPI + Redis + libSQL）

```bash
make dev             # docker compose up
make dev-build       # 再ビルドして起動
make dev-down        # 停止
```

`docker-compose.yml` で以下のサービスをまとめて起動する:

- `api`: FastAPI（`backend/Dockerfile` をビルド）
- `redis`: レート制限・キャッシュ
- `libsql`: libSQL サーバー（`ghcr.io/tursodatabase/libsql-server`）。`/var/lib/sqld` を `libsql_data` ボリュームに永続化

DB 接続先は compose 内で `TURSO_DATABASE_URL=http://libsql:8080` に固定されている。

#### Agent 機能（LLM）をローカルで試す場合

Ollama は compose に含めず**ホスト側で起動する**設計（ADR-0010）。macOS の Docker は GPU（Metal）を使えず、コンテナ内推論は大幅に遅くなるため。API コンテナは `OLLAMA_BASE_URL`（既定: `http://host.docker.internal:11434`）でホストの Ollama に接続する。

```bash
ollama serve          # アプリ起動済みなら不要
ollama pull llama3.2  # OLLAMA_MODEL の既定値
```

ローカルの compose では `LLM_LOCAL_OLLAMA` が既定 `1`（無料パス）で、選択モデルに関わらず全リクエストがホストの Ollama に流れる。実プロバイダの API（Anthropic / OpenAI / Gemini）で試す場合は、`.env` に `LLM_LOCAL_OLLAMA=0` と対応する API キー（例: `ANTHROPIC_API_KEY`）を設定して再起動し、UI のモデル選択で該当プロバイダのモデル（Claude / GPT / Gemini）を選ぶ。プロバイダはモデルエイリアスに紐づいて切り替わるため、グローバルな `LLM_PROVIDER` は無い（ADR-0013）。

#### フロントエンド単体起動（バックエンドは docker / 別途）

```bash
make dev-web    # Vite 開発サーバー（http://localhost:5173）
make dev-proxy       # Vite + Cloudflare Pages dev proxy（http://localhost:8788）
```

#### バックエンドだけ uvicorn で動かしたい場合

```bash
# libSQL だけ compose で起動（ホストの 127.0.0.1:8080 に公開）
docker compose up libsql

# 別ターミナルで uvicorn 起動（nix devshell 内で実行）
nix develop --command bash -c "cd backend && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000"
```

`backend/.env`:

```env
TURSO_DATABASE_URL=http://127.0.0.1:8080
TURSO_AUTH_TOKEN=
```

#### マスタデータ変更時の再起動

シードデータ（`backend/app/db/seed.py`）を変更した場合は、libSQL ボリュームを破棄して再起動する。

```bash
make dev-down
docker volume rm devforge_libsql_data
make dev
```

#### TablePlus からローカル libSQL に接続する

1. TablePlus で **新規接続** → **libSQL** を選択
2. **URL** に `http://127.0.0.1:8080` を指定（`docker compose up libsql` 経由）
3. **Token** は空のままで OK
4. **テスト** → **接続**

> **注意**: 旧 SQLite ファイル方式（`data/devforge.sqlite` の bind mount, DBeaver の SQLite 直接接続）は廃止しました。

## テスト・リント

> すべて Nix devshell 経由で実行する（`make` が `nix develop --command` をラップしている）。

### CI 相当を一括実行

```bash
make ci          # lint + test + build-web
```

### TDD（決定論的ロジック層）— ADR-0019

ミューテーションテスト対象と同じスコープ（backend: `backend/pyproject.toml` の `[tool.mutmut] only_mutate` / web: `web/stryker.conf.json` の `mutate`）の実装変更は、**テストを先に書く TDD（red → green → refactor）で行う**。手順の正本は [`.claude/rules/common/tdd.md`](../.claude/rules/common/tdd.md)。

テスト差分の随伴は機械ゲートで検証される（`make lint` / `make ci` / CI の test-backend ジョブに含まれる）:

```bash
make lint-tdd    # TDD 対象の実装変更にテスト差分が随伴しているか検知
```

- 振る舞いを変えない変更（リネーム・コメント修正・機械的リファクタ等）は、コミットメッセージに `Tdd-Exempt: <理由>` トレーラーを付けると skip される（理由は PR レビューで確認）。コミット前のローカル一時実行は `TDD_EXEMPT=1 make ci` で代用できる
- 対象スコープの追加・削除は mutation 設定側を編集する（TDD 用の別リストは持たない）

### バックエンド

```bash
make lint-backend       # ruff check（app / tests / alembic_migrations）
make typecheck-backend  # pyright 型チェック（make lint に含まれる）
make test-backend       # pytest -q tests
make lint-fix           # ruff --fix（自動修正）
```

特定ファイルだけ ruff したい場合:

```bash
nix develop --command bash -c "cd backend && ruff check <path>"
```

> **pyright の前提**: import 解決先の Python は実行側が `--pythonpath` で明示する（ADR-0021 Phase 1）。ローカル・CI とも `make typecheck-backend` が devshell の python3（uv2nix build）を渡す（CI も同じ make ターゲットを呼ぶ / ADR-0021 Phase 2）。pyright のバージョンピンは Makefile の `typecheck-backend` が正本。

### フロントエンド（ユニット・ビルド）

```bash
make lint-web       # eslint
make test-web       # vitest
make build-web      # Vite ビルド
```

### フロントエンド E2E（Playwright）

```bash
nix develop --command bash -c "cd web && npm run test:e2e"        # ヘッドレス
nix develop --command bash -c "cd web && npm run test:e2e:ui"     # UI モード（デバッグ用）
```

E2E テストは `web/e2e/` に配置。新しいページ・ルート・認証/ナビゲーション/レイアウト変更時は必ず実行すること。

### インフラ（OpenTofu）

```bash
make infra-fmt-check        # tofu fmt -check
make infra-validate         # dev / stg / prod を順に validate
```

詳細は [deployment.md](./deployment.md) の「インフラ構成（OpenTofu）」を参照。

### ミューテーションテスト（mutmut / Stryker）— 週次

テストスイートの検出力（弱い assertion / 実装なぞりテスト）を測る（設計判断: [ADR-0017](./adr/0017-mutation-testing-and-slack-notifications.md)）。
**フル実行は長時間かかるため通常 CI には含まれない。** 週次（毎週月曜 3:00 JST）の `.github/workflows/mutation.yml` が実行し、結果を Slack（`SLACK_WEBHOOK_URL_QUALITY`）へ通知する。手動実行は GitHub Actions の workflow_dispatch（`gh workflow run mutation.yml`）。

```bash
make mutation-backend   # mutmut（対象: backend/pyproject.toml の [tool.mutmut]）
make mutation-web       # Stryker（対象: web/stryker.conf.json）
```

ローカルで短時間だけ試す場合（対象を絞る）:

```bash
# backend: ミュータント名のグロブで絞る（モジュールパス + '*'）
nix develop --command bash -c "cd backend && python -m mutmut run 'app.services.shared.sort_utils*'"
# web: --mutate でファイルを絞る
nix develop --command bash -c "cd web && npx stryker run --mutate 'src/utils/text.ts'"
```

結果の確認:

```bash
# backend: 生存ミュータント一覧 / TUI ブラウズ / CI 用 JSON（mutants/mutmut-cicd-stats.json）
nix develop --command bash -c "cd backend && python -m mutmut results"
nix develop --command bash -c "cd backend && python -m mutmut browse"
# web: HTML レポート
open web/reports/mutation/mutation.html
```

- 生成物（`backend/mutants/` / `web/reports/` / `web/.stryker-tmp/`）は gitignore 済み。
- score が `MUTATION_SCORE_THRESHOLD`（初期値 80%。`mutation.yml` の env）未満だと Slack 通知が ⚠️ で強調される。Phase 1 は warn-only（fail しない）。

## Slack 通知（CI / デプロイ / 品質 / 依存更新）

GitHub Actions の結果を用途別の Slack チャンネルへ Incoming Webhook で通知する（[ADR-0017](./adr/0017-mutation-testing-and-slack-notifications.md)）。

| GitHub Secret | 用途 | 送信元 workflow |
|---|---|---|
| `SLACK_WEBHOOK_URL_CI` | 通常 CI の失敗のみ | `notify.yml` |
| `SLACK_WEBHOOK_URL_DEPLOY` | Cloud Run / Cloudflare Pages デプロイ結果（成功・失敗とも） | `notify.yml` |
| `SLACK_WEBHOOK_URL_QUALITY` | 週次ミューテーションテスト結果（killed / survived / score） | `mutation.yml` |
| `SLACK_WEBHOOK_URL_DEPS` | Renovate / Dependabot の依存更新 PR 起票 | `deps-notify.yml` |

### Secrets の登録手順（チャンネル作成後）

1. Slack で通知先チャンネルを作成し、各チャンネルに [Incoming Webhook](https://api.slack.com/messaging/webhooks) を発行する（チャンネルごとに 1 つ）
2. 発行された Webhook URL を GitHub Secrets に登録する:

   ```bash
   gh secret set SLACK_WEBHOOK_URL_CI      --body "https://hooks.slack.com/services/..."
   gh secret set SLACK_WEBHOOK_URL_DEPLOY  --body "https://hooks.slack.com/services/..."
   gh secret set SLACK_WEBHOOK_URL_QUALITY --body "https://hooks.slack.com/services/..."
   gh secret set SLACK_WEBHOOK_URL_DEPS    --body "https://hooks.slack.com/services/..."
   ```

3. 動作確認: `gh workflow run mutation.yml` を手動実行し QUALITY チャンネルへの通知を確認する

> **Secret 未登録の間の挙動**: 各通知ステップは Webhook が空だと静かに skip される（ワークフローは green のまま）。チャンネル作成前に導入しても CI は壊れない。
