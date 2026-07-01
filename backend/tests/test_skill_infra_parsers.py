"""IaC（Terraform）パーサのテスト（ADR-0016 D10）。"""

from app.services.intelligence.skills.infra import (
    INFRA_EXTENSIONS,
    parse_infra,
    parser_for_path,
)
from app.services.intelligence.skills.infra.terraform import TerraformParser


def _providers(declarations) -> set:
    """resource_type を持たない（provider 宣言）の provider 名集合。"""
    return {d.provider for d in declarations if d.resource_type is None}


def _resource_types(declarations) -> set:
    return {d.resource_type for d in declarations if d.resource_type is not None}


def test_provider_block_detected() -> None:
    """provider "aws" {} ブロックから provider を検出すること。"""
    content = 'provider "aws" {\n  region = "ap-northeast-1"\n}\n'
    decls = TerraformParser().parse(content)
    assert _providers(decls) == {"aws"}


def test_resource_block_derives_provider_from_prefix() -> None:
    """resource "<type>" から resource_type と、接頭辞由来の provider を検出すること。"""
    content = (
        'resource "aws_s3_bucket" "assets" {\n  bucket = "x"\n}\n'
        'resource "google_storage_bucket" "b" {\n}\n'
    )
    decls = TerraformParser().parse(content)
    assert _resource_types(decls) == {"aws_s3_bucket", "google_storage_bucket"}
    # resource 宣言は provider をタイプ接頭辞から導出する。
    by_type = {d.resource_type: d for d in decls if d.resource_type}
    assert by_type["aws_s3_bucket"].provider == "aws"
    assert by_type["google_storage_bucket"].provider == "google"
    assert all(d.tool == "terraform" for d in decls)


def test_required_providers_uses_source_last_segment() -> None:
    """required_providers の source 末尾セグメントを provider 名に採ること。"""
    content = (
        "terraform {\n"
        "  required_providers {\n"
        "    aws = {\n"
        '      source  = "hashicorp/aws"\n'
        '      version = "~> 5.0"\n'
        "    }\n"
        "    cloudflare = {\n"
        '      source = "cloudflare/cloudflare"\n'
        "    }\n"
        "  }\n"
        "}\n"
    )
    decls = TerraformParser().parse(content)
    assert _providers(decls) == {"aws", "cloudflare"}


def test_required_providers_oneline_entry() -> None:
    """ワンライナーの required_providers エントリも拾えること。"""
    content = (
        "terraform {\n"
        "  required_providers {\n"
        '    google = { source = "hashicorp/google" }\n'
        "  }\n"
        "}\n"
    )
    decls = TerraformParser().parse(content)
    assert _providers(decls) == {"google"}


def test_required_providers_without_source_falls_back_to_local_name() -> None:
    """source が無いエントリは local 名を provider 名に採ること。"""
    content = (
        "terraform {\n"
        "  required_providers {\n"
        '    mycloud = { version = "1.0" }\n'
        "  }\n"
        "}\n"
    )
    decls = TerraformParser().parse(content)
    assert _providers(decls) == {"mycloud"}


def test_dynamic_constructs_are_ignored() -> None:
    """module / count / for_each 等の動的生成は静的列挙しない（D10 スコープ外）。"""
    content = (
        'module "vpc" {\n  source = "terraform-aws-modules/vpc/aws"\n}\n'
        'resource "aws_instance" "web" {\n  count = 3\n}\n'
    )
    decls = TerraformParser().parse(content)
    # module は無視、resource は静的に 1 件だけ拾う（count で増える分は列挙しない）。
    assert _resource_types(decls) == {"aws_instance"}
    assert all("module" not in (d.resource_type or "") for d in decls)


def test_broken_hcl_is_best_effort() -> None:
    """途中で切れた HCL でも取れた分を返し、例外を投げないこと。"""
    content = (
        'provider "aws" {\n  region = "x"\n}\n'
        'resource "aws_s3_bucket" "a" {\n'  # 閉じ括弧なしで終端
    )
    decls = TerraformParser().parse(content)
    assert "aws" in _providers(decls)
    assert "aws_s3_bucket" in _resource_types(decls)


def test_comments_are_skipped() -> None:
    """コメント行はブロックとして誤検出しないこと。"""
    content = (
        '# provider "fake" {\n'
        '// resource "fake_thing" "x" {\n'
        'provider "azurerm" {\n}\n'
    )
    decls = TerraformParser().parse(content)
    assert _providers(decls) == {"azurerm"}
    assert _resource_types(decls) == set()


def test_registry_dispatches_by_extension() -> None:
    """.tf は Terraform パーサへ振り分け、非対応拡張子は空を返すこと。"""
    assert ".tf" in INFRA_EXTENSIONS
    assert parser_for_path("infra/main.tf") is not None
    assert parser_for_path("README.md") is None
    assert parse_infra("infra/main.tf", 'provider "aws" {\n}\n')
    assert parse_infra("main.py", 'provider "aws" {\n}\n') == []
