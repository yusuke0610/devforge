"""PDF 経歴書抽出の LLM 構造化出力スキーマ（機械制約の正本 / ADR-0024）。

チャット・ドラフトと同じ責務分離に従う: 機械検証可能な制約（フィールド構造・文字数
上限）はここに置き、品質制約（捏造禁止・抽出方針）は ``prompts/agent_resume_import.md``
に置く（ADR-0010 / P4）。

v1 の抽出スコープは「見出し 3 フィールド + フラット職歴」（ADR-0024 / #527）。experiences
の深いネスト（clients / projects / periods / technology_stacks）は v1 では抽出しない。
文字数上限は保存スキーマ（``schemas/resume.py``）と揃える（フォーム注入後の保存契約）。
"""

from ..output_schema import SCOPE_FIELDS

# 上限の正本: 見出しはチャットの SCOPE_FIELDS（= schemas/resume.py と drift 検証済み）
MAX_CAREER_SUMMARY_LENGTH = SCOPE_FIELDS["career_summary"]["career_summary"]
MAX_SELF_PR_LENGTH = SCOPE_FIELDS["self_pr"]["self_pr"]

# experiences のフラットフィールド上限（schemas/resume.py の Experience と一致させる）
MAX_FULL_NAME_LENGTH = 120
MAX_COMPANY_LENGTH = 120
MAX_BUSINESS_DESCRIPTION_LENGTH = 200
MAX_DATE_LENGTH = 30
MAX_EXPERIENCE_DESCRIPTION_LENGTH = 4500

# 職歴の抽出件数上限（暴走・トークン浪費の防止）
MAX_EXPERIENCES = 30


def build_import_output_schema() -> dict:
    """PDF 抽出の出力 JSON Schema を構築する。

    LLM クライアントの tool 定義（``build_tool_definition``）にそのまま渡せる形。
    maxLength は API では強制されないため、上限超過の扱いは import_service のパース側が
    担う（二重防衛 / ADR-0010）。全フィールドは抽出できなければ空文字/空配列を許容する
    （部分抽出を許す。欠落はフォーム側で既存値保持 / #524）。
    """
    experience_item = {
        "type": "object",
        "properties": {
            "company": {
                "type": "string",
                "maxLength": MAX_COMPANY_LENGTH,
                "description": "在籍企業名。読み取れない場合は空文字",
            },
            "business_description": {
                "type": "string",
                "maxLength": MAX_BUSINESS_DESCRIPTION_LENGTH,
                "description": "企業の事業内容（1 行程度）。読み取れない場合は空文字",
            },
            "start_date": {
                "type": "string",
                "maxLength": MAX_DATE_LENGTH,
                "description": "在籍開始（例: 2020-04 / 2020年4月）。読み取れない場合は空文字",
            },
            "end_date": {
                "type": "string",
                "maxLength": MAX_DATE_LENGTH,
                "description": "在籍終了（在籍中は空文字）",
            },
            "description": {
                "type": "string",
                "maxLength": MAX_EXPERIENCE_DESCRIPTION_LENGTH,
                "description": "その企業での職務内容の記述。読み取れない場合は空文字",
            },
        },
        "required": [
            "company",
            "business_description",
            "start_date",
            "end_date",
            "description",
        ],
        "additionalProperties": False,
    }
    return {
        "type": "object",
        "properties": {
            "full_name": {
                "type": "string",
                "maxLength": MAX_FULL_NAME_LENGTH,
                "description": "氏名。読み取れない場合は空文字",
            },
            "career_summary": {
                "type": "string",
                "maxLength": MAX_CAREER_SUMMARY_LENGTH,
                "description": "職務要約。経歴書の該当箇所をそのまま整形した日本語",
            },
            "self_pr": {
                "type": "string",
                "maxLength": MAX_SELF_PR_LENGTH,
                "description": "自己PR。経歴書の該当箇所をそのまま整形した日本語",
            },
            "experiences": {
                "type": "array",
                "maxItems": MAX_EXPERIENCES,
                "items": experience_item,
                "description": "在籍企業ごとの職歴（新しい順は問わない。読み取れた分のみ）",
            },
        },
        "required": ["full_name", "career_summary", "self_pr", "experiences"],
        "additionalProperties": False,
    }
