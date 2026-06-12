# ADR-0005: Cloud Run single instance 構成の採用

## ステータス

Accepted

## コンテキスト

DevForge は Cloud Run 上で動作する個人開発プロジェクト（想定ユーザー数: 〜10人）。

> **注記（2025年）**: データストアは Turso (libSQL) に移行済み（[ADR-0001](./0001-sqlite-gcs-backup.md) は Deprecated）。
> SQLite ファイルの同時書き込み問題は解消されたが、max-instances=1 はコスト最適化と個人開発規模の観点から引き続き採用している。

当初は SQLite を採用しており（ADR-0001 参照）、以下の制約があった。

- SQLite はファイルベースの DB であり、複数インスタンスが同一ファイルに同時書き込みすると
  データ破損・ロック競合が発生する
- Cloud Run がスケールアウトした場合、各インスタンスは独立したファイルシステムを持つため
  SQLite ファイルの状態が分岐する

加えて以下の要件があった。

- インフラコストを最小化したい（個人開発フェーズ）
- 〜10ユーザー規模ではスケールアウトの必要性がない

## 決定内容

Cloud Run のインスタンス数を `max-instances=1` に固定し、全環境（local / dev / stg / prod）で
single instance 構成を採用する。

**Terraform 設定**:

```hcl
max_instance_count               = 1
min_instance_count               = 0   # コスト最優先・cold start 許容
max_instance_request_concurrency = 80  # 1インスタンスあたりの同時リクエスト数
```

`min-instances=0` とすることでアイドル時のインスタンス料金をゼロにする。
cold start のレイテンシは個人開発フェーズでは許容する。

## 代替案

- **`max-instances` を 2 以上に設定**: SQLite の同時書き込み競合・ファイル状態の分岐が発生するため、
  SQLite を使用している間は採用不可
- **Cloud SQL (PostgreSQL) + スケールアウト**: コストが増加するため現フェーズでは対象外。
  ユーザー数増加時の移行先として想定している（ADR-0001 参照）
- **Firestore 等のサーバーレス DB への移行**: リレーショナル構造の維持を優先しているため対象外

## トレードオフ・既知のリスク

1. **単一障害点（SPOF）**
   - インスタンスが 1 つのため、コンテナ障害・デプロイ時のダウンタイムが発生する
   - Cloud Run のローリングデプロイは `max-instances=1` では新旧インスタンスが並走できないため、
     デプロイ中に短時間のダウンタイムが生じる可能性がある
   - 個人開発フェーズでは許容する

2. **cold start によるレイテンシ**
   - `min-instances=0` のためアイドルアウト後の初回リクエストに cold start が発生する
   - SQLite のマウント（GCS からのリストア）も cold start 時に実行されるため、
     通常の cold start より時間がかかる可能性がある

3. **スケールアウト不可**
   - トラフィックが急増しても水平スケールできない
   - `max_instance_request_concurrency=80` の上限を超えるリクエストはキューイングされる

4. **ADR-0001 との強い結合**
   - この制約は SQLite 採用（ADR-0001）に起因する
   - PostgreSQL 移行（ADR-0001 の将来対応）と single instance 解除はセットで対応する

## 将来の移行条件

ユーザー数が 10 人に達した場合、または可用性要件が高まった場合。

1. ADR-0001 に従い Cloud SQL (PostgreSQL) へ移行する
2. `max-instances=1` の制約を解除し、スケールアウトを有効にする
3. `min-instances=1` への変更も併せて検討する（cold start の排除）

ADR-0001 と ADR-0005 は同一の移行タイミングで対応する。

## 関連リンク

- [ADR-0001: SQLite + GCS バックアップ](./0001-sqlite-gcs-backup.md)
