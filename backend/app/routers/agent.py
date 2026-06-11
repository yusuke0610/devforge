"""DevForge Agent（LLM チャット）エンドポイント（ADR-0010）。

外部 LLM API を呼ぶ高コスト endpoint のため rate limit を付与する。
DB は参照・更新しない（フロントが編集中フォームを送り、適用はフロント側）。
"""

import logging

from fastapi import APIRouter, Depends, Request

from ..core.errors import ErrorCode, raise_app_error
from ..core.messages import get_error
from ..core.security.auth import get_current_user
from ..core.security.dependencies import limiter
from ..models import User
from ..schemas.agent import AgentChatRequest, AgentChatResponse
from ..services.agent import chat_service
from ..services.agent.chat_service import (
    AgentResponseParseError,
    AgentTargetNotFoundError,
)
from ..services.agent.llm.base import LLMError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/agent", tags=["agent"])


@router.post("/chat", response_model=AgentChatResponse)
@limiter.limit("10/minute")
async def agent_chat(
    request: Request,
    body: AgentChatRequest,
    user: User = Depends(get_current_user),
) -> AgentChatResponse:
    """選択スコープの内容とプロンプトをもとに、職務経歴書への差分 operations を返す。

    レスポンスはフロントの state にのみ適用され、DB は更新しない。
    ユーザーが確認して「適用」した時点で既存の保存 API が呼ばれる。
    """
    try:
        return await chat_service.run_agent_chat(body)
    except AgentTargetNotFoundError:
        raise_app_error(
            status_code=422,
            code=ErrorCode.VALIDATION_ERROR,
            message=get_error("agent.target_not_found"),
        )
    except LLMError:
        raise_app_error(
            status_code=502,
            code=ErrorCode.AGENT_LLM_ERROR,
            message=get_error("agent.llm_failed"),
        )
    except AgentResponseParseError:
        raise_app_error(
            status_code=502,
            code=ErrorCode.AGENT_PARSE_ERROR,
            message=get_error("agent.parse_failed"),
        )
