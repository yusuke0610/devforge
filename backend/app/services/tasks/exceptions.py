"""バックグラウンドタスクのリトライ用例外。

タスク内で発生した外部サービス例外（httpx / GitHub API / DB 等）を、
- ``RetryableError`` : 一時的な障害（タイムアウト / 5xx / レート制限）
- ``NonRetryableError`` : 恒久的な障害（バリデーション / 401/403/404）
の二種類に分類して raise し直すための例外クラスを提供する。

未分類の例外は呼び出し側で保守的に ``NonRetryableError`` 相当として扱うこと
（無限リトライの防止）。
"""


class RetryableError(Exception):
    """一時的な障害を表す例外。再エンキュー対象。

    HTTP 429 を受け取った場合は ``retry_after`` に ``Retry-After`` ヘッダの値を
    秒単位で渡すこと。通常のバックオフ計算より優先される。
    """

    def __init__(self, message: str, retry_after: float | None = None) -> None:
        super().__init__(message)
        self.retry_after = retry_after


class NonRetryableError(Exception):
    """恒久的な障害を表す例外。即座に ``dead_letter`` 状態へ遷移させる。"""
