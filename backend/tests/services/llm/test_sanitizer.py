"""sanitizer モジュールのユニットテスト。"""

from app.services.llm.sanitizer import (
    SanitizeContext,
    sanitize_project_name,
    sanitize_text,
    strip_prohibited_fields,
)

# ============================================================
# strip_prohibited_fields
# ============================================================


def test_prohibited_fields_are_stripped():
    """strip_prohibited_fields が C分類フィールドを除去する。

    住所・郵便番号・生年月日・電話番号・名前ふりがな・写真はシステム上入力されないため除外対象外。
    """
    data = {
        "full_name": "山田太郎",
        "email": "yamada@example.com",
        "motivation": "貢献したい",
        "personal_preferences": "朝型",
        "username": "yamada_t",
        # A分類（残るべきフィールド）
        "skills": ["Python", "FastAPI"],
        "repos_analyzed": 10,
    }
    result = strip_prohibited_fields(data)

    prohibited = {
        "full_name",
        "email",
        "motivation",
        "personal_preferences",
        "username",
    }
    for field in prohibited:
        assert field not in result, f"C分類フィールド '{field}' が残っている"

    assert "skills" in result
    assert "repos_analyzed" in result


def test_strip_prohibited_fields_returns_new_dict():
    """strip_prohibited_fields は元の dict を変更せず新しい dict を返す。"""
    data = {"username": "test", "repos_analyzed": 5}
    result = strip_prohibited_fields(data)
    assert "username" not in result
    assert "username" in data  # 元は変更されない


# ============================================================
# sanitize_project_name
# ============================================================


def test_project_name_is_anonymized():
    """sanitize_project_name が raw の案件名をラベルに変換する。"""
    context = SanitizeContext()
    raw_name = "ネット銀行基幹システム刷新"
    label = sanitize_project_name(raw_name, context)

    assert label != raw_name
    assert raw_name not in label
    assert label == "[案件A]"


# ============================================================
# sanitize_text
# ============================================================


def test_career_summary_is_masked():
    """career_summary 内の既知企業名・案件名がマスキングされる。"""
    context = SanitizeContext()
    context.register_company("株式会社サンプル")
    context.register_project("決済基盤刷新プロジェクト")

    summary = "株式会社サンプルに勤務し、決済基盤刷新プロジェクトを担当しました。"
    masked = sanitize_text(summary, context)

    assert "株式会社サンプル" not in masked
    assert "決済基盤刷新プロジェクト" not in masked
    assert "[企業A]" in masked
    assert "[案件A]" in masked


def test_sanitize_text_no_op_on_empty_context():
    """空のコンテキストでは sanitize_text はテキストをそのまま返す。"""
    context = SanitizeContext()
    text = "これはテストテキストです。"
    assert sanitize_text(text, context) == text


def test_sanitize_text_empty_string():
    """sanitize_text に空文字列を渡しても例外が発生しない。"""
    context = SanitizeContext()
    assert sanitize_text("", context) == ""


def test_sanitize_text_none_input():
    """sanitize_text に None を渡しても例外が発生しない。"""
    context = SanitizeContext()
    assert sanitize_text(None, context) == ""


def test_sanitize_text_longer_name_takes_priority():
    """長い名前から置換することで短い名前の部分一致誤変換を防ぐ。"""
    context = SanitizeContext()
    context.register_company("株式会社テスト")
    context.register_company("株式会社テストグループ")

    text = "株式会社テストグループの案件を担当した。"
    masked = sanitize_text(text, context)

    # 「株式会社テスト」で途中まで置換され「グループ」が残らないことを確認
    assert "株式会社テストグループ" not in masked
    # 長い名前のラベルで正しく置換されていること
    assert "[企業B]" in masked


# ============================================================
# SanitizeContext 一貫性
# ============================================================


def test_context_consistency():
    """同一 SanitizeContext 内で同じ企業名は同じラベルに変換される。"""
    context = SanitizeContext()
    label1 = context.register_company("株式会社テスト")
    label2 = context.register_company("株式会社テスト")

    assert label1 == label2
    assert label1 == "[企業A]"

    label3 = context.register_company("別会社株式会社")
    assert label3 == "[企業B]"
    assert label1 != label3


def test_context_separate_categories():
    """異なるカテゴリは独立した採番を持つ。"""
    context = SanitizeContext()
    company_label = context.register_company("株式会社テスト")
    customer_label = context.register_customer("株式会社テスト")

    # 同じ raw 名でもカテゴリが違えば別ラベル
    assert company_label == "[企業A]"
    assert customer_label == "[顧客A]"


def test_context_empty_name_not_registered():
    """空文字はコンテキストに登録されない。"""
    context = SanitizeContext()
    result = context.register_company("")
    assert result == ""
    assert len(context.companies) == 0
