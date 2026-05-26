from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.pool import NullPool

from ..core.settings import build_sqlalchemy_database_url

# Turso (libSQL) 接続 URL を構築する。`TURSO_DATABASE_URL` を `sqlite+libsql://` 形式に変換する
_db_url = build_sqlalchemy_database_url()

# libSQL は HTTP/HTTPS 経由のため SQLAlchemy のコネクションプールは保持せず NullPool を使う
# `check_same_thread` は SQLite ドライバ固有の引数で libSQL では不要
engine = create_engine(
    _db_url,
    poolclass=NullPool,
    pool_pre_ping=True,
)

# libsql_experimental は PEP 249 の `Binary` を未提供のため、SQLAlchemy の LargeBinary
# bind_processor が `dialect.dbapi.Binary` を参照した時点で AttributeError になる。
# 標準 DBAPI の `Binary` は単に bytes を生成するコンストラクタなので bytes でシムする。
if engine.dialect.driver == "libsql" and not hasattr(engine.dialect.dbapi, "Binary"):
    setattr(engine.dialect.dbapi, "Binary", bytes)


# expire_on_commit=False: commit 後の attribute 自動 expire を抑止する。
# libSQL (Hrana over HTTP) は idle stream が timeout すると後続 commit が
# `STREAM_EXPIRED` で 400 を返す。SQLAlchemy デフォルトの expire_on_commit=True だと
# 1 回目の commit 後に attribute が expire され、2 回目の commit 時に
# `_collect_update_commands` 内の history 比較で expired attribute を reload する
# SELECT が走り、その SELECT が失効した stream に当たって落ちる。
# バックグラウンドタスクは commit 後の fresh データ参照を必要としないため安全に無効化できる。
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
    bind=engine,
)
Base = declarative_base()


def get_db() -> Generator:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
