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
make setup           # git hooks + backend (.venv + uv) + frontend (npm ci)
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
make dev-frontend    # Vite 開発サーバー（http://localhost:5173）
make dev-proxy       # Vite + Cloudflare Pages dev proxy（http://localhost:8788）
```

#### バックエンドだけ uvicorn で動かしたい場合

```bash
# libSQL だけ compose で起動（ホストの 127.0.0.1:8080 に公開）
docker compose up libsql

# 別ターミナルで uvicorn 起動（nix devshell 内で実行）
nix develop --command bash -c "cd backend && .venv/bin/uvicorn app.main:app --reload --host 0.0.0.0 --port 8000"
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
make ci          # lint + test + build-frontend
```

### バックエンド

```bash
make lint-backend    # ruff check（app / tests / alembic_migrations）
make test-backend    # pytest -q tests
make lint-fix        # ruff --fix（自動修正）
```

特定ファイルだけ ruff したい場合:

```bash
nix develop --command bash -c "cd backend && .venv/bin/python -m ruff check <path>"
```

### フロントエンド（ユニット・ビルド）

```bash
make lint-frontend       # eslint
make test-frontend       # vitest
make build-frontend      # Vite ビルド
```

### フロントエンド E2E（Playwright）

```bash
nix develop --command bash -c "cd frontend && npm run test:e2e"        # ヘッドレス
nix develop --command bash -c "cd frontend && npm run test:e2e:ui"     # UI モード（デバッグ用）
```

E2E テストは `frontend/e2e/` に配置。新しいページ・ルート・認証/ナビゲーション/レイアウト変更時は必ず実行すること。

### インフラ（OpenTofu）

```bash
make infra-fmt-check        # tofu fmt -check
make infra-validate         # dev / stg / prod を順に validate
```

詳細は [deployment.md](./deployment.md) の「インフラ構成（OpenTofu）」を参照。
