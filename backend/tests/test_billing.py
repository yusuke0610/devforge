"""クレジット課金（ADR-0012）の統合テスト。

LLM（外部 API）のみモックし、残高チェック・消費・台帳記録・使用ログは
実 DB（テスト用 SQLite セッション）を通す。
"""

from typing import cast, get_args

import pytest
import stripe
from app.core import settings
from app.models import AgentUsageLog
from app.repositories import BillingRepository, UserRepository
from app.schemas.agent import AgentModelAlias
from app.services.agent import chat_service
from app.services.agent.chat_service import AgentUsage
from app.services.agent.llm.base import LLMClient, LLMError, LLMResult
from app.services.agent.model_catalog import (
    MARGIN_MULTIPLIER,
    MODEL_CATALOG,
    YEN_PER_CREDIT,
    YEN_PER_USD,
    baseline_credits_per_chat,
    calculate_credit_cost,
)
from app.services.billing import credit_service, stripe_service
from fastapi.testclient import TestClient

from conftest import auth_header
from test_agent import _FakeLLM, _llm_json, _resume_payload, _SequentialFakeLLM

_ADMIN_HEADERS = {"Authorization": "Bearer test-admin-token"}


def _completed_event(
    user_id: str,
    credits: int,
    *,
    session_id: str = "cs_test_123",
    payment_status: str = "paid",
    event_type: str = "checkout.session.completed",
) -> dict:
    """Stripe Webhook の checkout.session.completed イベント相当の dict を返す。

    stripe.Event は dict ライクに振る舞うため、署名検証をモックする際はこの構造で代用できる。
    """
    return {
        "type": event_type,
        "data": {
            "object": {
                "id": session_id,
                "payment_status": payment_status,
                "metadata": {"user_id": user_id, "credits": str(credits)},
            }
        },
    }


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
    # Vertex AI の Anthropic model id は版指定が要る（Haiku は @20251001 必須 / ADR-0015）
    assert MODEL_CATALOG["haiku"].model_id == "claude-haiku-4-5@20251001"
    assert MODEL_CATALOG["haiku"].is_free is True
    assert MODEL_CATALOG["sonnet"].model_id == "claude-sonnet-4-6"
    assert MODEL_CATALOG["sonnet"].is_free is False


def test_model_catalog_providers_are_valid() -> None:
    """全 spec の provider は既知の識別子（anthropic / google / openai）である。"""
    valid = {"anthropic", "google", "openai"}
    assert all(spec.provider in valid for spec in MODEL_CATALOG.values())


def test_model_catalog_multi_provider_entries() -> None:
    """Gemini / GPT エイリアスが正しいプロバイダ・実モデル ID で登録されている（ADR-0013）。"""
    assert MODEL_CATALOG["gemini-flash"].provider == "google"
    assert MODEL_CATALOG["gemini-flash"].model_id == "gemini-2.5-flash"
    assert MODEL_CATALOG["gemini-pro"].provider == "google"
    assert MODEL_CATALOG["gpt-mini"].provider == "openai"
    assert MODEL_CATALOG["gpt"].provider == "openai"


def test_model_catalog_free_and_paid_tiers() -> None:
    """低単価モデル（haiku / gemini-flash / gpt-mini）は無料枠、上位は有料（ADR-0013）。"""
    for alias in ("haiku", "gemini-flash", "gpt-mini"):
        assert MODEL_CATALOG[alias].is_free is True
        assert calculate_credit_cost(alias, 10_000, 1_500) == 0
    for alias in ("sonnet", "gemini-pro", "gpt"):
        assert MODEL_CATALOG[alias].is_free is False
        # 有料モデルは非ゼロのトークンで必ずコストが出る
        assert calculate_credit_cost(alias, 10_000, 1_500) > 0


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
    monkeypatch.setattr(chat_service, "get_llm_client", lambda provider: fake)
    headers = auth_header(client, "billing-haiku")

    resp = client.post("/api/agent/chat", json=_chat_payload(), headers=headers)

    assert resp.status_code == 200
    assert fake.received_model_id == "claude-haiku-4-5@20251001"
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
    monkeypatch.setattr(chat_service, "get_llm_client", lambda provider: fake)
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


