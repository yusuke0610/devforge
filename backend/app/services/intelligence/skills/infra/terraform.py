"""Terraform / OpenTofu パーサ（tool=terraform / D10）。

static な HCL ブロックから provider（クラウド事業者）と resource（具体サービス）を抽出する:

  - ``provider "aws" {``                       → provider 宣言（resource_type=None）
  - ``required_providers { aws = { source } }``→ provider 宣言（source 末尾 or local 名）
  - ``resource "aws_s3_bucket" "x" {``          → resource 宣言（provider は type 接頭辞）

正規表現ベースで依存を持たない（既存の manifest パーサと同方針）。``module`` / ``count`` /
``for_each`` / ``dynamic`` による動的生成は静的列挙できないため対象外（将来課題）。壊れた HCL は
例外を投げずベストエフォート（取れた分だけ返す）で処理する。
"""

import re

from ..types import InfraResourceDeclaration

_TOOL = "terraform"

# provider "aws" {
_PROVIDER_BLOCK = re.compile(r'^provider\s+"([^"]+)"\s*\{')
# resource "aws_s3_bucket" "name" {
_RESOURCE_BLOCK = re.compile(r'^resource\s+"([^"]+)"\s+"[^"]+"\s*\{')
# required_providers {
_REQUIRED_PROVIDERS_OPEN = re.compile(r'^required_providers\s*\{')
# required_providers 内の各エントリ（local 名）: `aws = {`
_RP_LOCAL_ENTRY = re.compile(r'^([A-Za-z_][A-Za-z0-9_-]*)\s*=\s*\{')
# required_providers 内の source 行: `source = "hashicorp/aws"`
_RP_SOURCE = re.compile(r'source\s*=\s*"([^"]+)"')


class TerraformParser:
    extensions: tuple[str, ...] = (".tf",)
    tool: str = _TOOL

    def parse(self, content: str) -> list[InfraResourceDeclaration]:
        declarations: list[InfraResourceDeclaration] = []
        in_required_providers = False
        rp_depth = 0  # required_providers ブロック内のネスト深さ
        pending_local: str | None = None  # source 待ちの local 名
        pending_source: str | None = None

        def flush_provider() -> None:
            nonlocal pending_local, pending_source
            if pending_local is None:
                return
            # provider の「型」は source の末尾セグメント（hashicorp/aws → aws）を優先し、
            # 無ければ local 名を使う（resource の type 接頭辞と一致させるため）。
            provider = (
                pending_source.rsplit("/", 1)[-1] if pending_source else pending_local
            )
            declarations.append(
                InfraResourceDeclaration(tool=_TOOL, provider=provider)
            )
            pending_local = None
            pending_source = None

        for raw_line in content.splitlines():
            line = raw_line.strip()
            if not line or line.startswith(("#", "//")):
                continue

            if in_required_providers:
                # source を先に拾う（エントリと同一行のワンライナーにも対応）。
                source_match = _RP_SOURCE.search(line)
                local_match = _RP_LOCAL_ENTRY.match(line)
                if local_match:
                    # 新しいエントリに入る前に直前のエントリを確定する。
                    flush_provider()
                    pending_local = local_match.group(1)
                    pending_source = source_match.group(1) if source_match else None
                elif source_match and pending_local is not None:
                    pending_source = source_match.group(1)

                rp_depth += line.count("{") - line.count("}")
                if rp_depth <= 0:
                    flush_provider()
                    in_required_providers = False
                continue

            if _REQUIRED_PROVIDERS_OPEN.match(line):
                in_required_providers = True
                rp_depth = line.count("{") - line.count("}")
                continue

            provider_match = _PROVIDER_BLOCK.match(line)
            if provider_match:
                declarations.append(
                    InfraResourceDeclaration(
                        tool=_TOOL, provider=provider_match.group(1)
                    )
                )
                continue

            resource_match = _RESOURCE_BLOCK.match(line)
            if resource_match:
                resource_type = resource_match.group(1)
                # type 接頭辞（最初の `_` の前）が provider。例: aws_s3_bucket → aws。
                provider = resource_type.split("_", 1)[0]
                declarations.append(
                    InfraResourceDeclaration(
                        tool=_TOOL,
                        provider=provider,
                        resource_type=resource_type,
                    )
                )

        # ファイルが途中で切れて required_providers が閉じない場合も取れた分を確定する。
        if in_required_providers:
            flush_provider()

        return declarations
