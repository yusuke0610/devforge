# ============================================================================
# 本番イメージ（ADR-0021 Phase 3: Nix build 化）
#
# build context は「リポジトリルート」であること（flake.nix を参照するため）:
#   docker build -f backend/Dockerfile .
# （docker-compose.yml / deploy.yml / smoke-backend はこの前提で呼び出す）
#
# 依存の SSoT は backend/pyproject.toml + uv.lock（Phase 0）。devshell（flake.nix の
# uv2nix build）と同じ backend-runtime 環境をイメージ内で nix build し、
# dev / CI / 本番の 3 経路のビルド機構を flake に一元化する。
# ============================================================================

# ============================================================================
# Build stage: uv2nix で Python 依存 + WeasyPrint ライブラリの closure を構成する
# ============================================================================
FROM nixos/nix:2.35.1@sha256:377d4887aca98f0dfa12971c1ea6d6a625a435d8b610d4c95a436843da6fbfd1 AS builder

WORKDIR /build

# flake と lock 一式のみコピーする（app コードの変更で Nix build レイヤの
# docker cache が無効化されないよう、コード COPY は final stage 側で行う）
COPY flake.nix flake.lock ./
COPY backend/pyproject.toml backend/uv.lock ./backend/

# --option sandbox false: コンテナ内では Nix サンドボックス（user namespace）を
# 作れないため無効化する。wheel の取得は fixed-output derivation（ハッシュ検証付き）
# なので再現性は lock で担保される。aarch64-linux のみ libsql-experimental が
# sdist（Rust）ビルドとなり crates.io へのネットワーク取得を伴う
# （従来の pip wheel ビルドと同等の妥協。本番 = amd64 は wheel のみで純粋）。
RUN nix --extra-experimental-features "nix-command flakes" \
        build --option sandbox false .#backend-runtime -o /build/runtime

# ランタイム closure を /out に集約し、実体へのパスを控える（final stage へのコピー用）
RUN mkdir -p /out/nix/store \
    && cp -a $(nix --extra-experimental-features "nix-command flakes" path-info -r /build/runtime) /out/nix/store/ \
    && readlink /build/runtime > /out/runtime-path


# ============================================================================
# Final stage: ランタイム closure とアプリコードのみを含む軽量イメージ
# ============================================================================
FROM debian:12-slim@sha256:7b140f374b289a7c2befc338f42ebe6441b7ea838a042bbd5acbfca6ec875818

ARG APP_VERSION=dev
ENV APP_VERSION=$APP_VERSION

# Turso (libSQL) 接続設定
# TURSO_AUTH_TOKEN は機微情報のため Dockerfile では宣言せず、実行時に
# docker-compose の environment / Cloud Run の Secret Manager から注入する
ENV TURSO_DATABASE_URL=""

WORKDIR /app

# Nix build 済みのランタイム closure（python / uvicorn / alembic / WeasyPrint ライブラリ）。
# /runtime は store パスへの symlink で、ENV から固定パスで参照できるようにする
COPY --from=builder /out/nix/store /nix/store
COPY --from=builder /out/runtime-path /tmp/runtime-path
RUN ln -s "$(cat /tmp/runtime-path)" /runtime && rm /tmp/runtime-path

ENV PATH="/runtime/bin:$PATH"
# WeasyPrint が共有ライブラリを発見できるよう動的リンカーのパスを設定（devshell と同じ構成）
ENV LD_LIBRARY_PATH="/runtime/lib"
# libsql ドライバ（rustls）と curl が CA 証明書を発見できるようにする
# （debian:12-slim は ca-certificates 非同梱。バンドルは flake の cacert 由来）
ENV SSL_CERT_FILE="/runtime/etc/ssl/certs/ca-bundle.crt"

COPY backend/alembic.ini ./
COPY backend/alembic_migrations ./alembic_migrations
COPY backend/app ./app
COPY backend/scripts ./scripts

RUN chmod +x ./scripts/entrypoint.sh

EXPOSE 8000

CMD ["./scripts/entrypoint.sh"]
