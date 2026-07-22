"""Agent 応答の構造化出力スキーマ（tool use input_schema）の構築。

機械検証可能な制約（許可 field・文字数上限・JSON 構造・配列上限）の正本。
プロンプト（app/prompts/agent_*.md）には機械検証不能な制約（品質基準・
捏造禁止・思考ステップ）のみを書く（ADR-0010「制約の責務分離」）。

注意: Anthropic の非 strict tool use は maxLength を API 側で強制しない（モデルへの
助言扱い）。Ollama（llama.cpp の format → GBNF 文法変換）は maxLength / maxItems を
解釈できず文法変換自体が失敗するため、to_portable_schema で数値制約を除去してから渡す
（ADR-0013）。いずれの経路でも文字数上限の実強制は chat_service._parse_response の
破棄ロジックが担う（二重防衛）。
maxLength は JSON Schema 仕様どおり Unicode 文字数（日本語の len() と一致）。
"""

from typing import cast

TOOL_NAME = "propose_revision"
TOOL_DESCRIPTION = "職務経歴書フィールドの改善案・説明・次の依頼候補を返す"

# スコープごとに operations が編集してよいフィールドと文字数上限（SSoT）
SCOPE_FIELDS: dict[str, dict[str, int]] = {
    "career_summary": {"career_summary": 2000},
    "self_pr": {"self_pr": 2000},
    "project": {"description": 4500, "role": 200},
    "experience": {"business_description": 200, "description": 4500},
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


def to_portable_schema(schema: dict, *, drop_additional_properties: bool = False) -> dict:
    """build_output_schema の出力を、Ollama の構造化出力（``format``）に通る形へ変換する。

    Ollama ``format``（llama.cpp の GBNF 文法変換）は ``oneOf`` / ``const`` / ``maxLength`` /
    ``maxItems`` といった JSON Schema キーワードで文法変換が壊れるため、以下に正規化する:

    - operations.items の ``oneOf`` 分岐 → ``field`` を許可値の ``enum`` に畳んだ単一オブジェクト
    - ``maxLength`` / ``maxItems`` を除去（上限の実強制は chat_service._parse_response が担う / 二重防衛）

    ``drop_additional_properties`` は ``additionalProperties`` を除去するオプション（既定 False）。

    Anthropic（tool use）は oneOf/const/maxLength を解釈できるため元スキーマをそのまま使い、
    本関数は通さない。本番は Anthropic のみ・本関数はローカル開発の Ollama 経路専用（ADR-0023）。
    """
    strip_keys = {"maxLength", "maxItems"}
    if drop_additional_properties:
        strip_keys = strip_keys | {"additionalProperties"}
    # _strip_constraints は object を返すが、dict 入力に対しては dict を返す（下で .get / 返却に使う）。
    portable = cast(dict, _strip_constraints(schema, strip_keys))
    operations = portable.get("properties", {}).get("operations", {})
    items = operations.get("items", {})
    branches = items.get("oneOf")
    if branches:
        # 各分岐の field.const を集めて enum 化（許可フィールド名の集合）
        allowed_fields = [
            b["properties"]["field"]["const"]
            for b in branches
            if "const" in b.get("properties", {}).get("field", {})
        ]
        item_schema: dict = {
            "type": "object",
            "properties": {
                "field": {"type": "string", "enum": allowed_fields},
                "value": {
                    "type": "string",
                    "description": "職務経歴書にそのまま掲載できる完成した日本語の本文",
                },
            },
            "required": ["field", "value"],
        }
        if not drop_additional_properties:
            item_schema["additionalProperties"] = False
        operations["items"] = item_schema
    return portable


def _strip_constraints(node: object, strip_keys: set[str]) -> object:
    """strip_keys のキーを再帰的に除去したコピーを返す（破壊しない）。"""
    if isinstance(node, dict):
        return {
            key: _strip_constraints(value, strip_keys)
            for key, value in node.items()
            if key not in strip_keys
        }
    if isinstance(node, list):
        return [_strip_constraints(item, strip_keys) for item in node]
    return node