def test_chat_refreshes_session_before_recording_usage(
    client: TestClient, monkeypatch
) -> None:
    """LLM 応答後、消費記録の前に DB セッションを開き直す（Hrana STREAM_EXPIRED 回帰防止）。

    libSQL（Hrana over HTTP）は LLM の await 中に idle stream が失効するため、消費記録の
    commit 前に ``db.close()`` で失効ストリームを解放し、新規ストリームで commit させる。
    本テストは「close が record_chat_usage より前に呼ばれる」順序と、消費が正しく確定する
    ことを検証する。
    """
    fake = _FakeLLM(
        response=_llm_json("self_pr", "改善した自己PR"),
        input_tokens=1000,
        output_tokens=1000,
    )
    monkeypatch.setattr(chat_service, "get_llm_client", lambda provider: fake)
    headers = auth_header(client, "billing-refresh")
    user_id = _get_user_id(client, "billing-refresh")
    credit_service.grant_credits(
        client._db_session,
        user_id,
        10_000,
        transaction_type=credit_service.TRANSACTION_TYPE_ADMIN_GRANT,
    )

    events: list[str] = []
    original_close = client._db_session.close
    monkeypatch.setattr(
        client._db_session,
        "close",
        lambda *a, **kw: (events.append("close"), original_close(*a, **kw))[1],
    )
    import app.routers.agent as agent_router

    original_record = credit_service.record_chat_usage

    def _spy_record(*a, **kw):
        events.append("record")
        return original_record(*a, **kw)

    monkeypatch.setattr(agent_router.credit_service, "record_chat_usage", _spy_record)

    resp = client.post("/api/agent/chat", json=_chat_payload("sonnet"), headers=headers)

    assert resp.status_code == 200
    # close が record より前に呼ばれている
    assert events == ["close", "record"]
    # セッション刷新後も消費が正しく確定している
    assert BillingRepository(client._db_session, user_id).get_balance() == 10_000 - 5


def test_chat_sonnet_with_zero_balance_returns_402(client: TestClient, monkeypatch) -> None:
    """sonnet は残高 0 で 402 INSUFFICIENT_CREDITS。LLM は呼ばれない。"""
    fake = _FakeLLM(response=_llm_json("self_pr", "提案"))
    monkeypatch.setattr(chat_service, "get_llm_client", lambda provider: fake)
    headers = auth_header(client, "billing-empty")

    resp = client.post("/api/agent/chat", json=_chat_payload("sonnet"), headers=headers)

    assert resp.status_code == 402
    # AppErrorResponse はトップレベルに code / message を持つ（main.py の例外ハンドラ）
    assert resp.json()["code"] == "INSUFFICIENT_CREDITS"
    assert fake.received_messages is None


def test_chat_requires_auth(client: TestClient, monkeypatch) -> None:
    """トークン無しの /api/agent/chat は 401（get_current_user ガードの回帰防止）。

    認証が外れると未ログインで LLM を呼べてしまうため、ガード欠落を直接固定する。
    """
    fake = _FakeLLM(response=_llm_json("self_pr", "提案"))
    monkeypatch.setattr(chat_service, "get_llm_client", lambda provider: fake)

    resp = client.post("/api/agent/chat", json=_chat_payload("haiku"))

    assert resp.status_code == 401
    # 認証で弾かれるため LLM は呼ばれない
    assert fake.received_messages is None


