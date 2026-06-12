# ADR-0001: SQLite + GCS バックアップ方式の採用

## ステータス

Deprecated

> **廃止**: Turso (libSQL) への移行に伴い、SQLite + GCS バックアップ方式は廃止。
> GCS ストレージモジュール (`infra/modules/storage/`) およびバックアップ実装 (`backend/app/db/sqlite_backup.py`) は削除済み。
> 代替: [docs/data-model.md](../data-model.md) の Turso 接続・運用方針を参照。
> 関連 ADR: [ADR-0005](./0005-cloudrun-single-instance.md)（Cloud Run single instance 構成は Turso 移行後もコスト最適化の観点で継続）

## コンテキスト

DevForge は Cloud Run 上で動作する個人開発プロジェクトであり、想定ユーザー数は〜10人規模。
ユーザー・職務経歴・資格・スキル等の関連データを扱うため、リレーショナルなデータ構造が必要。
個人開発フェーズではインフラコストの最小化が最優先となる。

Cloud Run はコンテナ実行環境であり、`/tmp` 以下のファイルシステムはコンテナのライフサイクルに依存する。
`min-instances=0` の設定によりアイドルアウト後はコンテナが破棄され、再起動時にファイルシステムが初期化される。
そのため、データの永続化には外部ストレージとの連携が必要となる。

## 決定内容

- データストアに SQLite を採用する（`/tmp/devforge.sqlite`）
- Cloud Run 起動時（FastAPI lifespan）に GCS から SQLite ファイルをダウンロードしてリストアする
- バックアップは `POST /admin/backup`（`ADMIN_TOKEN` 認証）を手動で叩くことで GCS にフルバックアップする
- バックアップは tmp オブジェクト経由のアトミック置き換え（`upload → rewrite → delete`）とし、中途半端な状態が残らない設計にする
- Cloud Run の `max-instances=1` により、複数インスタンスによる SQLite の同時書き込み競合を回避する

## 代替案

| 選択肢 | 評価 |
|---|---|
| Cloud SQL (PostgreSQL) | 常時稼働で月数千円〜のコストが発生するため却下 |
| Firestore | リレーショナル構造の表現が複雑になるため却下 |
| Cloud Spanner | コスト・オーバースペックのため対象外 |

## トレードオフ・既知のリスク

- **データロスリスク**: バックアップは手動トリガーのみのため、前回バックアップ以降の書き込みデータはコンテナがアイドルアウトすると失われる（Cloud Scheduler 等による自動バックアップは未実装）
- **リストアレイテンシ**: アイドルアウト後のコンテナ再起動時に GCS からリストアが走るため、コールドスタートのレイテンシが増加する
- **バックアップのブロッキング**: `backup_sqlite_to_gcs` は同期処理であり、GCS 書き込みが完了するまで `POST /admin/backup` のレスポンスがブロックされる
- **同時書き込み競合**: `max-instances=1` で回避しているが、インスタンス数制限が変更された場合はロック競合が発生する。〜10ユーザー規模では現実的に発生しないと判断し許容している
- **スケーラビリティ上限**: SQLite はシングルライタ前提のため、ユーザー数・書き込み頻度が増加した場合にボトルネックになりうる

## 将来の移行条件

以下のいずれかが発生した場合、Cloud SQL (PostgreSQL) への移行を検討する。

- ユーザー数が 10 人を超えた場合
- 同時書き込み競合が実際に発生した場合
- データロスが許容できないビジネス要件が生じた場合

**移行方針**: Terraform で Cloud SQL リソースを追加し、SQLite のスキーマ・データを PostgreSQL に移行する。
Alembic のマイグレーション定義は PostgreSQL にも流用できる想定。

## 関連リンク

- [backend/app/db/bootstrap.py](../../backend/app/db/bootstrap.py) — 起動時 DB 初期化（現在は Turso 接続のみ）
- [docs/data-model.md](../data-model.md) — 現行の Turso (libSQL) 運用方針
- [ADR-0005](./0005-cloudrun-single-instance.md) — Cloud Run single instance 構成（max-instances=1 は継続）
