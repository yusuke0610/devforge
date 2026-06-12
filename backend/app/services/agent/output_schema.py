"""Agent 応答の構造化出力スキーマ（tool use input_schema）の構築。

機械検証可能な制約（許可 field・文字数上限・JSON 構造・配列上限）の正本。
プロンプト（app/prompts/agent_*.md）には機械検証不能な制約（品質基準・
捏造禁止・思考ステップ）のみを書く（ADR-0010「制約の責務分離」）。

注意: Anthropic の非 strict tool use / Ollama の format（文法制約）は
maxLength を API 側で強制しない（モデルへの助言扱い）。文字数上限の
実強制は chat_service._parse_response の破棄ロジックが担う（二重防衛）。
maxLength は JSON Schema 仕様どおり Unicode 文字数（日本語の len() と一致）。
"""

TOOL_NAME = "propose_revision"
TOOL_DESCRIPTION = "職務経歴書フィールドの改善案・説明・次の依頼候補を返す"

# スコープごとに operations が編集してよいフィールドと文字数上限（SSoT）
SCOPE_FIELDS: dict[str, dict[str, int]] = {
    "career_summary": {"career_summary": 2000},
    "self_pr": {"self_pr": 2000},
    "project": {"description": 4500, "role": 200},
}

# LLM が生成する「次の依頼候補」（suggestions）の制約
MAX_SUGGESTIONS = 4
MAX_SUGGESTION_LENGTH = 200


def build_output_schema(scope: str) -> dict:
    """スコープの許可 field・上限から propose_revision の input JSON Schema を構築する。

    operations.items は field ごとの oneOf 分岐にする（project は description と
    role で maxLength が異なるため、field 名と上限をペアで制約する必要がある）。
    """
    operation_branches = [
        {
            "type": "object",
            "properties": {
                "field": {"const": field},
                "value": {
                    "type": "string",
                    "maxLength": limit,
                    "description": "職務経歴書にそのまま掲載できる完成した日本語の本文",
                },
            },
            "required": ["field", "value"],
            "additionalProperties": False,
        }
        for field, limit in SCOPE_FIELDS[scope].items()
    ]
    return {
        "type": "object",
        "properties": {
            "message": {
                "type": "string",
                "description": "提案の説明（日本語）。何をどう改善したか",
            },
            "operations": {
                "type": "array",
                "description": "編集対象フィールドの置換案。提案できない場合は空配列",
                "items": {"oneOf": operation_branches},
            },
            "suggestions": {
                "type": "array",
                "description": "曖昧な依頼への次の依頼文候補。operations を返すときは空配列",
                "items": {"type": "string", "maxLength": MAX_SUGGESTION_LENGTH},
                "maxItems": MAX_SUGGESTIONS,
            },
        },
        "required": ["message", "operations", "suggestions"],
        "additionalProperties": False,
    }


def build_tool_definition(input_schema: dict) -> dict:
    """Anthropic Messages API に渡す tool 定義を構築する。"""
    return {
        "name": TOOL_NAME,
        "description": TOOL_DESCRIPTION,
        "input_schema": input_schema,
    }
