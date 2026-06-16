import os
from urllib.parse import urlparse

from . import env_keys

# --- Turso (libSQL) ---


def get_turso_database_url() -> str:
    """Turso / libSQL データベースの接続 URL を取得する。

    対応する形式:
      - `http://127.0.0.1:8080` / `https://...` : turso dev・libSQL HTTP サーバー
      - `libsql://<db>.turso.io` : Turso Cloud
      - `file:./local.sqlite` または絶対パス : ローカルファイル（テスト用途）
    """
    return os.getenv(env_keys.TURSO_DATABASE_URL, "").strip()


def get_turso_auth_token() -> str:
    """Turso 認証トークン（Cloud 用）。turso dev では空でよい。"""
    return os.getenv(env_keys.TURSO_AUTH_TOKEN, "").strip()


def build_sqlalchemy_database_url() -> str:
    """SQLAlchemy 用のデータベース接続 URL を `TURSO_DATABASE_URL` から組み立てる。

    - HTTP / HTTPS / libsql スキーム: `sqlite+libsql://` 形式に変換し Turso (libSQL) に接続
    - ローカルファイルパス: `sqlite:///` （標準 SQLite ドライバ）を使用
        libsql-experimental のローカルファイルドライバは複雑な DDL/DML (例: 0010 マイグレーション)
        で `database table is locked` を返すため、ローカル/テスト用途では標準 sqlite を使う
    - `TURSO_DATABASE_URL` 未設定時は RuntimeError を送出する
    """
    raw = get_turso_database_url()
    if not raw:
        raise RuntimeError(
            "TURSO_DATABASE_URL が設定されていません。"
            "turso dev または Turso Cloud の接続 URL を設定してください。"
        )

    parsed = urlparse(raw)
    token = get_turso_auth_token()

    if parsed.scheme in {"http", "https", "libsql"}:
        # ホスト+ポート形式（HTTP/HTTPS サーバー or Turso Cloud）→ libSQL ドライバ
        netloc = parsed.netloc
        path = parsed.path or ""
        url = f"sqlite+libsql://{netloc}{path}"
        if token:
            url = f"{url}?authToken={token}"
        return url

    if parsed.scheme in {"", "file"}:
        # ローカルファイル形式（テスト用途）→ 標準 SQLite ドライバ
        # path が "/abs" の場合 f"sqlite:///{path}" は自動で "sqlite:////abs" になる
        path = parsed.path if parsed.scheme == "file" else raw
        return f"sqlite:///{path}"

    raise RuntimeError(f"TURSO_DATABASE_URL のスキームを解釈できません: {raw}")


def _parse_bool_env(name: str) -> bool | None:
    value = os.getenv(name)
    if value is None:
        return None

    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise RuntimeError(f"{name} must be a boolean value")


def _is_loopback_origin(origin: str) -> bool:
    parsed = urlparse(origin)
    return parsed.scheme == "http" and parsed.hostname in {"localhost", "127.0.0.1"}


def get_cors_origins() -> list[str]:
    cors_origins = os.getenv(env_keys.CORS_ORIGINS, "")
    return [origin.strip() for origin in cors_origins.split(",") if origin.strip()]


def get_cookie_secure() -> bool:
    configured = _parse_bool_env(env_keys.COOKIE_SECURE)
    if configured is not None:
        return configured

    origins = get_cors_origins()
    if origins and all(_is_loopback_origin(origin) for origin in origins):
        return False
    return True


def get_cookie_samesite() -> str:
    default = "lax"
    origins = get_cors_origins()
    if origins and not all(_is_loopback_origin(origin) for origin in origins):
        default = "none"

    value = os.getenv(env_keys.COOKIE_SAMESITE, default).strip().lower()
    if value not in {"lax", "strict", "none"}:
        raise RuntimeError("COOKIE_SAMESITE must be one of: lax, strict, none")
    return value


def get_admin_token() -> str:
    return os.getenv(env_keys.ADMIN_TOKEN, "").strip()


def get_jwt_private_key() -> str:
    """RS256署名用秘密鍵（PEM形式）を取得する。"""
    key = os.getenv(env_keys.JWT_PRIVATE_KEY, "").replace("\\n", "\n").strip()
    if not key:
        raise RuntimeError("JWT_PRIVATE_KEY is not configured")
    return key


