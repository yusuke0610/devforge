"""クレジット課金（ADR-0012）の統合テスト。

LLM（外部 API）のみモックし、残高チェック・消費・台帳記録・使用ログは
実 DB（テスト用 SQLite セッション）を通す。
"""

from typing import get_args

import pytest
from app.models import AgentUsageLog
from app.repositories import BillingRepository, UserRepository
from app.schemas.agent import AgentModelAlias
from app.services.agent import chat_service
from app.services.agent.chat_service import AgentUsage
from app.services.agent.model_catalog import (
    MARGIN_MULTIPLIER,
    MODEL_CATALOG,
    YEN_PER_CREDIT,
    YEN_PER_USD,
    baseline_credits_per_chat,
    calculate_credit_cost,
)
from app.services.billing import credit_service
from fastapi.testclient import TestClient

from conftest import auth_header
from test_agent import _FakeLLM, _llm_json, _resume_payload, _SequentialFakeLLM

_ADMIN_HEADERS = {"Authorization": "Bearer test-admin-token"}


def _chat_payload(model: str | None = None) -> dict:
    """self_pr スコープの最小チャットペイロードを返す。"""
    payload = {
        "scope": "self_pr",
        "prompt": "もっと魅力的にしてください",
        "resume": _resume_payload(),
    }
    if model is not None:
        payload["model"] = model
    return payload


def _get_user_id(client: TestClient, username: str) -> str:
    """auth_header で作成済みのユーザー ID を返す。"""
    user = UserRepository(client._db_session).get_by_username(username)
    assert user is not None
    return user.id


# --- ユニットテスト（model_catalog: エイリアス・課金レート） ---


def test_model_catalog_matches_schema_alias() -> None:
    """MODEL_CATALOG のキー集合はスキーマの AgentModelAlias と一致する（drift 防止）。"""
    assert set(MODEL_CATALOG) == set(get_args(AgentModelAlias))


def test_model_catalog_resolves_real_model_ids() -> None:
    """エイリアスから実モデル ID と無料/有料フラグが解決できる。"""
    assert MODEL_CATALOG["haiku"].model_id == "claude-haiku-4-5"
    assert MODEL_CATALOG["haiku"].is_free is True
    assert MODEL_CATALOG["sonnet"].model_id == "claude-sonnet-4-6"
    assert MODEL_CATALOG["sonnet"].is_free is False


def test_credit_rates_are_yen_pegged_with_margin() -> None:
    """消費レートは API 原価（USD/MTok）を円換算しマージンを乗せて算出される（1cr=¥1 / ADR-0012）。"""
    sonnet = MODEL_CATALOG["sonnet"]
    assert sonnet.input_credits_per_mtok == round(3.0 * YEN_PER_USD * MARGIN_MULTIPLIER / YEN_PER_CREDIT)
    assert sonnet.output_credits_per_mtok == round(15.0 * YEN_PER_USD * MARGIN_MULTIPLIER / YEN_PER_CREDIT)
    # 1 クレジット = ¥1 なので Sonnet 入力は 675 クレジット/MTok（= $3 × ¥150 × 1.5）
    assert sonnet.input_credits_per_mtok == 675
    assert sonnet.output_credits_per_mtok == 3375


def test_calculate_credit_cost_free_model_is_zero() -> None:
    """無料モデル（haiku）はトークン数に関わらずコスト 0。"""
    assert calculate_credit_cost("haiku", 100_000, 100_000) == 0


def test_calculate_credit_cost_sonnet_exact() -> None:
    """sonnet のコストは入出力レートの合算（クレジット/MTok）から算出される。"""
    # input 1000 tok × 675/MTok = 0.675 / output 1000 tok × 3375/MTok = 3.375 → 計 4.05 → ceil 5
    assert calculate_credit_cost("sonnet", 1000, 1000) == 5


def test_calculate_credit_cost_rounds_up() -> None:
    """端数は切り上げ、課金対象の利用が 0 クレジットにならない。"""
    # input 1 tok = 675 / 1e6 = 0.000675 → 1 クレジットに切り上げ
    assert calculate_credit_cost("sonnet", 1, 0) == 1


