"""app/prompts/ 配下の MD ファイルを読み込むユーティリティ。"""

from pathlib import Path

# backend/app/utils/prompt_loader.py から見て backend/app/prompts を指すように修正
PROMPTS_DIR = Path(__file__).parent.parent / "prompts"


def load_prompt(filename: str) -> str:
    """app/prompts/ 配下の MD ファイルを読み込んで文字列で返す。

    呼び出し時に都度ファイルを読み込む（キャッシュなし）。

    Args:
        filename: 拡張子込みのファイル名（例: "github_trend.md"）

    Returns:
        MD ファイルの内容文字列（前後の空白・改行を除去済み）

    Raises:
        FileNotFoundError: 指定ファイルが存在しない場合
    """
    path = PROMPTS_DIR / filename
    if not path.exists():
        raise FileNotFoundError(f"プロンプトファイルが見つかりません: {path}")
    return path.read_text(encoding="utf-8").strip()