@pytest.mark.parametrize("model", ["gemini-pro", "gpt"])
def test_chat_paid_model_with_zero_balance_returns_402(
    client: TestClient, monkeypatch, model: str
) -> None:
    """有料モデル（gemini-pro / gpt）も残高 0 で 402。is_free 判定の SSoT 化を endpoint で固定。

    残高ゲートが sonnet だけでなく全有料モデルに効くこと（ハードコード回帰でバイパスされない）を守る。
    """
    fake = _FakeLLM(response=_llm_json("self_pr", "提案"))
    monkeypatch.setattr(chat_service, "get_llm_client", lambda provider: fake)
    headers = auth_header(client, f"billing-empty-{model}")

    resp = client.post("/api/agent/chat", json=_chat_payload(model), headers=headers)

    assert resp.status_code == 402
    assert resp.json()["code"] == "INSUFFICIENT_CREDITS"
    # 残高不足で弾かれるため LLM は呼ばれない
    assert fake.received_messages is None


def test_chat_sonnet_allows_negative_balance(client: TestClient, monkeypatch) -> None:
    """事前チェック通過後の実コストが残高を超えた場合は負残高で確定する（ADR-0012）。"""
    fake = _FakeLLM(
        response=_llm_json("self_pr", "提案"),
        input_tokens=1000,
        output_tokens=1000,
    )
    monkeypatch.setattr(chat_service, "get_llm_client", lambda provider: fake)
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
    monkeypatch.setattr(chat_service, "get_llm_client", lambda provider: fake)
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


def test_chat_sonnet_retry_failure_still_bills_usage(
    client: TestClient, monkeypatch
) -> None:
    """パース失敗 → リトライも失敗（502）でも、消費済み 2 回分の API 原価は課金する。

    リトライ後も失敗した場合に課金をスキップすると、有料モデルの呼び出し原価が
    課金漏れになる。502 を返しつつ残高減算・使用ログ記録を確定させる（ADR-0012）。
    """
    fake = _SequentialFakeLLM(
        ["不正応答 1 回目", "不正応答 2 回目"],
        input_tokens=1000,
        output_tokens=1000,
    )
    monkeypatch.setattr(chat_service, "get_llm_client", lambda provider: fake)
    headers = auth_header(client, "billing-retry-fail")
    user_id = _get_user_id(client, "billing-retry-fail")
    credit_service.grant_credits(
        client._db_session,
        user_id,
        10_000,
        transaction_type=credit_service.TRANSACTION_TYPE_ADMIN_GRANT,
    )

    resp = client.post("/api/agent/chat", json=_chat_payload("sonnet"), headers=headers)

    assert resp.status_code == 502
    assert resp.json()["code"] == "AGENT_PARSE_ERROR"
    assert len(fake.calls) == 2
    repo = BillingRepository(client._db_session, user_id)
    # 2 呼び出し合算 2000/2000 トークン: (2000×675 + 2000×3375)/1e6 = 8.1 → ceil 9
    assert repo.get_balance() == 10_000 - 9
    consumption = [
        t
        for t in repo.list_transactions()
        if t.transaction_type == credit_service.TRANSACTION_TYPE_CONSUMPTION
    ]
    assert len(consumption) == 1
    assert consumption[0].amount == -9
    logs = client._db_session.query(AgentUsageLog).filter_by(user_id=user_id).all()
    assert len(logs) == 1
    assert logs[0].model_alias == "sonnet"
    assert logs[0].credit_cost == 9


