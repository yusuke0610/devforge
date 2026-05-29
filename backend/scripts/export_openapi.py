"""FastAPI アプリの OpenAPI スキーマを JSON にダンプするスクリプト。

frontend の型生成（`openapi-typescript`）の入力となる `backend/openapi.json` を出力する。
ADR-0007（OpenAPI → TypeScript 型コード生成）のパイプライン Phase 0 の一部。

使用例（必ず Nix devshell 経由で実行する。WeasyPrint 等のネイティブ依存解決のため）:
    nix develop --command bash -c "cd backend && .venv/bin/python scripts/export_openapi.py"

出力先はデフォルトで `backend/openapi.json`。第 1 引数で変更可能。

注意:
- `app.main` を import するだけで FastAPI app は構築される（lifespan の bootstrap は実行されない）。
- ENVIRONMENT 未設定時は local 扱いとなり、INTERNAL_SECRET 等の必須チェックは走らない。
- diff の安定化のため `sort_keys=True` で出力する（openapi-typescript はキー順に依存しない）。
"""

import json
import os
import sys
from pathlib import Path

# import 時の設定チェックを避けるため、未設定なら local 環境として扱う。
os.environ.setdefault("ENVIRONMENT", "local")

# scripts/ から見たプロジェクトルート（backend/）配下に openapi.json を出力する。
_BACKEND_DIR = Path(__file__).resolve().parent.parent
_DEFAULT_OUTPUT = _BACKEND_DIR / "openapi.json"

# backend ディレクトリを import パスに追加し、`app.main` を解決可能にする。
sys.path.insert(0, str(_BACKEND_DIR))


def main() -> None:
    from app.main import app

    output_path = Path(sys.argv[1]) if len(sys.argv) > 1 else _DEFAULT_OUTPUT
    schema = app.openapi()
    # 末尾に改行を付け、エディタ・lint と整合させる。
    output_path.write_text(
        json.dumps(schema, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"OpenAPI スキーマを書き出しました: {output_path}")


if __name__ == "__main__":
    main()
