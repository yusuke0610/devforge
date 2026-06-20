#!/usr/bin/env python3
"""THIRD_PARTY_LICENSES.md を再生成する。

DevForge が直接依存する OSS（自分で選んで入れたライブラリ）の一覧と
ライセンス・リンクを SSoT（web/package.json, backend/requirements.txt）から
収集し、ルートの THIRD_PARTY_LICENSES.md へ出力する。

- Frontend: web/node_modules/<pkg>/package.json を読む（オフライン・追加依存なし）
- Backend: importlib.metadata でインストール済みパッケージのメタデータを読む

依存を追加したら `make licenses` で再生成すること。
nix devshell 経由（backend/.venv の python）で実行する前提。
"""

from __future__ import annotations

import importlib.metadata as imd
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "web"
OUTPUT = ROOT / "THIRD_PARTY_LICENSES.md"

# requirements.txt のうち開発専用ツール（ランタイムには載らない）
BACKEND_DEV_TOOLS = {
    "pytest",
    "pytest-cov",
    "ruff",
    "black",
    "isort",
    "autopep8",
}


def _clean_url(url: str | None) -> str:
    """git+https://...​.git のような URL を https の閲覧用 URL に正規化する。"""
    if not url:
        return ""
    url = url.strip()
    # npm の repository ショートハンド (github:owner/repo, gitlab:..., bitbucket:...)
    m = re.match(r"^(github|gitlab|bitbucket):(.+)$", url)
    if m:
        host = {"github": "github.com", "gitlab": "gitlab.com", "bitbucket": "bitbucket.org"}[m.group(1)]
        url = f"https://{host}/{m.group(2)}"
    url = re.sub(r"^git\+", "", url)
    url = re.sub(r"^git://", "https://", url)
    url = re.sub(r"^ssh://git@", "https://", url)
    url = re.sub(r"\.git$", "", url)
    return url


def _npm_license(pkg: dict) -> str:
    """npm の package.json から SPDX ライセンス表記を取り出す。"""
    lic = pkg.get("license")
    if isinstance(lic, str):
        return lic
    if isinstance(lic, dict):
        return lic.get("type", "")
    # 旧形式: licenses: [{type, url}, ...]
    licenses = pkg.get("licenses")
    if isinstance(licenses, list):
        types = [x.get("type", "") for x in licenses if isinstance(x, dict)]
        return " OR ".join(t for t in types if t)
    return ""


def _npm_url(pkg: dict) -> str:
    homepage = pkg.get("homepage")
    if homepage:
        return _clean_url(homepage)
    repo = pkg.get("repository")
    if isinstance(repo, dict):
        return _clean_url(repo.get("url"))
    if isinstance(repo, str):
        return _clean_url(repo)
    return ""


def collect_npm(dep_names: list[str]) -> list[tuple[str, str, str, str]]:
    """(name, version, license, url) のリストを返す。"""
    rows: list[tuple[str, str, str, str]] = []
    for name in sorted(dep_names, key=str.lower):
        pkg_json = WEB / "node_modules" / name / "package.json"
        if not pkg_json.exists():
            rows.append((name, "—", "要確認 (未インストール)", f"https://www.npmjs.com/package/{name}"))
            continue
        pkg = json.loads(pkg_json.read_text(encoding="utf-8"))
        version = pkg.get("version", "—")
        lic = _npm_license(pkg) or "要確認"
        url = _npm_url(pkg) or f"https://www.npmjs.com/package/{name}"
        rows.append((name, version, lic, url))
    return rows