def test_chat_sonnet_retry_llm_error_still_bills_first_attempt(
    client: TestClient, monkeypatch
) -> None:
    """1 回目成功（パース失敗）→ リトライ呼び出しが LLMError でも 1 回目分は課金する。

    リトライの API 呼び出し自体が失敗（502 AGENT_LLM_ERROR）しても、1 回目の原価は
    発生済みのため課金を確定させる（課金漏れを防ぐ / ADR-0012）。
    """

    class _FailOnRetryLLM(LLMClient):
        """1 回目はパース不能応答（課金対象トークンつき）、2 回目は LLMError を投げる。"""

        def __init__(self) -> None:
            self.calls = 0

        async def generate(self, *_args, **_kwargs) -> LLMResult:
            self.calls += 1
            if self.calls == 1:
                return LLMResult(text="不正応答", input_tokens=1000, output_tokens=1000)
            raise LLMError("リトライ呼び出し失敗（テスト）")

    fake = _FailOnRetryLLM()
    monkeypatch.setattr(chat_service, "get_llm_client", lambda provider: fake)
    headers = auth_header(client, "billing-retry-llm-error")
    user_id = _get_user_id(client, "billing-retry-llm-error")
    credit_service.grant_credits(
        client._db_session,
        user_id,
        10_000,
        transaction_type=credit_service.TRANSACTION_TYPE_ADMIN_GRANT,
    )

    resp = client.post("/api/agent/chat", json=_chat_payload("sonnet"), headers=headers)

    assert resp.status_code == 502
    assert resp.json()["code"] == "AGENT_LLM_ERROR"
    assert fake.calls == 2
    repo = BillingRepository(client._db_session, user_id)
    # 1 回目のみ 1000/1000 トークン: (1000×675 + 1000×3375)/1e6 = 4.05 → ceil 5
    assert repo.get_balance() == 10_000 - 5
    logs = client._db_session.query(AgentUsageLog).filter_by(user_id=user_id).all()
    assert len(logs) == 1
    assert logs[0].credit_cost == 5


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
    monkeypatch.setattr(chat_service, "get_llm_client", lambda provider: fake)
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
    monkeypatch.setattr(chat_service, "get_llm_client", lambda provider: fake)
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
    monkeypatch.setattr(chat_service, "get_llm_client", lambda provider: haiku)
    client.post("/api/agent/chat", json=_chat_payload(), headers=headers)
    client.post("/api/agent/chat", json=_chat_payload(), headers=headers)
    sonnet = _FakeLLM(
        response=_llm_json("self_pr", "提案"), input_tokens=1000, output_tokens=1000
    )
    monkeypatch.setattr(chat_service, "get_llm_client", lambda provider: sonnet)
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


# --- ユニットテスト（Stripe 購入の冪等性 / ADR-0012 Phase 2） ---


def test_record_stripe_purchase_grants_once(client: TestClient) -> None:
    """同一 stripe_session_id の Webhook 再送は二重付与しない（UNIQUE 制約 + 事前チェック）。"""
    auth_header(client, "billing-purchase-idem")
    user_id = _get_user_id(client, "billing-purchase-idem")
    db = client._db_session

    first = credit_service.record_stripe_purchase(
        db, user_id, 1_000, stripe_session_id="cs_idem_1"
    )
    second = credit_service.record_stripe_purchase(
        db, user_id, 1_000, stripe_session_id="cs_idem_1"
    )

    assert first == 1_000
    # 2 回目は処理済みのため None（付与スキップ）
    assert second is None
    repo = BillingRepository(db, user_id)
    assert repo.get_balance() == 1_000
    purchases = [
        t for t in repo.list_transactions()
        if t.transaction_type == credit_service.TRANSACTION_TYPE_PURCHASE
    ]
    assert len(purchases) == 1
    assert purchases[0].amount == 1_000
    assert purchases[0].stripe_session_id == "cs_idem_1"


def test_extract_completed_purchase_skips_unpaid() -> None:
    """未払い（payment_status != paid）のイベントは付与対象にしない。"""
    event = _completed_event("u1", 1_000, payment_status="unpaid")
    # stripe.Event は dict ライクに振る舞う（helper は同等 dict を返す）。境界で型を合わせる。
    assert stripe_service.extract_completed_purchase(cast(stripe.Event, event)) is None


def test_extract_completed_purchase_skips_other_event_types() -> None:
    """checkout.session.completed 以外のイベントは付与対象にしない。"""
    event = _completed_event("u1", 1_000, event_type="payment_intent.created")
    assert stripe_service.extract_completed_purchase(cast(stripe.Event, event)) is None


# --- 統合テスト（Checkout セッション作成） ---


