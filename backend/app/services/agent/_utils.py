"""services/agent/ 配下の複数モジュールで共有する純粋関数。"""


def strip_code_fence(raw: str) -> str:
    """LLM 応答テキストからコードフェンス（```json ... ``` 等）を剥がす。

    Ollama など tool use ではないローカル実装は、構造化出力指定後もコードフェンスを
    付ける場合がある。JSON mode への依存ではなく、ローカル開発用の耐性として残す
    （chat_service / resume_draft / resume_import / skill_display の各 ``_parse_*`` で共通）。
    """
    text = raw.strip()
    if text.startswith("```"):
        text = text.strip("`")
        text = text.removeprefix("json").strip()
    return text
