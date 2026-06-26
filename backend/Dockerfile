# ============================================================================
# Build stage: libsql-experimental など Rust ビルドが必要な wheel を作成する
# ============================================================================
FROM python:3.13-slim@sha256:2b7445fb71ca9cb15e9aab053fe8cb3162796f8e1d92ada12a49c766a811bc1e AS builder

WORKDIR /build

# Rust + C リンカ + cmake + tcl が必要なのは libsql-experimental
# (aarch64-linux + cp313 の wheel が PyPI に無いためソースから build される)
# - build-essential: gcc / cc (Rust の linker)
# - cmake: libsql-ffi が同梱する sqlite3mc (SQLite3MultipleCiphers) のビルドに必要
# - tcl: SQLite 系のビルドスクリプトが要求するケースあり
# - curl: puccinialin が rustup を取得する際に使う
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    cmake \
    tcl \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./

# wheel を /build/wheels に集約しておき、final stage で再利用する
RUN pip wheel --no-cache-dir --wheel-dir=/build/wheels -r requirements.txt


# ============================================================================
# Final stage: 実行に必要なシステムライブラリと wheel のみを含む軽量イメージ
# ============================================================================
FROM python:3.13-slim@sha256:2b7445fb71ca9cb15e9aab053fe8cb3162796f8e1d92ada12a49c766a811bc1e

ARG APP_VERSION=dev
ENV APP_VERSION=$APP_VERSION

# Turso (libSQL) 接続設定
# TURSO_AUTH_TOKEN は機微情報のため Dockerfile では宣言せず、実行時に
# docker-compose の environment / Cloud Run の Secret Manager から注入する
ENV TURSO_DATABASE_URL=""

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    libpango-1.0-0 libpangoft2-1.0-0 libpangocairo-1.0-0 \
    libglib2.0-0 libgobject-2.0-0 libffi-dev libcairo2 \
    && rm -rf /var/lib/apt/lists/*

# builder stage でビルドした wheel を流用して高速・確実に install する
COPY --from=builder /build/wheels /wheels
COPY requirements.txt ./
RUN pip install --no-cache-dir --no-index --find-links=/wheels -r requirements.txt \
    && rm -rf /wheels

COPY alembic.ini ./
COPY alembic_migrations ./alembic_migrations
COPY app ./app
COPY scripts ./scripts

RUN chmod +x ./scripts/entrypoint.sh

EXPOSE 8000

CMD ["./scripts/entrypoint.sh"]
