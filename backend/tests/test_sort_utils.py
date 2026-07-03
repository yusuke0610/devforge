from datetime import date
from types import SimpleNamespace

from app.services.shared.sort_utils import sort_by_date_asc, sort_by_date_desc, sort_by_period_desc


def _exp(start: str, end: str | None = None) -> dict:
    """テスト用の経歴 dict を生成する。"""
    return {
        "start_date_value": date.fromisoformat(f"{start}-01"),
        "end_date_value": date.fromisoformat(f"{end}-01") if end else None,
    }


def test_current_job_comes_first():
    """end_date が None（現在在籍中）の項目が最上位に来ること。"""
    items = [
        _exp("2020-01", "2022-06"),
        _exp("2023-01"),  # 現在在籍中
    ]
    result = sort_by_period_desc(items)
    assert result[0]["end_date_value"] is None
    assert result[1]["end_date_value"] is not None


def test_multiple_current_jobs_sorted_by_start_desc():
    """end_date が None の項目が複数ある場合、start_date DESC でソートされること。"""
    items = [
        _exp("2020-01"),
        _exp("2023-04"),
        _exp("2021-06"),
    ]
    result = sort_by_period_desc(items)
    starts = [item["start_date_value"] for item in result]
    assert starts == sorted(starts, reverse=True)


def test_end_date_desc():
    """退職済み（end あり）が end_date 降順に並ぶこと。

    start 降順と end 降順が食い違うデータ＋位置ベース assert を使い、end を無視して
    start / None で並べる sort_key の実装退行（end_key 破壊・end を None 化する変異等）を
    検出する。以前は start 順と end 順が偶然一致するデータだったため、これらの変異が
    生き残っていた（ミューテーションテストで検出）。"""
    old_start_new_end = _exp("2010-01", "2023-01")  # 最古 start・最新 end
    new_start_old_end = _exp("2018-01", "2019-01")  # 新しい start・古い end
    result = sort_by_period_desc([new_start_old_end, old_start_new_end])
    # end 降順なら最新 end(2023) を持つ old_start_new_end が先頭に来る。
    # end を見ない実装は start 降順で new_start_old_end を先頭にするため、位置で検出できる。
    assert result[0] is old_start_new_end
    assert result[1] is new_start_old_end


def test_empty_list():
    """空リストでエラーにならないこと。"""
    assert sort_by_period_desc([]) == []


def test_sort_by_attribute_access_objects():
    """dict でなく属性アクセス（ORM 行相当）でも並べ替えできること。

    本番では ORM オブジェクトを渡すため、_get の getattr 分岐（dict 以外）が実経路。
    ユニットテストは dict 入力に偏り、この分岐が未検証だった（ミューテーションテストで検出）。
    end 属性を持たないオブジェクトは None（現在在籍中）扱いになる getattr の
    デフォルトフォールバックも併せて検証する。"""
    past = SimpleNamespace(start_date_value=date(2010, 1, 1), end_date_value=date(2020, 1, 1))
    current = SimpleNamespace(start_date_value=date(2015, 1, 1))  # end_date_value 属性なし
    result = sort_by_period_desc([past, current])
    assert result[0] is current  # end 欠損 → None 扱いで最上位
    assert result[1] is past


def test_with_string_dates():
    """文字列日付（YYYY-MM）にも対応すること。"""
    items = [
        {"start_date": "2018-01", "end_date": "2020-03"},
        {"start_date": "2023-01", "end_date": None},
        {"start_date": "2020-04", "end_date": "2023-12"},
    ]
    result = sort_by_period_desc(items, start_key="start_date", end_key="end_date")
    # 現在在籍中が最上位
    assert result[0]["end_date"] is None
    # 次に end_date が新しい順
    assert result[1]["end_date"] == "2023-12"
    assert result[2]["end_date"] == "2020-03"


# ===== sort_by_date_desc テスト =====


def _qual(acquired: str | None) -> dict:
    """テスト用の資格 dict を生成する。"""
    return {
        "acquired_date_value": date.fromisoformat(acquired) if acquired else None,
        "name": f"資格_{acquired}",
    }


def test_date_desc_none_last():
    """日付が None の項目が最下位に来ること。"""
    items = [_qual(None), _qual("2023-06-01"), _qual("2020-01-15")]
    result = sort_by_date_desc(items)
    assert result[-1]["acquired_date_value"] is None
    assert result[0]["acquired_date_value"] == date(2023, 6, 1)


def test_date_desc_empty():
    """空リストでエラーにならないこと。"""
    assert sort_by_date_desc([]) == []


def test_date_desc_with_full_string_dates():
    """フル日付文字列（YYYY-MM-DD, 長さ10）を _to_date のフル解析分岐で処理できること。
    YYYY-MM（長さ7）専用の分岐と異なり、len!=7 の else 側（date.fromisoformat(value)）を
    通す唯一のテスト。この分岐のミューテーションを撃破するため長さ10の文字列を使う。"""
    items = [
        {"date": "2020-03-15", "name": "A"},
        {"date": "2023-06-01", "name": "B"},
    ]
    result = sort_by_date_desc(items, date_key="date")
    assert result[0]["name"] == "B"
    assert result[1]["name"] == "A"


# ===== sort_by_date_asc テスト =====


def _history(occurred: str | None) -> dict:
    """テスト用の学歴/職歴 dict を生成する。"""
    return {
        "occurred_on_value": date.fromisoformat(f"{occurred}-01") if occurred else None,
        "name": f"項目_{occurred}",
    }


def test_date_asc_sorted():
    """日付昇順でソートされること。"""
    items = [_history("2020-03"), _history("2015-04"), _history("2018-03")]
    result = sort_by_date_asc(items)
    dates = [item["occurred_on_value"] for item in result]
    assert dates == sorted(dates)


def test_date_asc_none_last():
    """日付が None の項目が最下位に来ること。"""
    items = [_history(None), _history("2020-03"), _history("2015-04")]
    result = sort_by_date_asc(items)
    assert result[-1]["occurred_on_value"] is None
    assert result[0]["occurred_on_value"] == date(2015, 4, 1)


def test_date_asc_empty():
    """空リストでエラーにならないこと。"""
    assert sort_by_date_asc([]) == []
