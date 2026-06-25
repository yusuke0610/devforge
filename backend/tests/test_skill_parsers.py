"""manifest パーサ群のテスト（ADR-0016 declare / D7）。"""

from app.services.intelligence.skills.manifests import parse_manifest
from app.services.intelligence.skills.manifests.cargo_toml import CargoTomlParser
from app.services.intelligence.skills.manifests.go_mod import GoModParser
from app.services.intelligence.skills.manifests.package_json import PackageJsonParser
from app.services.intelligence.skills.manifests.pyproject import PyprojectParser
from app.services.intelligence.skills.manifests.requirements_txt import (
    RequirementsTxtParser,
)


def _by_name(declarations) -> dict:
    return {d.name: d for d in declarations}


def test_go_mod_block_marks_indirect() -> None:
    """go.mod の `// indirect` は indirect、それ以外は direct になること。"""
    content = (
        "module example.com/app\n\n"
        "go 1.21\n\n"
        "require (\n"
        "    github.com/gin-gonic/gin v1.9.1\n"
        "    github.com/bytedance/sonic v1.10.0 // indirect\n"
        ")\n"
    )
    result = _by_name(GoModParser().parse(content))
    assert result["github.com/gin-gonic/gin"].dependency_kind == "direct"
    assert result["github.com/gin-gonic/gin"].version_spec == "v1.9.1"
    assert result["github.com/bytedance/sonic"].dependency_kind == "indirect"
    assert all(d.ecosystem == "go" for d in result.values())


def test_go_mod_single_line_require() -> None:
    """単行 require も拾えること。"""
    result = _by_name(GoModParser().parse("require github.com/foo/bar v1.0.0\n"))
    assert result["github.com/foo/bar"].dependency_kind == "direct"


def test_package_json_dependency_kinds() -> None:
    """dependencies/devDependencies/peerDependencies の kind が分類されること。"""
    content = """
    {
      "dependencies": {"react": "^18.0.0"},
      "devDependencies": {"jest": "^29.0.0"},
      "peerDependencies": {"react-dom": "^18.0.0"}
    }
    """
    result = _by_name(PackageJsonParser().parse(content))
    assert result["react"].dependency_kind == "direct"
    assert result["react"].ecosystem == "npm"
    assert result["jest"].dependency_kind == "dev"
    assert result["react-dom"].dependency_kind == "peer"


def test_package_json_broken_returns_empty() -> None:
    """壊れた JSON は例外を投げず空リストを返すこと。"""
    assert PackageJsonParser().parse("{not json") == []


def test_pyproject_pep621_and_build_system() -> None:
    """PEP 621 の dependencies/optional/build-system を分類すること。"""
    content = """
[build-system]
requires = ["hatchling>=1.0"]

[project]
name = "demo"
dependencies = ["requests>=2.0", "httpx[http2]>=0.27"]

[project.optional-dependencies]
dev = ["pytest>=8"]
postgres = ["psycopg2-binary"]
"""
    result = _by_name(PyprojectParser().parse(content))
    assert result["requests"].dependency_kind == "direct"
    assert result["httpx"].dependency_kind == "direct"  # extras は名前のみ抽出
    assert result["pytest"].dependency_kind == "dev"  # dev グループ
    assert result["psycopg2-binary"].dependency_kind == "direct"  # 非 dev extras
    assert result["hatchling"].dependency_kind == "build"
    assert all(d.ecosystem == "pypi" for d in result.values())


def test_pyproject_poetry() -> None:
    """Poetry 形式の dependencies / group.dev を分類し python を除外すること。"""
    content = """
[tool.poetry.dependencies]
python = "^3.12"
fastapi = "^0.110"

[tool.poetry.group.dev.dependencies]
ruff = "^0.4"
"""
    result = _by_name(PyprojectParser().parse(content))
    assert "python" not in result
    assert result["fastapi"].dependency_kind == "direct"
    assert result["ruff"].dependency_kind == "dev"


def test_requirements_txt_skips_options_and_comments() -> None:
    """コメント・オプション行をスキップし、名前を抽出すること。"""
    content = (
        "# core deps\n"
        "requests>=2.0\n"
        "django==4.2  ; python_version>'3.10'\n"
        "-r other.txt\n"
        "-e .\n"
        "\n"
        "flask[async]\n"
    )
    result = _by_name(RequirementsTxtParser().parse(content))
    assert set(result) == {"requests", "django", "flask"}
    assert all(d.dependency_kind == "direct" for d in result.values())


def test_cargo_toml_sections() -> None:
    """Cargo.toml の各セクションを分類し、table 値の version を拾うこと。"""
    content = """
[dependencies]
serde = "1.0"
tokio = { version = "1", features = ["full"] }

[dev-dependencies]
criterion = "0.5"

[build-dependencies]
cc = "1.0"
"""
    result = _by_name(CargoTomlParser().parse(content))
    assert result["serde"].dependency_kind == "direct"
    assert result["tokio"].dependency_kind == "direct"
    assert result["tokio"].version_spec == "1"
    assert result["criterion"].dependency_kind == "dev"
    assert result["cc"].dependency_kind == "build"
    assert all(d.ecosystem == "cargo" for d in result.values())


def test_registry_dispatches_by_filename() -> None:
    """parse_manifest がファイル名でパーサを選び、未対応は空を返すこと。"""
    assert parse_manifest("go.mod", "require x/y v1.0.0\n")[0].ecosystem == "go"
    assert parse_manifest("unknown.txt", "whatever") == []
