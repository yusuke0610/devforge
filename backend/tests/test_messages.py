from app.core.messages import get_error, get_notification, get_success, load_messages


def test_get_notification_returns_message() -> None:
    load_messages()

    assert (
        get_notification("github_link", "completed") == "GitHub連携が完了しました"
    )
    assert get_notification("github_link", "failed") == "GitHub連携に失敗しました"


def test_get_error_returns_message_by_key() -> None:
    load_messages()

    assert get_error("auth.login_required") == "ログインが必要です。"


def test_get_error_formats_placeholders() -> None:
    load_messages()

    assert get_error("validation.required_field", field="メールアドレス") == "メールアドレスは必須です。"


def test_get_success_formats_placeholders() -> None:
    load_messages()

    assert get_success("document.saved", document="職務経歴書") == "職務経歴書を保存しました。"


def test_missing_message_key_falls_back_to_key() -> None:
    load_messages()

    assert get_error("unknown.category.key") == "unknown.category.key"


def test_validation_end_date_required() -> None:
    load_messages()

    assert get_error("validation.end_date_required") == "在職中でない場合は終了年月を入力してください。"


def test_master_data_placeholder() -> None:
    """master_data は {item}、document は {document} で統一されている。"""
    load_messages()

    assert get_error("master_data.not_found", item="資格マスタ") == "資格マスタが見つかりません。"
    assert get_error("document.not_found", document="基本情報") == "基本情報が見つかりません。"