def get_jwt_public_key() -> str:
    """RS256検証用公開鍵（PEM形式）を取得する。"""
    key = os.getenv(env_keys.JWT_PUBLIC_KEY, "").replace("\\n", "\n").strip()
    if not key:
        raise RuntimeError("JWT_PUBLIC_KEY is not configured")
    return key


def get_callback_base_url() -> str:
    """OAuth callback の base URL を取得する。環境変数が設定されていれば優先する。

    Cloudflare Pages → Cloud Run 構成では x-forwarded-host が正しく伝播しない場合があるため、
    CALLBACK_BASE_URL に Cloudflare Pages の URL（例: https://app.devforge.app）を明示することで
    redirect_uri を固定できる。空の場合は呼び出し元が build_external_base_url にフォールバックする。
    """
    url = os.getenv(env_keys.CALLBACK_BASE_URL, "").strip()
    return url.rstrip("/") if url else ""


def get_github_client_id() -> str:
    return os.getenv(env_keys.GITHUB_CLIENT_ID, "").strip()


def get_github_client_secret() -> str:
    return os.getenv(env_keys.GITHUB_CLIENT_SECRET, "").strip()


def get_app_version() -> str:
    """アプリケーションバージョンを取得する（Git タグから CI で注入）。"""
    return os.getenv(env_keys.APP_VERSION, "dev").strip()


def get_environment() -> str:
    """実行環境を取得する（local / dev / stg / prod）。"""
    return os.getenv(env_keys.ENVIRONMENT, "local").strip()


def get_internal_secret() -> str:
    """Cloudflare Pages → Cloud Run 間の秘密ヘッダー値を取得する。

    local 環境以外では必須。未設定の場合は起動時に RuntimeError を送出する。
    値はログや例外メッセージに含めないこと。
    """
    env = get_environment()
    secret = os.getenv(env_keys.INTERNAL_SECRET, "").strip()
    if env != "local" and not secret:
        raise RuntimeError(
            "INTERNAL_SECRET が設定されていません。"
            "Secret Manager で internal-secret を登録し、Cloud Run 環境変数に追加してください。"
        )
    return secret


def get_llm_provider() -> str:
    """Agent 機能の LLM プロバイダ名（anthropic / ollama）を小文字で取得する。

    未設定時はローカル開発向けに ollama を既定とする（ADR-0010）。
    """
    return os.getenv(env_keys.LLM_PROVIDER, "ollama").strip().lower()


def get_anthropic_api_key() -> str:
    """Anthropic API キーを取得する。値はログや例外メッセージに含めないこと。"""
    return os.getenv(env_keys.ANTHROPIC_API_KEY, "").strip()


def get_ollama_base_url() -> str:
    """ローカル Ollama のベース URL を取得する。"""
    return os.getenv(env_keys.OLLAMA_BASE_URL, "http://localhost:11434").strip()


def get_ollama_model() -> str:
    """ローカル Ollama で使用するモデル名を取得する。"""
    return os.getenv(env_keys.OLLAMA_MODEL, "llama3.2").strip()


def get_stripe_secret_key() -> str:
    """Stripe シークレットキー（sk_...）を取得する。値はログや例外メッセージに含めないこと。"""
    return os.getenv(env_keys.STRIPE_SECRET_KEY, "").strip()


def get_stripe_webhook_secret() -> str:
    """Stripe Webhook 署名シークレット（whsec_...）を取得する。値はログに含めないこと。"""
    return os.getenv(env_keys.STRIPE_WEBHOOK_SECRET, "").strip()


def get_billing_return_base_url() -> str:
    """Stripe Checkout の success/cancel リダイレクト先のベース URL を返す。

    フロントエンド（Cloudflare Pages）の URL を指す。OAuth と同じ ``CALLBACK_BASE_URL``
    を優先し、未設定ならローカル開発向けに CORS の先頭オリジンへフォールバックする。
    """
    base = get_callback_base_url()
    if base:
        return base
    origins = get_cors_origins()
    return origins[0].rstrip("/") if origins else ""


def get_log_format() -> str:
    """ログフォーマット指定（json / text / 空）を小文字で取得する。"""
    return os.getenv(env_keys.LOG_FORMAT, "").strip().lower()


def get_log_level() -> str:
    """ログレベル名（DEBUG / INFO / WARNING / ERROR / CRITICAL）を大文字で取得する。"""
    return os.getenv(env_keys.LOG_LEVEL, "INFO").strip().upper()
