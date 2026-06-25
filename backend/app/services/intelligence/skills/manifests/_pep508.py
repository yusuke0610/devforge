"""PEP 508 依存指定から package 名だけを取り出すヘルパ（pypi 系パーサ共用）。"""

import re

# 先頭の package 名（PEP 508）。extras / バージョン / 環境マーカーは名前の後に続く。
_NAME_RE = re.compile(r"^\s*([A-Za-z0-9][A-Za-z0-9._-]*)")


def extract_package_name(spec: str) -> str | None:
    """``"requests[security] >=2,<3 ; python_version>'3.8'"`` → ``"requests"``。

    名前を取り出せない（URL 直指定・空行など）場合は ``None``。
    """
    if not spec:
        return None
    match = _NAME_RE.match(spec)
    if not match:
        return None
    return match.group(1)