def test_baseline_credits_per_chat() -> None:
    """標準的な 1 回の消費（回数目安用）。Sonnet は概算 12 クレジット、Haiku は 0。"""
    # 10000×675/1e6 + 1500×3375/1e6 = 6.75 + 5.0625 = 11.8125 → ceil 12
    assert baseline_credits_per_chat("sonnet") == 12
    assert baseline_credits_per_chat("haiku") == 0


def test_grant_credits_rejects_non_positive(db_session) -> None:
    """付与額 0 以下は ValueError（実質消費になる付与を防ぐ最終ガード）。"""
    with pytest.raises(ValueError, match="付与額"):
        credit_service.grant_credits(
            db_session,
            "dummy-user-id",
            0,
            transaction_type=credit_service.TRANSACTION_TYPE_ADMIN_GRANT,
        )


# --- 統合テスト（チャット課金フロー） ---


def test_chat_haiku_works_with_zero_balance(client: TestClient, monkeypatch) -> None:
    """haiku（無料）は残高 0 でも利用でき、使用ログのみ記録される。"""
    fake = _FakeLLM(
        response=_llm_json("self_pr", "改善した自己PR"),
        input_tokens=1200,
        output_tokens=300,
    )
    monkeypatch.setattr(chat_service, "get_llm_client", lambda: fake)
    headers = auth_header(client, "billing-haiku")

    resp = client.post("/api/agent/chat", json=_chat_payload(), headers=headers)

    assert resp.status_code == 200
    assert fake.received_model_id == "claude-haiku-4-5"
    user_id = _get_user_id(client, "billing-haiku")
    repo = BillingRepository(client._db_session, user_id)
    assert repo.get_balance() == 0
    assert repo.list_transactions() == []
    logs = client._db_session.query(AgentUsageLog).filter_by(user_id=user_id).all()
    assert len(logs) == 1
    assert logs[0].model_alias == "haiku"
    assert logs[0].input_tokens == 1200
    assert logs[0].output_tokens == 300
    assert logs[0].credit_cost == 0


def test_chat_sonnet_consumes_credits(client: TestClient, monkeypatch) -> None:
    """sonnet は実トークン量からコストを算出し、残高減算 + 台帳 + 使用ログを記録する。"""
    fake = _FakeLLM(
        response=_llm_json("self_pr", "改善した自己PR"),
        input_tokens=1000,
        output_tokens=1000,
    )
    monkeypatch.setattr(chat_service, "get_llm_client", lambda: fake)
    headers = auth_header(client, "billing-sonnet")
    user_id = _get_user_id(client, "billing-sonnet")
    credit_service.grant_credits(
        client._db_session,
        user_id,
        10_000,
        transaction_type=credit_service.TRANSACTION_TYPE_ADMIN_GRANT,
    )

    resp = client.post("/api/agent/chat", json=_chat_payload("sonnet"), headers=headers)

    assert resp.status_code == 200
    assert fake.received_model_id == "claude-sonnet-4-6"
    repo = BillingRepository(client._db_session, user_id)
    # コスト: 1000×675/MTok + 1000×3375/MTok = 4.05 → ceil 5（1cr=¥1）
    assert repo.get_balance() == 10_000 - 5
    transactions = repo.list_transactions()
    consumption = [
        t for t in transactions
        if t.transaction_type == credit_service.TRANSACTION_TYPE_CONSUMPTION
    ]
    assert len(consumption) == 1
    assert consumption[0].amount == -5
    assert consumption[0].balance_after == 10_000 - 5


def test_chat_sonnet_with_zero_balance_returns_402(client: TestClient, monkeypatch) -> None:
    """sonnet は残高 0 で 402 INSUFFICIENT_CREDITS。LLM は呼ばれない。"""
    fake = _FakeLLM(response=_llm_json("self_pr", "提案"))
    monkeypatch.setattr(chat_service, "get_llm_client", lambda: fake)
    headers = auth_header(client, "billing-empty")

    resp = client.post("/api/agent/chat", json=_chat_payload("sonnet"), headers=headers)

    assert resp.status_code == 402
    # AppErrorResponse はトップレベルに code / message を持つ（main.py の例外ハンドラ）
    assert resp.json()["code"] == "INSUFFICIENT_CREDITS"
    assert fake.received_messages is None


