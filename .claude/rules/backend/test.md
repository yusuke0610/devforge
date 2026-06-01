---
paths:
  - backend/**
---

# Backend テスト方針

## いつテストを書く・回すか（トリガー）

以下のいずれかに該当する変更を行った場合、テスト追加・更新と実行が必須:

- **新規エンドポイント追加**: 必ず統合テスト（`tests/test_<router>.py`）を追加し、正常系・認可エラー・バリデーションエラー・404 を最低限カバーする
- **既存エンドポイントの契約変更**: ステータスコード / レスポンス body / 副作用が変わる場合、既存テストの assert を見直す（旧契約を固定化したテストが残ると意図が後退する）
- **リポジトリ層・サービス層のロジック変更**: 該当ユニットテスト（`tests/test_<module>.py` / `tests/services/`）を更新
- **タスクハンドラの追加・変更**: `tests/test_worker_extended.py` または `tests/test_worker_timeout.py` に状態遷移（`processing` → `completed` / `dead_letter` / `retrying`）のテストを追加
- **マイグレーション追加**: 実 DB に対する upgrade/downgrade が通ることを `make test-backend` で確認
- **暗号化・認証関連**: `tests/test_auth.py` / `tests/test_encryption.py` / `tests/test_oauth_flow.py` を必ず回す

## 実行コマンド

```bash
make test-backend                    # 全テスト
```

特定ファイルだけ回す場合:
```bash
nix develop --command bash -c "cd backend && .venv/bin/python -m pytest tests/test_worker_extended.py -q"
```

## OK 基準（達成条件）

以下をすべて満たして初めて「テスト OK」と判定する:

1. **全テスト pass**: `make test-backend` が exit 0
2. **新規・変更コードに対応するテストが存在する**:
   - 新規エンドポイント → ハッピーパス + 認可失敗 + 不正入力（最低 3 ケース）
   - 新規サービス関数 → 主要分岐ごとに 1 ケース
   - タスクハンドラ → 成功 / `NonRetryableError` / `RetryableError` の 3 パス
3. **失敗パスを明示的に検証している**: 例外を `pytest.raises(ExpectedError)` で必ず assert する。silent return を許容するテスト（過去の `test_no_cache_returns_early` のようなもの）は書かない
4. **モックは最小限**: DB はモックしない（実 SQLite セッションを使う）。外部サービス（GitHub API / Cloud Tasks / Redis）はモックする
5. **lint が pass**: `make lint-backend` も同時に通ること

## アンチパターン

- `assert result is not None` だけで満足する（中身を検証していない）
- `try / except Exception: pass` をテストコード内で使う（失敗を隠す）
- `time.sleep` での同期待ち（フレーキーになる。`AsyncMock` / `monkeypatch` を使う）
- 過剰モック: SQLAlchemy セッション全体をモックする等。実 DB セッションを使うこと
