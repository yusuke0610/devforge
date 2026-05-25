import pytest
from app.utils import prompt_loader
from app.utils.prompt_loader import load_prompt


def test_load_prompt_success(tmp_path, monkeypatch):
    """プロンプトファイルが正常に読み込めること（前後の空白は除去される）。"""
    # 実プロンプトは将来の LLM 機能向けに空のため、テスト用ファイルを一時生成して検証する
    prompt_file = tmp_path / "sample.md"
    prompt_file.write_text("  GitHub 分析プロンプト  \n", encoding="utf-8")
    monkeypatch.setattr(prompt_loader, "PROMPTS_DIR", tmp_path)

    content = load_prompt("sample.md")
    assert content == "GitHub 分析プロンプト"


def test_load_prompt_not_found():
    """存在しないファイルを指定した場合に FileNotFoundError が発生すること。"""
    with pytest.raises(FileNotFoundError):
        load_prompt("non_existent_file.md")
