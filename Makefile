.PHONY: help \
	setup install-hooks install-backend install-web generate-keys \
	dev dev-build dev-down dev-amd64 dev-amd64-build dev-web preview-web dev-proxy dev-proxy-only stripe-webhook \
	test test-backend test-web \
	lint lint-backend lint-web lint-web-messages lint-env-keys lint-fix \
	format format-check \
	ci \
	dupe-check dupe-check-html dupe-clean \
	build-web build-backend deploy-web \
	gen-redirects codegen-types licenses \
	migrate migrate-create \
	infra-fmt infra-fmt-check infra-validate-dev infra-validate-stg infra-validate-prod infra-validate \
	clean

# デフォルトターゲット: ヘルプ表示
help:
	@echo "Usage: make <target>"
	@echo ""
	@echo "セットアップ"
	@echo "  setup             初回セットアップ (hooks + backend + web)"
	@echo "  install-hooks     git hooks を設定"
	@echo "  install-backend   Backend 依存パッケージをインストール"
	@echo "  install-web  Frontend 依存パッケージをインストール"
	@echo "  generate-keys     JWT RSA 鍵ペアを生成"
	@echo ""
	@echo "ローカル開発"
	@echo "  dev               docker-compose で API を起動"
	@echo "  dev-build         再ビルドして起動"
	@echo "  dev-down          docker-compose を停止"
	@echo "  dev-amd64         本番と同じ amd64 で API を起動 (native 不具合の再現用 / Mac では低速)"
	@echo "  dev-amd64-build   amd64 で再ビルドして起動"
	@echo "  dev-web      Frontend 開発サーバーを起動 (Vite / localhost:5173)"
	@echo "  preview-web  ビルド済みを wrangler でローカル提供 (HMR なし / localhost:8788)"
	@echo "  stripe-webhook    Stripe Webhook を localhost:8000 へ転送 (要 stripe login / whsec を .env へ)"
	@echo ""
	@echo "テスト・リント"
	@echo "  ci                lint + test + build-web を一括実行 (CI 相当)"
	@echo "  test              全テスト (backend + web)"
	@echo "  test-backend      Backend: pytest"
	@echo "  test-web     Frontend: vitest"
	@echo "  lint              全リント (backend + web)"
	@echo "  lint-backend      Backend: ruff check"
	@echo "  lint-web     Frontend: eslint"
	@echo "  lint-web-messages  Frontend: setError等にリテラル日本語が渡っていないか検知"
	@echo "  lint-env-keys     env名/エラーコードの SSoT drift を検知 (env_keys.py↔compose, errors.py↔errorCodes.ts)"
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
	@echo "  build-web    Vite ビルド"
	@echo "  build-backend     Docker イメージビルド"
	@echo "  deploy-web   Cloudflare Pages へビルド＆デプロイ (CLOUD_RUN_URL=... 指定可)"
	@echo "  gen-redirects     Cloudflare Pages 用 _redirects を生成 (CLOUD_RUN_URL=... 指定可)"
	@echo "  codegen-types     OpenAPI から web 型 (src/api/generated.ts) を再生成 (ADR-0007)"
	@echo "  licenses          使用 OSS の一覧 (THIRD_PARTY_LICENSES.md) を再生成"
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

setup: install-hooks install-backend install-web

install-hooks:
	./scripts/setup-git-hooks.sh

install-backend:
	nix develop --command bash -c "cd backend && (.venv/bin/python --version > /dev/null 2>&1 || (rm -rf .venv && uv venv)) && uv pip install --python .venv/bin/python -r requirements.txt"

install-web:
	nix develop --command bash -c "cd web && npm ci"

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

dev-amd64:
	docker compose -f docker-compose.yml -f docker-compose.amd64.yml up

dev-amd64-build:
	docker compose -f docker-compose.yml -f docker-compose.amd64.yml up --build

stripe-webhook:
	nix develop --command stripe listen --forward-to localhost:8000/api/billing/webhook

dev-web:
	nix develop --command bash -c "cd web && npm run dev"

preview-web:
	nix develop --command bash -c "cd web && CLOUD_RUN_URL='http://localhost:8000' npm run build && npx wrangler pages dev dist --port 8788"

dev-proxy:
	cd web && npm run dev:all

dev-proxy-only:
	cd web && npm run dev:proxy

# ------------------------------------------------------------------ #
# テスト・リント
# ------------------------------------------------------------------ #

ci: lint test build-web

test: test-backend test-web

test-backend:
	nix develop --command bash -c "cd backend && .venv/bin/python -m pytest -q tests"

test-web:
	nix develop --command bash -c "cd web && npm test"

lint: lint-backend lint-web lint-web-messages lint-env-keys

lint-backend:
	nix develop --command bash -c "cd backend && .venv/bin/python -m ruff check app tests alembic_migrations"

lint-web:
	nix develop --command bash -c "cd web && npm run lint"

# ts/tsx で setError/toast.error/alert にリテラル日本語を直接渡していないか検知。
# ESLint は throw new Error の AST しか拾えないため、関数呼び出し系をここで補完する。
lint-web-messages:
	nix develop --command bash scripts/lint-web-messages.sh

# env 名 / エラーコードの SSoT drift を検知。
# env_keys.py↔docker-compose.yml、errors.py↔errorCodes.ts の集合一致を検証する。
# grep/sed/comm のみに依存（ripgrep 不要）。他 lint と揃えて nix wrap で実行する。
lint-env-keys:
	nix develop --command bash scripts/lint-env-keys.sh

lint-fix:
	nix develop --command bash -c "cd backend && .venv/bin/python -m ruff check --fix app tests alembic_migrations"
	cd web && npm run lint:fix

format:
	cd web && npm run format

format-check:
	cd web && npm run format:check

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

build-web:
	cd web && npm run build

build-backend:
	docker build ./backend -t devforge-api

deploy-web:
	nix develop --command bash -c "cd web && CLOUD_RUN_URL='$(CLOUD_RUN_URL)' npm run build && npm run deploy"

gen-redirects:
	nix develop --command bash -c "cd web && CLOUD_RUN_URL='$(CLOUD_RUN_URL)' node scripts/gen-redirects.mjs"

# ------------------------------------------------------------------ #
# OpenAPI 型コード生成 (ADR-0007)
# ------------------------------------------------------------------ #

# backend の FastAPI OpenAPI スキーマから web の型定義を生成する。
# export_openapi.py で backend/openapi.json を出力し、gen-types.mjs で
# web/src/api/generated.ts を再生成する。backend app の import に
# WeasyPrint 等のネイティブ依存解決が必要なため Nix devshell 経由で実行する。
codegen-types:
	nix develop --command bash -c "set -e; cd backend && .venv/bin/python scripts/export_openapi.py && cd ../web && node scripts/gen-types.mjs"

# ------------------------------------------------------------------ #
# 使用 OSS ライセンス一覧
# ------------------------------------------------------------------ #

# 直接依存 OSS の一覧と各ライセンスを web/package.json・backend/requirements.txt
# から収集し THIRD_PARTY_LICENSES.md を再生成する。importlib.metadata を使うため
# backend の依存がインストール済みの Nix devshell 経由で実行する。
licenses:
	nix develop --command bash -c "backend/.venv/bin/python scripts/gen-third-party-licenses.py"

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
	find . -type d -name __pycache__ -not -path "./.venv/*" -not -path "./web/node_modules/*" | xargs rm -rf