def test_create_checkout_returns_url(client: TestClient, monkeypatch) -> None:
    """POST /api/billing/checkout は Stripe Checkout の URL を返し、入力どおりに呼び出す。"""
    headers = auth_header(client, "billing-checkout")
    captured: dict = {}

    def _fake_create(*, user_id, credits, success_url, cancel_url):
        captured.update(
            user_id=user_id,
            credits=credits,
            success_url=success_url,
            cancel_url=cancel_url,
        )
        return "https://checkout.stripe.com/c/pay/cs_test_123"

    monkeypatch.setattr(stripe_service, "create_checkout_session", _fake_create)

    resp = client.post("/api/billing/checkout", json={"credits": 1_000}, headers=headers)

    assert resp.status_code == 200
    assert resp.json() == {"checkout_url": "https://checkout.stripe.com/c/pay/cs_test_123"}
    assert captured["credits"] == 1_000
    # success/cancel URL はサーバー側で信頼済みベース URL から組み立てる（オープンリダイレクト防止）
    assert captured["success_url"].endswith("/billing?checkout=success")
    assert captured["cancel_url"].endswith("/billing?checkout=cancel")


def test_create_checkout_requires_auth(client: TestClient) -> None:
    """未ログインの Checkout 作成は 401。"""
    resp = client.post("/api/billing/checkout", json={"credits": 1_000})
    assert resp.status_code == 401


def test_create_checkout_rejects_out_of_range(client: TestClient) -> None:
    """購入クレジットが下限未満はスキーマ検証で 422。"""
    headers = auth_header(client, "billing-checkout-range")
    resp = client.post("/api/billing/checkout", json={"credits": 1}, headers=headers)
    assert resp.status_code == 422


def test_create_checkout_unconfigured_returns_503(client: TestClient, monkeypatch) -> None:
    """STRIPE_SECRET_KEY 未設定なら 503 PAYMENT_ERROR（決済機能無効）。"""
    headers = auth_header(client, "billing-checkout-unconfigured")
    monkeypatch.setattr(settings, "get_stripe_secret_key", lambda: "")

    resp = client.post("/api/billing/checkout", json={"credits": 1_000}, headers=headers)

    assert resp.status_code == 503
    assert resp.json()["code"] == "PAYMENT_ERROR"


def test_create_checkout_stripe_error_returns_502(client: TestClient, monkeypatch) -> None:
    """Stripe API 呼び出し失敗は 502 PAYMENT_ERROR。"""
    headers = auth_header(client, "billing-checkout-error")

    def _boom(**_kwargs):
        raise stripe_service.StripeCheckoutError("Stripe error: APIError")

    monkeypatch.setattr(stripe_service, "create_checkout_session", _boom)

    resp = client.post("/api/billing/checkout", json={"credits": 1_000}, headers=headers)

    assert resp.status_code == 502
    assert resp.json()["code"] == "PAYMENT_ERROR"


# --- 統合テスト（Stripe Webhook 入金処理） ---


def test_webhook_grants_credits_on_completed(client: TestClient, monkeypatch) -> None:
    """checkout.session.completed（支払い済み）でクレジットを付与し purchase 台帳を記録する。"""
    auth_header(client, "billing-webhook")
    user_id = _get_user_id(client, "billing-webhook")
    client.cookies.clear()  # Stripe からの受信を模す（Cookie なし → CSRF 対象外）
    event = _completed_event(user_id, 2_000, session_id="cs_webhook_1")
    monkeypatch.setattr(stripe_service, "parse_webhook_event", lambda *_a, **_k: event)

    resp = client.post(
        "/api/billing/webhook",
        content=b"{}",
        headers={"Stripe-Signature": "t=1,v1=sig"},
    )

    assert resp.status_code == 200
    assert resp.json() == {"received": True}
    repo = BillingRepository(client._db_session, user_id)
    assert repo.get_balance() == 2_000
    purchases = [
        t for t in repo.list_transactions()
        if t.transaction_type == credit_service.TRANSACTION_TYPE_PURCHASE
    ]
    assert len(purchases) == 1
    assert purchases[0].amount == 2_000
    assert purchases[0].stripe_session_id == "cs_webhook_1"


