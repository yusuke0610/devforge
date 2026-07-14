"""スキル表示名提案の LLM 構造化出力スキーマ（機械制約の正本 / ADR-0016 D11）。

チャット・ドラフトのスキーマと同じ責務分離に従う:
機械検証可能な制約（グループ構造・表示名の文字数上限・メンバーの許可集合）はここに置き、
品質制約（畳み込みの粒度・保守的判断・捏造禁止）は ``prompts/agent_skill_display.md`` に置く。

ドラフト（``../resume_draft/output_schema.py``）と同様、メンバーを実在スキルの **token 集合**
の enum で縛るためスキーマはリクエストごとに動的構築する（存在しないスキルへの言及を
構造的に排除する）。プロンプト md は静的を維持し、動的情報は user メッセージの JSON に載せる。
"""

# 表示名の文字数上限（DB は 255 だが、スキル表示名は短いラベルなので実用上の上限を絞る）。
# 上限の実強制は proposer のパース側が担う（maxLength は API では強制されないため / 二重防衛）。
MAX_DISPLAY_NAME_LENGTH = 80


def build_skill_display_output_schema(member_tokens: list[str]) -> dict:
    """実在スキルの token 集合から、表示名提案の出力 JSON Schema を構築する。

    各グループは「表示名 + メンバー token 群」。メンバーは ``member_tokens`` の enum に
    縛られ、存在しないスキルを指せない。単独スキルのリネームはメンバー 1 件のグループで表す。
    """
    return {
        "type": "object",
        "properties": {
            "groups": {
                "type": "array",
                "description": "表示名の確定候補。1 グループ = 1 表示スキル（複数メンバーは畳み込み）",
                "items": {
                    "type": "object",
                    "properties": {
                        "display_name": {
                            "type": "string",
                            "maxLength": MAX_DISPLAY_NAME_LENGTH,
                            "description": "人間が読みやすい表示名（例: 「Amazon S3」）",
                        },
                        "members": {
                            "type": "array",
                            "description": "このグループに畳むスキルの token（与えた token のみ）",
                            "items": {"type": "string", "enum": member_tokens},
                        },
                    },
                    "required": ["display_name", "members"],
                    "additionalProperties": False,
                },
            },
        },
        "required": ["groups"],
        "additionalProperties": False,
    }