def test_chat_sonnet_allows_negative_balance(client: TestClient, monkeypatch) -> None:
    """事前チェック通過後の実コストが残高を超えた場合は負残高で確定する（ADR-0012）。"""
    fake = _FakeLLM(
        response=_llm_json("self_pr", "提案"),
        input_tokens=1000,
        output_tokens=1000,
    )
    monkeypatch.setattr(chat_service, "get_llm_client", lambda: fake)
    headers = auth_header(client, "billing-negative")
    user_id = _get_user_id(client, "billing-negative")
    # 残高 3 で事前チェックは通るが、実コスト 5 が上回り負残高になる
    credit_service.grant_credits(
        client._db_session,
        user_id,
        3,
        transaction_type=credit_service.TRANSACTION_TYPE_ADMIN_GRANT,
    )

    resp = client.post("/api/agent/chat", json=_chat_payload("sonnet"), headers=headers)

    assert resp.status_code == 200
    assert BillingRepository(client._db_session, user_id).get_balance() == 3 - 5


def test_chat_sonnet_retry_usage_is_summed(client: TestClient, monkeypatch) -> None:
    """パース失敗 → リトライ成功時は 2 回分の実トークン量を合算して課金する。"""
    fake = _SequentialFakeLLM(
        ["JSON ではない応答", _llm_json("self_pr", "再生成の提案")],
        input_tokens=1000,
        output_tokens=1000,
    )
    monkeypatch.setattr(chat_service, "get_llm_client", lambda: fake)
    headers = auth_header(client, "billing-retry")
    user_id = _get_user_id(client, "billing-retry")
    credit_service.grant_credits(
        client._db_session,
        user_id,
        10_000,
        transaction_type=credit_service.TRANSACTION_TYPE_ADMIN_GRANT,
    )

    resp = client.post("/api/agent/chat", json=_chat_payload("sonnet"), headers=headers)

    assert resp.status_code == 200
    assert len(fake.calls) == 2
    # 2 呼び出し合算 2000/2000 トークン: (2000×675 + 2000×3375)/1e6 = 8.1 → ceil 9
    assert BillingRepository(client._db_session, user_id).get_balance() == 10_000 - 9


def test_record_chat_usage_is_atomic_on_log_failure(
    client: TestClient, monkeypatch
) -> None:
    """使用ログ記録が失敗したらクレジット消費も rollback される（課金済み・ログ無しを防ぐ / ADR-0012）。"""
    auth_header(client, "billing-atomic")
    user_id = _get_user_id(client, "billing-atomic")
    db = client._db_session
    credit_service.grant_credits(
        db,
        user_id,
        10_000,
        transaction_type=credit_service.TRANSACTION_TYPE_ADMIN_GRANT,
    )

    # 単一トランザクションの後半（使用ログ insert）で例外を起こす
    import app.repositories.billing as billing_repo

    def _boom(*_args, **_kwargs):
        raise RuntimeError("使用ログ記録失敗（テスト）")

    monkeypatch.setattr(billing_repo, "AgentUsageLog", _boom)

    usage = AgentUsage(model="sonnet", input_tokens=1000, output_tokens=1000)
    with pytest.raises(RuntimeError, match="使用ログ"):
        credit_service.record_chat_usage(db, user_id, usage)

    # 消費が rollback され、残高据え置き・consumption 台帳なし・使用ログなし
    repo = BillingRepository(db, user_id)
    assert repo.get_balance() == 10_000
    consumption = [
        t
        for t in repo.list_transactions()
        if t.transaction_type == credit_service.TRANSACTION_TYPE_CONSUMPTION
    ]
    assert consumption == []
    assert db.query(AgentUsageLog).filter_by(user_id=user_id).all() == []


