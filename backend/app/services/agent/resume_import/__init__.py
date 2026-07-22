"""手持ち PDF 経歴書のフォーム流し込み（ADR-0024）。

テキスト埋め込み PDF を pypdf で抽出し、Claude Haiku で Resume 互換 payload に
構造化する。DB 非更新でフォーム注入機構（#524）へ渡す前段まで。
"""