def test_webhook_is_idempotent_on_resend(client: TestClient, monkeypatch) -> None:
    """同一イベントの再送では二重付与しない（Webhook 再送に対する冪等性）。"""
    auth_header(client, "billing-webhook-idem")
    user_id = _get_user_id(client, "billing-webhook-idem")
    client.cookies.clear()  # Stripe からの受信を模す（Cookie なし → CSRF 対象外）
    event = _completed_event(user_id, 2_000, session_id="cs_webhook_resend")
    monkeypatch.setattr(stripe_service, "parse_webhook_event", lambda *_a, **_k: event)

    first = client.post("/api/billing/webhook", content=b"{}", headers={"Stripe-Signature": "s"})
    second = client.post("/api/billing/webhook", content=b"{}", headers={"Stripe-Signature": "s"})

    assert first.status_code == 200
    assert second.status_code == 200
    repo = BillingRepository(client._db_session, user_id)
    # 2 回受信しても付与は 1 回分のみ
    assert repo.get_balance() == 2_000
    purchases = [
        t for t in repo.list_transactions()
        if t.transaction_type == credit_service.TRANSACTION_TYPE_PURCHASE
    ]
    assert len(purchases) == 1


def test_webhook_invalid_signature_returns_400(client: TestClient, monkeypatch) -> None:
    """署名検証に失敗したら 400（付与しない）。"""
    def _bad_sig(*_a, **_k):
        raise stripe_service.WebhookVerificationError("Webhook verification failed")

    monkeypatch.setattr(stripe_service, "parse_webhook_event", _bad_sig)

    resp = client.post("/api/billing/webhook", content=b"{}", headers={"Stripe-Signature": "bad"})

    assert resp.status_code == 400


def test_webhook_unconfigured_returns_503(client: TestClient) -> None:
    """STRIPE_WEBHOOK_SECRET 未設定なら署名検証できず 503（fail-closed）。"""
    resp = client.post("/api/billing/webhook", content=b"{}", headers={"Stripe-Signature": "x"})
    assert resp.status_code == 503


def test_webhook_ignores_non_completed_event(client: TestClient, monkeypatch) -> None:
    """付与対象外イベントは 200 で受領しつつ付与しない。"""
    auth_header(client, "billing-webhook-other")
    user_id = _get_user_id(client, "billing-webhook-other")
    client.cookies.clear()  # Stripe からの受信を模す（Cookie なし → CSRF 対象外）
    event = _completed_event(user_id, 2_000, event_type="payment_intent.created")
    monkeypatch.setattr(stripe_service, "parse_webhook_event", lambda *_a, **_k: event)

    resp = client.post("/api/billing/webhook", content=b"{}", headers={"Stripe-Signature": "s"})

    assert resp.status_code == 200
    assert BillingRepository(client._db_session, user_id).get_balance() == 0


def test_webhook_unknown_user_returns_200_without_grant(client: TestClient, monkeypatch) -> None:
    """metadata のユーザーが存在しなくても 200 で受領する（再送で解決しないため）。"""
    event = _completed_event("no-such-user-id", 2_000, session_id="cs_unknown")
    monkeypatch.setattr(stripe_service, "parse_webhook_event", lambda *_a, **_k: event)

    resp = client.post("/api/billing/webhook", content=b"{}", headers={"Stripe-Signature": "s"})

    assert resp.status_code == 200
    assert resp.json() == {"received": True}


def test_webhook_path_is_internal_secret_exempt() -> None:
    """Webhook は Cloudflare を経由せず Cloud Run へ直接届くため InternalSecret 検証の対象外。"""
    import app.main as main_module

    assert "/api/billing/webhook" in main_module._INTERNAL_SECRET_SKIP_PATHS
