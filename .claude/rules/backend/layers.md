---
paths:
  - backend/**
---

# Backend 層の境界ルール

`backend/architecture.md` が「何があるか」を示すのに対し、このファイルは「各層で何を書いてはいけないか」の禁止事項を補完する。
層責務に関する再発防止ルールはこのファイルが正本。新しい負債を発見したら本ファイルの Bad/Good 例を更新すること（`CLAUDE.md`「失敗から学んだ知見」の索引表からはここを指している）。

## 層ごとの責務と禁止事項

| 層 | 書いてよいこと | 書いてはいけないこと |
|---|---|---|
| `routers/` | エンドポイント定義・`Depends` による依存性解決・`raise_app_error` / `HTTPException` への変換・rate limit デコレータ | 外部 API 呼び出し・`db.query(...)` 直書き・ビジネスロジック・collector / fetcher の直接 import |
| `services/` | ビジネスロジック・外部 API 呼び出し・ドメイン例外の定義と raise・トランザクション管理 | `HTTPException`（HTTP 知識を service に持ち込まない）・プレゼンテーション整形 |
| `repositories/` | ORM クエリ・CRUD・`db.commit()` / `db.rollback()` | ビジネスロジック・外部 API 呼び出し・HTTP 知識 |
| `models/` | テーブル定義・リレーション・制約・DB レベルの型変換（`format_year_month` 等） | ソート・フォーマット等の表示ロジック・`sort_utils` のような presentation 層ユーティリティの import |

## 禁止パターンと修正例

### パターン A — router への外部 API 例外処理の漏れ

```python
# Bad: router が collector（外部 API クライアント）を直接 import し、外部 API 例外を自前で処理している
# routers/github_link.py
from ...services.intelligence.github.api_client import GitHubUserNotFoundError
from ...services.intelligence.github_collector import collect_repos

@router.post("/preview")
async def preview_repos(body: GitHubLinkRequest, ...):
    try:
        repos = await collect_repos(body.username)
    except GitHubUserNotFoundError as exc:
        raise HTTPException(status_code=404, ...) from exc
    except (RetryableError, NonRetryableError) as exc:
        raise HTTPException(status_code=502, ...) from exc
```

```python
# Good: service 層が外部 API 例外を吸収。router は raise_app_error への変換のみ
# services/intelligence/github_link_service.py
async def preview(self, username: str) -> GitHubLinkPreview:
    repos = await collect_repos(username)   # GitHubUserNotFoundError / Retryable 等を raise
    if not repos:
        raise GitHubLinkEmptyError(...)
    return self._to_preview(repos)

# routers/github_link.py
@router.post("/preview")
async def preview_repos(body: GitHubLinkRequest, ...):
    service = GitHubLinkService(db, user.id)
    try:
        return await service.preview(body.username)
    except GitHubUserNotFoundError as exc:
        raise_app_error(ErrorCode.NOT_FOUND, ...) from exc
    except GitHubLinkEmptyError as exc:
        raise_app_error(ErrorCode.EXTERNAL_API_ERROR, ...) from exc
```

### パターン B — router 内への DB クエリ直書き

```python
# Bad: router のモジュールレベル関数が db.query を直接実行している
# routers/github_link.py
def _get_or_create_cache(db: Session, user_id: str) -> GitHubLinkCache:
    cache = db.query(GitHubLinkCache).filter_by(user_id=user_id).first()
    if not cache:
        cache = GitHubLinkCache(user_id=user_id)
        db.add(cache)
        db.flush()
    return cache
```

```python
# Good: repository 層に移設。router からは service 経由で呼ぶ
# repositories/github_link.py
class GitHubLinkCacheRepository:
    def get_or_create(self, user_id: str) -> GitHubLinkCache:
        cache = self.db.query(GitHubLinkCache).filter_by(user_id=user_id).first()
        if not cache:
            cache = GitHubLinkCache(user_id=user_id)
            self.db.add(cache)
            self.db.flush()
        # IntegrityError 後の再 SELECT が None を返す場合は RuntimeError を上げる
        # （詳細: .claude/rules/backend/database.md）
        return cache
```

### パターン C — ORM model への表示ロジック混入

```python
# Bad: model が sort_utils を import し @property でソート済みリストを返す
# models/resume.py
from ..services.shared.sort_utils import sort_by_period_desc

class Resume(Base):
    @property
    def experiences(self) -> list["ResumeExperience"]:
        return sort_by_period_desc(list(self.experience_rows))
```

```python
# Good 案1: relationship に order_by を指定（DB レベルで解決できる場合）
# models/resume.py
experience_rows: Mapped[list["ResumeExperience"]] = relationship(
    back_populates="resume",
    cascade="all, delete-orphan",
    order_by="ResumeExperience.start_date.desc()",
)

# Good 案2: service 層でソート（動的な条件が必要な場合）
# services/shared/resume_format.py（既存）で sort_by_period_desc を呼ぶ
```

## 例外変換の責務ルール

- 外部 API 固有例外（`GitHubUserNotFoundError` 等）は発生するモジュール（collector / api_client 等）内で定義し、service が raise する
- router では `raise_app_error(...)` か `HTTPException` への変換のみ行う
- service 層は `HTTPException` を import しない。HTTP ステータスコードを service に持ち込まない
- ドメイン例外クラスの定義場所: 例外を raise するモジュールと同じファイルに置く
