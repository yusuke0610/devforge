.PHONY: help \
	setup install-hooks install-backend install-frontend generate-keys \
	dev dev-build dev-down dev-frontend preview-frontend dev-proxy dev-proxy-only \
	test test-backend test-frontend \
	lint lint-backend lint-frontend lint-frontend-messages lint-fix \
	format format-check \
	ci \
	dupe-check dupe-check-html dupe-clean \
	build-frontend build-backend deploy-frontend \
	gen-redirects codegen-types \
	migrate migrate-create \
	infra-fmt infra-fmt-check infra-validate-dev infra-validate-stg infra-validate-prod infra-validate \
	clean

# デフォルトターゲット: ヘルプ表示
help:
	@echo "Usage: make <target>"
	@echo ""
	@echo "セットアップ"
	@echo "  setup             初回セットアップ (hooks + backend + frontend)"
	@echo "  install-hooks     git hooks を設定"
	@echo "  install-backend   Backend 依存パッケージをインストール"
	@echo "  install-frontend  Frontend 依存パッケージをインストール"
	@echo "  generate-keys     JWT RSA 鍵ペアを生成"
	@echo ""
	@echo "ローカル開発"
	@echo "  dev               docker-compose で API + Ollama を起動"
	@echo "  dev-build         再ビルドして起動"
	@echo "  dev-down          docker-compose を停止"
	@echo "  dev-frontend      Frontend 開発サーバーを起動 (Vite / localhost:5173)"
	@echo "  preview-frontend  ビルド済みを wrangler でローカル提供 (HMR なし / localhost:8788)"
	@echo ""
	@echo "テスト・リント"
	@echo "  ci                lint + test + build-frontend を一括実行 (CI 相当)"
	@echo "  test              全テスト (backend + frontend)"
	@echo "  test-backend      Backend: pytest"
	@echo "  test-frontend     Frontend: vitest"
	@echo "  lint              全リント (backend + frontend)"
	@echo "  lint-backend      Backend: ruff check"
	@echo "  lint-frontend     Frontend: eslint"
	@echo "  lint-frontend-messages  Frontend: setError等にリテラル日本語が渡っていないか検知"
	@echo "  lint-fix          リント自動修正 (ruff + eslint)"
	@echo "  format            Prettier で整形"
	@echo "  format-check      Prettier チェック"
	@echo ""
	@echo "コード重複検知 (jscpd)"
	@echo "  dupe-check        重複検知を実行し report/dupe/ に JSON/HTML/Markdown を出力"
	@echo "  dupe-check-html   同上 (HTML レポート出力後にパスを表示)"
	@echo "  dupe-clean        report/dupe/ を削除"
	@echo ""
	@echo "ビルド"
	@echo "  build-frontend    Vite ビルド"
	@echo "  build-backend     Docker イメージビルド"
	@echo "  deploy-frontend   Cloudflare Pages へビルド＆デプロイ (CLOUD_RUN_URL=... 指定可)"
	@echo "  gen-redirects     Cloudflare Pages 用 _redirects を生成 (CLOUD_RUN_URL=... 指定可)"
	@echo "  codegen-types     OpenAPI から frontend 型 (src/api/generated.ts) を再生成 (ADR-0007)"
	@echo ""
	@echo "マイグレーション"
	@echo "  migrate           alembic upgrade head"
	@echo "  migrate-create    マイグレーション生成 (例: make migrate-create MSG=\"add user table\")"
	@echo ""
	@echo "インフラ (OpenTofu)"
	@echo "  infra-fmt           tofu fmt -recursive infra"
	@echo "  infra-fmt-check     tofu fmt -check -recursive infra"
	@echo "  infra-validate-dev  dev 環境を validate"
	@echo "  infra-validate-stg  stg 環境を validate"
	@echo "  infra-validate-prod prod 環境を validate"
	@echo "  infra-validate      dev/stg/prod を順に validate"
	@echo ""
	@echo "クリーンアップ"
	@echo "  clean             docker-compose 停止 + キャッシュ削除"

# ------------------------------------------------------------------ #
# セットアップ
# ------------------------------------------------------------------ #

setup: install-hooks install-backend install-frontend

install-hooks:
	./scripts/setup-git-hooks.sh

install-backend:
	nix develop --command bash -c "cd backend && (.venv/bin/python --version > /dev/null 2>&1 || (rm -rf .venv && uv venv)) && uv pip install --python .venv/bin/python -r requirements.txt"

install-frontend:
	nix develop --command bash -c "cd frontend && npm ci"

generate-keys:
	nix develop --command bash -c "cd backend && python scripts/generate_keys.py"

# ------------------------------------------------------------------ #
# ローカル開発
# ------------------------------------------------------------------ #

dev:
	docker compose up

dev-build:
	docker compose up --build

dev-down:
	docker compose down

dev-frontend:
	nix develop --command bash -c "cd frontend && npm run dev"

