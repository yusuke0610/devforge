"""services/agent/ 配下の複数モジュールで共有する純粋関数。"""

import re

_FENCE_RE = re.compile(r"^```[A-Za-z0-9_+-]*\s*\n?(.*?)\n?```$", re.DOTALL)


def strip_code_fence(raw: str) -> str:
    """LLM 応答テキストからコードフェンス（```json ... ``` 等）を剥がす。

    Ollama など tool use ではないローカル実装は、構造化出力指定後もコードフェンスを
    付ける場合がある。JSON mode への依存ではなく、ローカル開発用の耐性として残す
    （chat_service / resume_draft / resume_import / skill_display の各 ``_parse_*`` で共通）。
    言語タグの大小文字・種類を問わず、閉じフェンスまでを厳密に一致させて中身だけを返す
    （素朴な strip("`") は末尾の無関係なバッククォートまで削ってしまうため使わない）。
    """
    text = raw.strip()
    match = _FENCE_RE.match(text)
    return match.group(1).strip() if match else text
