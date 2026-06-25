"""manifest パーサ群（declare ステージ / ADR-0016 D7）。"""

from .base import ManifestParser
from .registry import MANIFEST_FILENAMES, parse_manifest

__all__ = ["MANIFEST_FILENAMES", "ManifestParser", "parse_manifest"]
