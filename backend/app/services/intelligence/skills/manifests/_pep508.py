"""PEP 508 依存指定から package 名だけを取り出すヘルパ（pypi 系パーサ共用）。"""

import re

# 先頭の package 名（PEP 508）。extras / バージョン / 環境マーカーは名前の後に続く。
_NAME_RE = re.compile(r"^\s*([A-Za-z0-9][A-Za-z0-9._-]*)")
# URL / VCS 直指定（https://... / git+https://... 等）。先頭の "https" 等を
# package 名と誤認しないよう、名前抽出前に弾く。
_DIRECT_REF_PREFIX_RE = re.compile(r"^\s*(?:https?://|git\+|ssh://|file:)", re.IGNORECASE)


def extract_package_name(spec: str) -> str | None:
    """``"requests[security] >=2,<3 ; python_version>'3.8'"`` → ``"requests"``。

    名前を取り出せない（URL 直指定・空行など）場合は ``None``。
    """
    if not spec:
        return None
    # URL / VCS 直指定は名前を持たないため None（"https" 等の誤抽出を防ぐ）。
    if _DIRECT_REF_PREFIX_RE.match(spec):
        return None
    match = _NAME_RE.match(spec)
    if not match:
        return None
    return match.group(1)
