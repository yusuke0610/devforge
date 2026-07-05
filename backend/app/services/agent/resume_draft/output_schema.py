"""経歴書ドラフトの LLM 構造化出力スキーマ（機械制約の正本 / ADR-0018）。

チャットのスキーマ（``../output_schema.py``）と同じ責務分離に従う:
機械検証可能な制約（フィールド構造・文字数上限・リポ名の許可集合）はここに置き、
品質制約（文体・捏造禁止・目安字数）は ``prompts/agent_resume_draft.md`` に置く。

チャットと異なり ``repo_full_name`` を選定リポジトリの enum で縛るため、スキーマは
リクエストごとに動的構築する（存在しないリポジトリへの言及を構造的に排除する）。
プロンプト md は静的を維持し、動的情報は user メッセージの JSON コンテキストに載せる。

文字数上限は保存契約（schemas/resume.py）と揃えるため、チャット側の
``SCOPE_FIELDS``（``test_scope_limits_match_resume_schema`` で drift 検証済み）を参照する。
"""

from ..output_schema import SCOPE_FIELDS

# 上限の正本はチャット側 SCOPE_FIELDS（= schemas/resume.py と drift テスト済み）
MAX_CAREER_SUMMARY_LENGTH = SCOPE_FIELDS["career_summary"]["career_summary"]
MAX_SELF_PR_LENGTH = SCOPE_FIELDS["self_pr"]["self_pr"]
MAX_PROJECT_DESCRIPTION_LENGTH = SCOPE_FIELDS["project"]["description"]


def build_draft_output_schema(repo_full_names: list[str]) -> dict:
    """選定リポジトリの許可集合から、ドラフト生成の出力 JSON Schema を構築する。

    LLM クライアント側の tool 定義（``build_tool_definition`` / tool 名は
    ``propose_revision`` 固定）にそのまま渡せる形。maxLength は API では強制されない
    ため、上限超過の扱いは draft_service のパース側が担う（二重防衛）。
    """
    return {
        "type": "object",
        "properties": {
            "career_summary": {
                "type": "string",
                "maxLength": MAX_CAREER_SUMMARY_LENGTH,
                "description": "職務要約。経歴書にそのまま掲載できる完成した日本語の文章",
            },
            "self_pr": {
                "type": "string",
                "maxLength": MAX_SELF_PR_LENGTH,
                "description": "自己PR。経歴書にそのまま掲載できる完成した日本語の文章",
            },
            "project_descriptions": {
                "type": "array",
                "description": "各リポジトリの業務内容説明。与えられたリポジトリのみ対象",
                "maxItems": len(repo_full_names),
                "items": {
                    "type": "object",
                    "properties": {
                        "repo_full_name": {
                            "type": "string",
                            "enum": repo_full_names,
                        },
                        "description": {
                            "type": "string",
                            "maxLength": MAX_PROJECT_DESCRIPTION_LENGTH,
                            "description": "経歴書にそのまま掲載できる完成した日本語の本文",
                        },
                    },
                    "required": ["repo_full_name", "description"],
                    "additionalProperties": False,
                },
            },
        },
        "required": ["career_summary", "self_pr", "project_descriptions"],
        "additionalProperties": False,
    }
