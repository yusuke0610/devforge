"""libsql_experimental が `Binary` 属性を持たない問題に対するシム検証。

`app.db.database` が libsql ドライバの engine を構築した際、
SQLAlchemy の LargeBinary 型が bind_processor を組み立てる時に参照する
`dialect.dbapi.Binary` を bytes でシムしていることを確認する。
"""

import importlib

import pytest
from sqlalchemy import LargeBinary, create_engine
from sqlalchemy.pool import NullPool


@pytest.fixture()
def libsql_engine(monkeypatch):
    """libsql ドライバを使う engine を準備する（HTTP 接続はしない）。"""
    monkeypatch.setenv("TURSO_DATABASE_URL", "http://127.0.0.1:8080")
    # database モジュールを再ロードして engine をシム適用済み状態で得る
    from app.db import database

    importlib.reload(database)
    return database.engine


def test_libsql_dialect_has_binary_shim(libsql_engine):
    """libsql ドライバに Binary シムが当たっていること。"""
    assert libsql_engine.dialect.driver == "libsql"
    assert libsql_engine.dialect.dbapi.Binary is bytes


def test_large_binary_bind_processor_passes_bytes_through(libsql_engine):
    """LargeBinary.bind_processor が bytes を非破壊で通すこと。"""
    proc = LargeBinary().bind_processor(libsql_engine.dialect)
    assert proc is not None
    payload = b"%PDF-1.3\n%fake-binary"
    assert proc(payload) == payload


def test_standard_sqlite_dialect_unaffected():
    """通常の pysqlite ドライバには影響しない（Binary は元から存在する）。"""
    engine = create_engine("sqlite:///:memory:", poolclass=NullPool)
    assert engine.dialect.driver == "pysqlite"
    # pysqlite は標準で Binary を提供する
    dbapi = engine.dialect.dbapi
    assert dbapi is not None
    assert callable(dbapi.Binary)
