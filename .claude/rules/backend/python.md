---
paths:
  - backend/**
---

# Python コーディング規約

- ruff に準拠すること（設定: `backend/pyproject.toml`）
- PEP8を守るな、PEP8を理解した上で抽象化しろ
- コード変更後は `make lint-backend` を実行し、違反がないことを確認すること（Nix devshell 経由で ruff が解決される）
- 特定ファイルだけ検証したい場合は `nix develop --command bash -c "cd backend && .venv/bin/python -m ruff check <path>"` を使う。生シェルで `.venv/bin/python` を直接叩くのは禁止（WeasyPrint の動的ライブラリが解決できず import に失敗するため）
- **lint 失敗時は当該ファイルだけ確認する**: `make lint-backend` が他ファイルの I001 等で落ちる場合、自分の変更分は上記の個別 `ruff check <touched_file>` で検証してから進める（既存違反を巻き込まない）
- 未使用の import を残さないこと（F401）
- 重複検知 / DRY ポリシーは `.claude/rules/common/duplication.md` を参照（抽出先は `backend/app/services/shared/` または同一サブパッケージの `_utils.py`）

## 例外処理の必須ルール

- **`except SomeException: pass` は絶対禁止**。例外を握りつぶすと障害調査が不可能になる
- 最低でも `logger.debug/warning/error` でログを出すこと
- 補助的な処理（通知生成など）でメインフローへの影響を避けるために例外を抑制する場合も `logger.warning` でログを残すこと
- 正しいパターン例:
  ```python
  # 補助処理で例外を抑制する場合
  try:
      _create_notification(...)
  except Exception:
      logger.warning("通知作成に失敗 (無視)", exc_info=True)

  # 想定内の例外でスキップする場合
  except HTTPException:
      logger.debug("Referer が CORS_ORIGINS に含まれないためスキップ: %s", referer)
  ```

## システムパッケージと Dockerfile

- Pythonライブラリがシステムパッケージ（C ライブラリ等）に依存する場合、ローカル環境（`flake.nix` の `devShells.default.packages`）と本番イメージ（`backend/Dockerfile` の `apt-get install`）の両方に追加すること
- `flake.nix` だけ更新して Dockerfile を忘れると Cloud Run デプロイで import エラーになる
