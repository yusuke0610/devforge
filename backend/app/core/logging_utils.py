"""構造化ログユーティリティ。

Cloud Run 上では標準出力に JSON を書くだけで Cloud Logging が収集する。
severity フィールドにより Cloud Logging のログレベルとして自動認識される。

**機密情報保護**: ログに氏名・住所・電話番号・メールアドレス・
トークン・Cookie・暗号化前の平文データを絶対に含めないこと。

**extra dict 標準キー（これ以外のキーは使用禁止）:**
  request_id  : str  - リクエスト ID（RequestIDMiddleware がセット）
  user_id     : str  - GitHub OAuth ユーザー ID
  task_id     : str  - 非同期タスク ID
  record_id   : int  - DB レコード ID
  status      : str  - "running" | "completed" | "failed"
  duration_ms : int  - 処理時間（ミリ秒）
  operation   : str  - 計測対象の操作名（metrics.py が付与）
  platform    : str  - "qiita" | "zenn" | "note" 等
  error_type  : str  - 例外クラス名
  http_status : int  - HTTP ステータスコード
  error_id    : str  - エラー追跡 ID
  client_ip   : str  - リクエスト元 IP（不正アクセス追跡用）
  path        : str  - リクエストパス（追跡用）
  method      : str  - HTTP メソッド（追跡用）
  reason      : str  - 失敗理由の機械可読コード（auth_failed 等の細分化）
"""

import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any

from .context import (
    client_ip_var,
    request_id_var,
    request_method_var,
    request_path_var,
)
from .settings import get_environment, get_log_format, get_log_level

_STRUCTURED_KEYS = frozenset(
    {
        "request_id",
        "task_id",
        "user_id",
        "record_id",
        "status",
        "duration_ms",
        "operation",
        "platform",
        "model",
        "error_type",
        "http_status",
        "error_id",
        "client_ip",
        "path",
        "method",
        "reason",
    }
)

# ContextVar から自動注入するキーと対応する変数のマッピング
_CONTEXT_VAR_KEYS = (
    ("request_id", request_id_var),
    ("client_ip", client_ip_var),
    ("path", request_path_var),
    ("method", request_method_var),
)

_SEVERITY_MAP = {
    logging.DEBUG: "DEBUG",
    logging.INFO: "INFO",
    logging.WARNING: "WARNING",
    logging.ERROR: "ERROR",
    logging.CRITICAL: "CRITICAL",
}


class CloudLoggingFormatter(logging.Formatter):
    """Cloud Logging が severity として認識する JSON フォーマッター。

    request_id は ContextVar から自動付与されるため、呼び出し側で
    extra={"request_id": ...} を明示しなくてよい。
    """

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "severity": _SEVERITY_MAP.get(record.levelno, "DEFAULT"),
            "message": record.getMessage(),
            "logger": record.name,
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z",
        }

        context_keys = {key for key, _ in _CONTEXT_VAR_KEYS}
        for key in _STRUCTURED_KEYS - context_keys:
            value = getattr(record, key, None)
            if value is not None:
                payload[key] = value

        # ContextVar 由来のキー: record の明示設定があればそれを優先、なければ ContextVar から自動注入
        for key, ctx_var in _CONTEXT_VAR_KEYS:
            value = getattr(record, key, None) or ctx_var.get("")
            if value:
                payload[key] = value

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(payload, ensure_ascii=False)


def get_logger(name: str) -> logging.Logger:
    """統一インターフェースでロガーを取得する。

    各モジュールで ``logging.getLogger(__name__)`` の代わりに使用すること。
    返されるロガーはルートロガーの設定（JSON フォーマット等）を継承する。
    """
    return logging.getLogger(name)


def setup_logging() -> None:
    """ルートロガーを構成する。

    判定順:
      1. LOG_FORMAT=json  → JSON（Cloud Run 本番）
      2. LOG_FORMAT=text  → テキスト（明示指定）
      3. ENVIRONMENT が dev/stg/prod → JSON（後方互換）
      4. それ以外 → テキスト（ローカル開発）
    """
    root = logging.getLogger()
    # 多重追加を防止
    if root.handlers:
        return

    handler = logging.StreamHandler(sys.stdout)
    log_format = get_log_format()
    env = get_environment()

    use_json = log_format == "json" or (log_format != "text" and env in ("dev", "stg", "prod"))
    if use_json:
        handler.setFormatter(CloudLoggingFormatter())

    log_level = getattr(logging, get_log_level(), logging.INFO)
    root.setLevel(log_level)
    root.addHandler(handler)


def log_event(level: int, event: str, **fields: Any) -> None:
    """構造化フィールド付きのイベントログを出力する。"""
    logger = logging.getLogger("devforge")
    logger.log(level, event, extra={k: v for k, v in fields.items() if k in _STRUCTURED_KEYS})