preview-frontend:
	nix develop --command bash -c "cd frontend && CLOUD_RUN_URL='http://localhost:8000' npm run build && npx wrangler pages dev dist --port 8788"

dev-proxy:
	cd frontend && npm run dev:all

dev-proxy-only:
	cd frontend && npm run dev:proxy

# ------------------------------------------------------------------ #
# テスト・リント
# ------------------------------------------------------------------ #

ci: lint test build-frontend

test: test-backend test-frontend

test-backend:
	nix develop --command bash -c "cd backend && .venv/bin/python -m pytest -q tests"

test-frontend:
	nix develop --command bash -c "cd frontend && npm test"

lint: lint-backend lint-frontend lint-frontend-messages

lint-backend:
	nix develop --command bash -c "cd backend && .venv/bin/python -m ruff check app tests alembic_migrations"

lint-frontend:
	nix develop --command bash -c "cd frontend && npm run lint"

# ts/tsx で setError/toast.error/alert にリテラル日本語を直接渡していないか検知。
# ESLint は throw new Error の AST しか拾えないため、関数呼び出し系をここで補完する。
lint-frontend-messages:
	nix develop --command bash scripts/lint-frontend-messages.sh

lint-fix:
	nix develop --command bash -c "cd backend && .venv/bin/python -m ruff check --fix app tests alembic_migrations"
	cd frontend && npm run lint:fix

format:
	cd frontend && npm run format

format-check:
	cd frontend && npm run format:check

# ------------------------------------------------------------------ #
# コード重複検知 (jscpd)
# ------------------------------------------------------------------ #

# jscpd は npx 経由で実行する（devShell の nodejs_22 を利用）。
# 設定は .jscpd.json、出力は report/dupe/。Phase 1 は warn-only（threshold=0）。
dupe-check:
	nix develop --command bash -c "mkdir -p report/dupe && npx --yes jscpd@4 --config .jscpd.json"

dupe-check-html:
	nix develop --command bash -c "mkdir -p report/dupe && npx --yes jscpd@4 --config .jscpd.json"
	@echo "HTML レポート: report/dupe/html/index.html"

dupe-clean:
	rm -rf report/dupe

# ------------------------------------------------------------------ #
# ビルド
# ------------------------------------------------------------------ #

build-frontend:
	cd frontend && npm run build

build-backend:
	docker build ./backend -t devforge-api

deploy-frontend:
	nix develop --command bash -c "cd frontend && CLOUD_RUN_URL='$(CLOUD_RUN_URL)' npm run build && npm run deploy"

gen-redirects:
	nix develop --command bash -c "cd frontend && CLOUD_RUN_URL='$(CLOUD_RUN_URL)' node scripts/gen-redirects.mjs"

# ------------------------------------------------------------------ #
# OpenAPI 型コード生成 (ADR-0007)
# ------------------------------------------------------------------ #

# backend の FastAPI OpenAPI スキーマから frontend の型定義を生成する。
# export_openapi.py で backend/openapi.json を出力し、gen-types.mjs で
# frontend/src/api/generated.ts を再生成する。backend app の import に
# WeasyPrint 等のネイティブ依存解決が必要なため Nix devshell 経由で実行する。
codegen-types:
	nix develop --command bash -c "set -e; cd backend && .venv/bin/python scripts/export_openapi.py && cd ../frontend && node scripts/gen-types.mjs"

# ------------------------------------------------------------------ #
# マイグレーション
# ------------------------------------------------------------------ #

migrate:
	cd backend && .venv/bin/alembic upgrade head

migrate-create:
	@if [ -z "$(MSG)" ]; then echo "エラー: MSG を指定してください (例: make migrate-create MSG=\"add user table\")"; exit 1; fi
	cd backend && .venv/bin/alembic revision --autogenerate -m "$(MSG)"

# ------------------------------------------------------------------ #
# インフラ (OpenTofu)
# ------------------------------------------------------------------ #

infra-fmt:
	nix develop --command tofu fmt -recursive infra

infra-fmt-check:
	nix develop --command tofu fmt -check -recursive infra

infra-validate-dev:
	nix develop --command bash -c "tofu -chdir=infra/environments/dev init -backend=false -input=false && tofu -chdir=infra/environments/dev validate"

infra-validate-stg:
	nix develop --command bash -c "tofu -chdir=infra/environments/stg init -backend=false -input=false && tofu -chdir=infra/environments/stg validate"

infra-validate-prod:
	nix develop --command bash -c "tofu -chdir=infra/environments/prod init -backend=false -input=false && tofu -chdir=infra/environments/prod validate"

infra-validate: infra-validate-dev infra-validate-stg infra-validate-prod

# ------------------------------------------------------------------ #
# クリーンアップ
# ------------------------------------------------------------------ #

clean:
	docker-compose down
	rm -rf backend/.pytest_cache backend/.ruff_cache
	find . -type d -name __pycache__ -not -path "./.venv/*" -not -path "./frontend/node_modules/*" | xargs rm -rf
