from app.core.messages import get_error, get_notification, get_success, load_messages


def test_key_lookup_returns_message() -> None:
    """キー引きで messages.json の文言が返ること（アクセサごとに代表 1 件）。

    文言の逐語 pin を全キーに置くと文言変更のたびに壊れる割に検出力が無いため、
    ここではキー→文言の解決経路だけを確認する。
    """
    load_messages()

    assert get_error("auth.login_required") == "ログインが必要です。"
    assert get_notification("github_link", "completed") == "GitHub連携が完了しました"


def test_get_error_formats_placeholders() -> None:
    load_messages()

    assert get_error("validation.required_field", field="メールアドレス") == "メールアドレスは必須です。"


def test_get_success_formats_placeholders() -> None:
    load_messages()

    assert get_success("document.saved", document="職務経歴書") == "職務経歴書を保存しました。"


def test_missing_message_key_falls_back_to_key() -> None:
    load_messages()

    assert get_error("unknown.category.key") == "unknown.category.key"


def test_master_data_placeholder() -> None:
    """master_data は {item}、document は {document} で統一されている。"""
    load_messages()

    assert get_error("master_data.not_found", item="資格マスタ") == "資格マスタが見つかりません。"
    assert get_error("document.not_found", document="基本情報") == "基本情報が見つかりません。"