def _py_license(dist_name: str) -> tuple[str, str, str]:
    """(version, license, url) を importlib.metadata から取り出す。"""
    try:
        meta = imd.metadata(dist_name)
    except imd.PackageNotFoundError:
        return ("—", "要確認 (未インストール)", f"https://pypi.org/project/{dist_name}/")

    version = meta.get("Version", "—")

    # ライセンス解決の優先順位:
    #   1. License-Expression（PEP 639 の SPDX。最もクリーン）
    #   2. License Classifier の末尾セグメント
    #   3. License フィールド（短い場合のみ。全文が入っていることがあるため除外）
    expr = meta.get("License-Expression")
    classifiers = [
        c.split("::")[-1].strip()
        for c in meta.get_all("Classifier", [])
        if c.startswith("License")
    ]
    license_field = meta.get("License")
    if expr:
        lic = expr
    elif classifiers:
        lic = " / ".join(classifiers)
    elif license_field and "\n" not in license_field and len(license_field) <= 40:
        lic = license_field
    else:
        lic = "要確認 (プロジェクト参照)"

    # URL 解決: Home-page → Project-URL(Homepage/Source/Repository) → PyPI
    url = meta.get("Home-page") or ""
    if not url:
        for entry in meta.get_all("Project-URL", []):
            label, _, value = entry.partition(",")
            if label.strip().lower() in {"homepage", "source", "repository", "source code"}:
                url = value.strip()
                break
    if not url:
        url = f"https://pypi.org/project/{dist_name}/"
    return (version, lic, _clean_url(url))


def parse_requirements() -> list[str]:
    """requirements.txt から配布名（extras/version 指定を除いた名前）を抽出する。"""
    req = (ROOT / "backend" / "requirements.txt").read_text(encoding="utf-8")
    names: list[str] = []
    for line in req.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        # 例: uvicorn[standard]==0.34.0 / pydantic[email]==2.10.3 / stripe>=11,<13
        name = re.split(r"[\[<>=!~ ]", line, maxsplit=1)[0].strip()
        if name:
            names.append(name)
    return names


def md_table(rows: list[tuple[str, str, str, str]]) -> str:
    out = ["| ライブラリ | バージョン | ライセンス |", "|---|---|---|"]
    for name, version, lic, url in rows:
        link = f"[{name}]({url})" if url else name
        out.append(f"| {link} | {version} | {lic} |")
    return "\n".join(out)


def main() -> None:
    web_pkg = json.loads((WEB / "package.json").read_text(encoding="utf-8"))
    fe_runtime = collect_npm(list(web_pkg.get("dependencies", {})))
    fe_dev = collect_npm(list(web_pkg.get("devDependencies", {})))

    backend_names = parse_requirements()
    be_runtime: list[tuple[str, str, str, str]] = []
    be_dev: list[tuple[str, str, str, str]] = []
    for name in sorted(backend_names, key=str.lower):
        version, lic, url = _py_license(name)
        row = (name, version, lic, url)
        (be_dev if name in BACKEND_DEV_TOOLS else be_runtime).append(row)

    doc = f"""# サードパーティライセンス / 使用 OSS

DevForge は多くのオープンソースソフトウェア（OSS）に支えられています。
本ファイルは DevForge が **直接依存している** OSS の一覧と、それぞれのライセンス・
配布元へのリンクをまとめたものです（謝辞および attribution を兼ねます）。

- ここに列挙した各 OSS の著作権・権利は、それぞれの著作権者に帰属します。
- 一覧は直接依存（自分で選んで導入したライブラリ）が対象です。推移的依存は含みません。
- ライセンス種別は各パッケージのメタデータから自動収集しています（手書きの推測ではありません）。
- **依存を追加・更新したら `make licenses` で本ファイルを再生成してください。** 手動編集は不要です。

> 注: 本ファイルは依存 OSS のライセンス表記であり、DevForge 本体のライセンスを定めるものではありません。

## Frontend（ランタイム / バンドルに同梱）

{md_table(fe_runtime)}

## Frontend（ビルド・開発ツール）

{md_table(fe_dev)}

## Backend（ランタイム）

{md_table(be_runtime)}

## Backend（開発ツール）

{md_table(be_dev)}
"""
    OUTPUT.write_text(doc, encoding="utf-8")
    print(f"生成しました: {OUTPUT.relative_to(ROOT)}")
    print(
        f"  Frontend runtime={len(fe_runtime)} dev={len(fe_dev)} / "
        f"Backend runtime={len(be_runtime)} dev={len(be_dev)}"
    )


if __name__ == "__main__":
    main()