def test_chat_rejects_unknown_model_alias(client: TestClient, monkeypatch) -> None:
    """カタログ外のモデル指定はスキーマ検証で 422（実モデル ID の注入を防ぐ）。"""
    fake = _FakeLLM(response=_llm_json("self_pr", "提案"))
    monkeypatch.setattr(chat_service, "get_llm_client", lambda: fake)
    headers = auth_header(client, "billing-unknown-model")

    resp = client.post(
        "/api/agent/chat",
        json=_chat_payload("claude-opus-4-8"),
        headers=headers,
    )

    assert resp.status_code == 422
    assert fake.received_messages is None


# --- 統合テスト（残高・台帳エンドポイント） ---


def test_get_balance_returns_current_balance(client: TestClient) -> None:
    """GET /api/billing/balance は現在残高を返す。"""
    auth_header(client, "billing-balance")
    user_id = _get_user_id(client, "billing-balance")
    credit_service.grant_credits(
        client._db_session,
        user_id,
        5_000,
        transaction_type=credit_service.TRANSACTION_TYPE_ADMIN_GRANT,
    )

    resp = client.get("/api/billing/balance")

    assert resp.status_code == 200
    assert resp.json() == {"balance": 5_000}


def test_get_balance_requires_auth(client: TestClient) -> None:
    """未ログインの残高照会は 401。"""
    resp = client.get("/api/billing/balance")
    assert resp.status_code == 401


def test_list_transactions_returns_history(client: TestClient, monkeypatch) -> None:
    """GET /api/billing/transactions は付与・消費の履歴を返す。"""
    fake = _FakeLLM(
        response=_llm_json("self_pr", "提案"), input_tokens=1000, output_tokens=1000
    )
    monkeypatch.setattr(chat_service, "get_llm_client", lambda: fake)
    headers = auth_header(client, "billing-history")
    user_id = _get_user_id(client, "billing-history")
    credit_service.grant_credits(
        client._db_session,
        user_id,
        1_000,
        transaction_type=credit_service.TRANSACTION_TYPE_ADMIN_GRANT,
        description="テスト付与",
    )
    resp = client.post("/api/agent/chat", json=_chat_payload("sonnet"), headers=headers)
    assert resp.status_code == 200

    resp = client.get("/api/billing/transactions")

    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 2
    types = {entry["transaction_type"] for entry in body}
    assert types == {"admin_grant", "consumption"}
    # 台帳エントリは金額と適用後残高のスナップショットを持つ
    consumption = next(e for e in body if e["transaction_type"] == "consumption")
    assert consumption["amount"] == -5
    assert consumption["balance_after"] == 1_000 - 5


# --- 統合テスト（使用量サマリ） ---


def test_usage_summary_aggregates_per_model(client: TestClient, monkeypatch) -> None:
    """GET /api/billing/usage-summary はモデル別にチャット回数・トークン・消費を集計する。"""
    headers = auth_header(client, "billing-usage")
    user_id = _get_user_id(client, "billing-usage")
    credit_service.grant_credits(
        client._db_session,
        user_id,
        10_000,
        transaction_type=credit_service.TRANSACTION_TYPE_ADMIN_GRANT,
    )
    # haiku 2 回（無料）・sonnet 1 回（有料）
    haiku = _FakeLLM(
        response=_llm_json("self_pr", "提案"), input_tokens=500, output_tokens=200
    )
    monkeypatch.setattr(chat_service, "get_llm_client", lambda: haiku)
    client.post("/api/agent/chat", json=_chat_payload(), headers=headers)
    client.post("/api/agent/chat", json=_chat_payload(), headers=headers)
    sonnet = _FakeLLM(
        response=_llm_json("self_pr", "提案"), input_tokens=1000, output_tokens=1000
    )
    monkeypatch.setattr(chat_service, "get_llm_client", lambda: sonnet)
    client.post("/api/agent/chat", json=_chat_payload("sonnet"), headers=headers)

    resp = client.get("/api/billing/usage-summary")

    assert resp.status_code == 200
    by_model = {entry["model"]: entry for entry in resp.json()}
    assert by_model["haiku"]["chat_count"] == 2
    assert by_model["haiku"]["input_tokens"] == 1000
    assert by_model["haiku"]["output_tokens"] == 400
    assert by_model["haiku"]["credit_cost"] == 0
    assert by_model["sonnet"]["chat_count"] == 1
    assert by_model["sonnet"]["credit_cost"] == 5


