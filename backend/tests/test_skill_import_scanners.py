"""import スキャナ（verify / ADR-0016 D6）の単体テスト。

エコシステム別の import 抽出（scan）と、宣言 package との照合（matches）を検証する。
機械的照合で当たらない既知の乖離（PyYAML→yaml 等）は内部マスタで補正されること（#477）、
マスタ未収録の乖離は依然 false negative になることの両方を明示的に固定する。
"""

from app.services.intelligence.skills.imports import (
    SOURCE_EXTENSIONS,
    scanner_for_ecosystem,
    scanner_for_extension,
)
from app.services.intelligence.skills.imports.go import GoImportScanner
from app.services.intelligence.skills.imports.js_ts import JsTsImportScanner
from app.services.intelligence.skills.imports.python import PythonImportScanner
from app.services.intelligence.skills.imports.rust import RustImportScanner

# ── registry ────────────────────────────────────────────────────────────


def test_source_extensions_cover_all_ecosystems():
    """Tier1 全 4 エコシステムの代表拡張子が登録されていること。"""
    for ext in (".py", ".ts", ".go", ".rs"):
        assert ext in SOURCE_EXTENSIONS


def test_scanner_for_extension_dispatches_by_suffix():
    for path, ecosystem in (
        ("a/b/main.py", "pypi"),
        ("src/index.tsx", "npm"),
        ("cmd/main.go", "go"),
        ("src/lib.rs", "cargo"),
    ):
        scanner = scanner_for_extension(path)
        assert scanner is not None
        assert scanner.ecosystem == ecosystem
    assert scanner_for_extension("README.md") is None
    assert scanner_for_extension("no_extension") is None


def test_scanner_for_ecosystem_lookup():
    assert isinstance(scanner_for_ecosystem("pypi"), PythonImportScanner)
    assert scanner_for_ecosystem("unknown") is None


# ── Python ──────────────────────────────────────────────────────────────


class TestPythonScanner:
    scanner = PythonImportScanner()

    def test_extracts_top_level_modules(self):
        src = "import os\nimport fastapi\nfrom sqlalchemy.orm import Session\n"
        assert self.scanner.scan(src) == {"os", "fastapi", "sqlalchemy"}

    def test_indented_imports(self):
        src = "def f():\n    import httpx\n"
        assert "httpx" in self.scanner.scan(src)

    def test_matches_with_dash_to_underscore(self):
        # canonical（PEP503）は小文字・ダッシュ。import 名はアンダースコア。
        assert self.scanner.matches("google-cloud-storage", {"google_cloud_storage"})

    def test_matches_divergent_import_name_via_alias_master(self):
        # 配布名≠import名の既知乖離は内部マスタ（pypi_import_aliases.json）で昇格する（#477 / D3・D4）。
        assert self.scanner.matches("pyyaml", {"yaml"}) is True
        assert self.scanner.matches("pillow", {"pil"}) is True
        assert self.scanner.matches("beautifulsoup4", {"bs4"}) is True
        assert self.scanner.matches("scikit-learn", {"sklearn"}) is True
        assert self.scanner.matches("opencv-python", {"cv2"}) is True

    def test_known_alias_not_imported_stays_false(self):
        # マスタ収録済みでも実 import が無ければ昇格しない（過剰昇格の防止）。
        assert self.scanner.matches("pyyaml", {"requests"}) is False

    def test_unknown_divergence_still_false(self):
        # マスタ未収録の乖離は依然として昇格漏れ（false negative）を受容する。
        assert self.scanner.matches("some-obscure-dist", {"obscuremod"}) is False


# ── JS/TS ───────────────────────────────────────────────────────────────


class TestJsTsScanner:
    scanner = JsTsImportScanner()

    def test_extracts_import_and_require(self):
        src = (
            'import React from "react";\n'
            "const x = require('lodash');\n"
            'import { z } from "@scope/pkg";\n'
        )
        assert self.scanner.scan(src) == {"react", "lodash", "@scope/pkg"}

    def test_subpath_is_reduced_to_package(self):
        src = 'import s from "date-fns/locale";\n'
        assert self.scanner.scan(src) == {"date-fns"}

    def test_relative_imports_excluded(self):
        src = 'import a from "./local";\nimport b from "../up";\n'
        assert self.scanner.scan(src) == set()

    def test_matches_exact_including_scope(self):
        assert self.scanner.matches("@scope/pkg", {"@scope/pkg"})
        assert self.scanner.matches("react", {"preact"}) is False

    def test_ignores_imports_in_comments(self):
        """コメント内の import/require は誤検出しないこと（CodeRabbit 指摘）。"""
        src = (
            '// require("commented-out")\n'
            "/* import x from 'block-commented' */\n"
            'import real from "real-pkg";\n'
        )
        assert self.scanner.scan(src) == {"real-pkg"}

    def test_line_comment_strip_preserves_url_imports(self):
        """行コメント除去が URL（http://）入り specifier を壊さないこと。"""
        src = 'import a from "https://esm.sh/preact";\n'
        # specifier は相対でないため preserve され、package 名として URL 先頭が拾われる
        assert self.scanner.scan(src) != set()


# ── Go ──────────────────────────────────────────────────────────────────


class TestGoScanner:
    scanner = GoImportScanner()

    def test_extracts_block_and_single_imports(self):
        src = (
            'import "fmt"\n'
            "import (\n"
            '    "github.com/gin-gonic/gin"\n'
            '    h "github.com/foo/bar/http"\n'
            ")\n"
        )
        got = self.scanner.scan(src)
        assert "fmt" in got
        assert "github.com/gin-gonic/gin" in got
        assert "github.com/foo/bar/http" in got

    def test_matches_module_and_subpackage_prefix(self):
        imported = {"github.com/foo/bar/http"}
        assert self.scanner.matches("github.com/foo/bar", imported)
        assert self.scanner.matches("github.com/foo/ba", imported) is False


# ── Rust ────────────────────────────────────────────────────────────────


class TestRustScanner:
    scanner = RustImportScanner()

    def test_extracts_use_and_extern_crate(self):
        src = "use serde_json::Value;\nextern crate tokio;\nuse crate::local;\n"
        got = self.scanner.scan(src)
        assert "serde_json" in got
        assert "tokio" in got
        # crate/self/super/std 等は外部クレートでないため除外
        assert "crate" not in got

    def test_matches_with_dash_to_underscore(self):
        assert self.scanner.matches("serde-json", {"serde_json"})
        assert self.scanner.matches("serde-json", {"serde"}) is False

    def test_extracts_pub_use_reexports(self):
        """pub use / pub(crate) use の re-export も外部クレート使用として拾うこと（指摘）。"""
        src = "pub use serde::Serialize;\npub(crate) use tokio::task;\n"
        got = self.scanner.scan(src)
        assert "serde" in got
        assert "tokio" in got