def test_usage_summary_empty_when_no_usage(client: TestClient) -> None:
    """利用実績が無ければ空配列（モデル一覧の補完は表示側が担う）。"""
    auth_header(client, "billing-no-usage")
    resp = client.get("/api/billing/usage-summary")
    assert resp.status_code == 200
    assert resp.json() == []


def test_usage_summary_requires_auth(client: TestClient) -> None:
    """未ログインの使用量サマリ取得は 401。"""
    resp = client.get("/api/billing/usage-summary")
    assert resp.status_code == 401


# --- 統合テスト（クレジットパック） ---


def test_list_credit_packs(client: TestClient) -> None:
    """GET /api/billing/packs は pricing.py のパック一覧を返す。"""
    auth_header(client, "billing-packs")
    resp = client.get("/api/billing/packs")
    assert resp.status_code == 200
    packs = resp.json()
    ids = [p["id"] for p in packs]
    assert ids == ["starter", "standard", "pro"]
    starter = packs[0]
    assert starter["price_jpy"] == 500
    # 1 クレジット = ¥1。スターターは等価
    assert starter["credits"] == 500


def test_list_model_rates(client: TestClient) -> None:
    """GET /api/billing/model-rates はモデル別の標準消費レートを返す。"""
    auth_header(client, "billing-rates")
    resp = client.get("/api/billing/model-rates")
    assert resp.status_code == 200
    by_model = {entry["model"]: entry for entry in resp.json()}
    assert by_model["haiku"]["is_free"] is True
    assert by_model["haiku"]["baseline_credits_per_chat"] == 0
    assert by_model["sonnet"]["is_free"] is False
    assert by_model["sonnet"]["baseline_credits_per_chat"] == 12


def test_list_model_rates_requires_auth(client: TestClient) -> None:
    """未ログインのレート取得は 401。"""
    resp = client.get("/api/billing/model-rates")
    assert resp.status_code == 401


def test_list_credit_packs_requires_auth(client: TestClient) -> None:
    """未ログインのパック一覧取得は 401。"""
    resp = client.get("/api/billing/packs")
    assert resp.status_code == 401


# --- 統合テスト（管理者付与） ---


def test_admin_grant_adds_credits(client: TestClient) -> None:
    """ADMIN_TOKEN 認証でユーザーへクレジットを付与できる。"""
    auth_header(client, "billing-grant-target")
    client.cookies.clear()  # Bearer 認証のみで呼ぶ（CSRF チェック対象外であることも担保）

    resp = client.post(
        "/api/billing/admin/grant",
        json={"username": "billing-grant-target", "amount": 30_000, "description": "テスト"},
        headers=_ADMIN_HEADERS,
    )

    assert resp.status_code == 200
    assert resp.json() == {"balance": 30_000}


def test_admin_grant_requires_bearer_token(client: TestClient) -> None:
    """Bearer トークンなしの付与は 401。"""
    resp = client.post(
        "/api/billing/admin/grant",
        json={"username": "anyone", "amount": 100},
    )
    assert resp.status_code == 401


def test_admin_grant_rejects_wrong_token(client: TestClient) -> None:
    """不正な Bearer トークンは 403。"""
    resp = client.post(
        "/api/billing/admin/grant",
        json={"username": "anyone", "amount": 100},
        headers={"Authorization": "Bearer wrong-token"},
    )
    assert resp.status_code == 403


def test_admin_grant_unknown_user_returns_404(client: TestClient) -> None:
    """存在しないユーザーへの付与は 404。"""
    resp = client.post(
        "/api/billing/admin/grant",
        json={"username": "no-such-user", "amount": 100},
        headers=_ADMIN_HEADERS,
    )
    assert resp.status_code == 404


def test_admin_grant_rejects_non_positive_amount(client: TestClient) -> None:
    """付与額 0 以下はスキーマ検証で 422。"""
    auth_header(client, "billing-grant-zero")
    client.cookies.clear()
    resp = client.post(
        "/api/billing/admin/grant",
        json={"username": "billing-grant-zero", "amount": 0},
        headers=_ADMIN_HEADERS,
    )
    assert resp.status_code == 422
