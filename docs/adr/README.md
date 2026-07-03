# ADR 索引

- **本ファイルが ADR の一覧・関係（テーマ・置き換え・関連）の正本**。CONTRIBUTING.md 等に一覧を複製しない。
- ADR を新規作成・ステータス変更したら、同じ PR で本索引を更新する（手順: [CONTRIBUTING.md](../../CONTRIBUTING.md) の「ADR」節）。
- 「全 ADR 一覧」表の **ファイル存在・ステータス・見出し番号は CI で機械検証される**（`scripts/lint-adr-index.sh` / `make lint-adr-index`）。テーマ・関連・決定系統図は人間が編集する（機械検証外）。

## 現在有効な決定（Accepted）

いま生きている判断の早見表。詳細・経緯は各 ADR と「テーマ別の決定系統」を参照。

| No. | タイトル | テーマ | 一言サマリ |
|---|---|---|---|
| [ADR-0002](./0002-jwt-cookie-auth.md) | JWT + Cookie 認証方式の採用 | 基盤 | GitHub OAuth only + JWT（RS256）を HttpOnly Cookie で扱い、PII をブラウザストレージに置かない |
| [ADR-0003](./0003-redux-toolkit-persist.md) | Redux Toolkit + redux-persist の採用 | フロントエンド | フォーム一時キャッシュをページ遷移をまたいで保持（PII は localStorage 非保存） |
| [ADR-0005](./0005-cloudrun-single-instance.md) | Cloud Run single instance 構成の採用 | 基盤 | コスト最優先で max-instances=1 / min-instances=0。個人開発規模を明示的な設計入力にする |
| [ADR-0007](./0007-openapi-typescript-codegen.md) | OpenAPI → TypeScript 型コード生成の導入（完全移行） | 開発プロセス / 品質 | Pydantic スキーマを正本に TS 型を自動生成し、drift を CI（codegen-drift）で機械検知 |
| [ADR-0009](./0009-frontend-toast-notification.md) | フロントエンドの一時通知をトースト方式に統一する | フロントエンド | 外部ライブラリを足さず自前 Toast 基盤（Context + Portal）に一時通知を統一 |
| [ADR-0010](./0010-devforge-agent.md) | DevForge Agent 機能の導入 | LLM / Agent | 対話型 LLM を再導入。DB 非更新原則・スキーマ/プロンプトの責務分離・失敗の明示的エラー化 |
| [ADR-0012](./0012-agent-model-switching-and-prepaid-billing.md) | Agent モデル切り替えとプリペイドクレジット課金 | LLM / Agent | モデルはエイリアス方式（実 ID はサーバー側 model_catalog が SSoT）+ プリペイド従量課金（Stripe） |
| [ADR-0013](./0013-multi-provider-llm-selection.md) | マルチプロバイダ LLM（ユーザー選択式） | LLM / Agent | プロバイダをモデルエイリアスの属性に移しユーザー選択式へ。グローバル `LLM_PROVIDER` 廃止 |
| [ADR-0014](./0014-renovate-dependency-automation.md) | Renovate による依存更新の自動化 | 開発プロセス / 品質 | 依存の完全固定（SHA / `==` ピン）を維持したまま、追従だけを Renovate で自動化 |
| [ADR-0015](./0015-vertex-ai-for-gemini-anthropic.md) | Gemini / Anthropic を Vertex AI（SA→ADC）経由にする | LLM / Agent | API キー注入を廃止し ADC 認証へ。データ所在地（アジア圏）と学習除外を担保 |
| [ADR-0016](./0016-github-skill-inference.md) | GitHub 連携によるスキル推論基盤 | LLM / Agent | スキルを 3 層に分離（機械=幅 / 人間=深さ）。推論パイプラインは決定論を維持 |
| [ADR-0017](./0017-mutation-testing-and-slack-notifications.md) | ミューテーションテスト週次実行と Slack 通知チャンネル分割 | 開発プロセス / 品質 | テストの検出力を週次ミューテーションで可視化（warn-only）、CI 通知を用途別 Slack へ分割 |

## 全 ADR 一覧

ステータスの定義と変更手順は [CONTRIBUTING.md](../../CONTRIBUTING.md) を参照。
「原則」列（P1〜P7）はその ADR の中心的な判断軸で、定義と対応マトリクスは [docs/design-principles.md](../design-principles.md) を参照。

| No. | タイトル | ステータス | テーマ | 置き換え・関連 | 原則 |
|---|---|---|---|---|---|
| [ADR-0001](./0001-sqlite-gcs-backup.md) | SQLite + GCS バックアップ方式の採用 | Deprecated | 基盤 | Turso (libSQL) 移行で廃止。関連: 0005（同時移行前提の強結合） | P1 |
| [ADR-0002](./0002-jwt-cookie-auth.md) | JWT + Cookie 認証方式の採用 | Accepted | 基盤 | — | P2 |
| [ADR-0003](./0003-redux-toolkit-persist.md) | Redux Toolkit + redux-persist の採用 | Accepted | フロントエンド | 関連: 0006（責務境界・PII 方針を踏襲） | P2 |
| [ADR-0004](./0004-llm-provider-abstraction.md) | LLM プロバイダ抽象化（Ollama/Vertex AI）の設計判断 | Superseded by ADR-0008 | LLM / Agent | 0008 が撤去。dev/prod 分離思想は 0010 が再利用 | P6 |
| [ADR-0005](./0005-cloudrun-single-instance.md) | Cloud Run single instance 構成の採用 | Accepted | 基盤 | 関連: 0001（制約の起点）、0012（単一インスタンス前提の原子的 UPDATE） | P1 |
| [ADR-0006](./0006-tanstack-query.md) | TanStack Query 導入検討 | Deprecated | フロントエンド | パイロット未実施で見送り。関連: 0003 | P6 |
| [ADR-0007](./0007-openapi-typescript-codegen.md) | OpenAPI → TypeScript 型コード生成の導入（完全移行） | Accepted | 開発プロセス / 品質 | 関連: 0010（Agent の型契約も codegen 経由） | P3 |
| [ADR-0008](./0008-remove-llm-to-rule-based-design.md) | LLM プロバイダ抽象化の撤去とルールベース設計への統一 | Superseded by ADR-0010 | LLM / Agent | Supersedes: 0004。0010 が「将来の移行条件」の手続きに従い再導入 | P5・P6 |
| [ADR-0009](./0009-frontend-toast-notification.md) | フロントエンドの一時通知をトースト方式に統一する | Accepted | フロントエンド | — | P6 |
| [ADR-0010](./0010-devforge-agent.md) | DevForge Agent 機能の導入 | Accepted | LLM / Agent | Supersedes: 0008。関連: 0004（積み残しリスクを設計段階で解消）、0007 | P4・P5 |
| [ADR-0011](./0011-frontend-textlint-proofread.md) | 職務経歴書のフロントエンド完結型 文章校正（textlint + kuromoji） | Deprecated | フロントエンド | 実装後に運用不要と判断し撤去。関連: 0008（PII 非送信・ルールベース志向） | P2 |
| [ADR-0012](./0012-agent-model-switching-and-prepaid-billing.md) | Agent モデル切り替えとプリペイドクレジット課金 | Accepted | LLM / Agent | 関連: 0010（チャット契約）、0005（原子的 UPDATE の前提） | P1 |
| [ADR-0013](./0013-multi-provider-llm-selection.md) | マルチプロバイダ LLM（ユーザー選択式） | Accepted | LLM / Agent | 関連: 0010（切替 1 箇所の原則を維持）、0012（課金・model_catalog） | P3 |
| [ADR-0014](./0014-renovate-dependency-automation.md) | Renovate による依存更新の自動化 | Accepted | 開発プロセス / 品質 | 関連: 0017（Actions の SHA ピン運用） | P7 |
| [ADR-0015](./0015-vertex-ai-for-gemini-anthropic.md) | Gemini / Anthropic を Vertex AI（SA→ADC）経由にする | Accepted | LLM / Agent | 0013 の認証部分を更新。関連: 0010、0012 | P2 |
| [ADR-0016](./0016-github-skill-inference.md) | GitHub 連携によるスキル推論基盤 | Accepted | LLM / Agent | 関連: 0010（責務分離の元思想）、0013、0015 | P4 |
| [ADR-0017](./0017-mutation-testing-and-slack-notifications.md) | ミューテーションテスト週次実行と Slack 通知チャンネル分割 | Accepted | 開発プロセス / 品質 | 関連: 0014 | P3 |

## テーマ別の決定系統

各テーマの判断がどう連なり・覆されてきたかの系統図。実線 = 置き換え（supersede）、点線 = 参照・前提。

### LLM / Agent

```mermaid
graph LR
    A0004["0004<br/>LLM 抽象設計"] -->|"撤去"| A0008["0008<br/>ルールベース一本化"]
    A0008 -->|"再導入"| A0010["0010<br/>DevForge Agent"]
    A0010 -.-> A0012["0012<br/>モデル切替 + 課金"]
    A0012 -.-> A0013["0013<br/>マルチプロバイダ"]
    A0013 -.-> A0015["0015<br/>Vertex AI (ADC)"]
    A0010 -.-> A0016["0016<br/>スキル推論 3 層"]
```

このプロダクトで最も判断の往復が大きい系統。「LLM 抽象の先行実装（0004）→ 利用見込み薄と判断して全撤去（0008）→ 対話型として価値が明確になった時点で、0008 自身が規定した手続きに従い再導入（0010）→ 課金・マルチプロバイダ・データガバナンスへ段階拡張（0012/0013/0015）」という流れで、**撤退条件を先に書いておく運用が実際に機能した実例**になっている。0016 は 0010 の「機械検証可能な制約はコード、不能な制約はプロンプト」という責務分離を「機械=幅 / 人間=深さ」の 3 層モデルへ一般化した。

### 基盤（データ / インフラ / 認証）

```mermaid
graph LR
    B0001["0001<br/>SQLite + GCS"] -.->|"制約の起点"| B0005["0005<br/>single instance"]
    B0001 -->|"Turso 移行で廃止"| BX["(Turso / libSQL)"]
    B0002["0002<br/>JWT + Cookie 認証"]
```

0005 の single instance 制約は当初 0001（SQLite の同時書き込み不可）に起因していた。Turso 移行で 0001 は Deprecated になったが、0005 は「コスト最適化・個人開発規模」という別の根拠で存続している。**同じ決定でも根拠が入れ替わることがある**ため、系統図は「何に依存していた判断か」を追う手がかりになる。0002 は独立した判断だが、「PII をブラウザに置かない」方針の起点として 0003 / 0011 に思想面で連なる。

### フロントエンド

```mermaid
graph LR
    C0003["0003<br/>Redux Toolkit + persist"] -.->|"PII 方針を踏襲"| C0006["0006<br/>TanStack Query (見送り)"]
    C0009["0009<br/>自前 Toast 統一"]
    C0011["0011<br/>textlint 校正 (撤去)"]
```

導入したもの（0003 / 0009）より、**見送り・撤去の判断（0006 / 0011）が残っていること**がこの系統の価値。0006 はパイロット未実施のまま導入せず、0011 は実装まで行った上で運用不要と判断して撤去した。外部ライブラリを安易に足さない・使われないものを残さない判断の記録として参照する。型定義の正本は backend にある（0007 の codegen が FE の手書き DTO を置き換えた）。

### 開発プロセス / 品質

```mermaid
graph LR
    D0007["0007<br/>OpenAPI → TS codegen"]
    D0014["0014<br/>Renovate 自動追従"] -.->|"SHA ピン運用"| D0017["0017<br/>ミューテーションテスト"]
```

「正本を 1 つに定め、複製との乖離は機械で検知する」（0007）、「依存は固定し、追従は自動化する」（0014）、「テストの検出力自体を計測する」（0017）という、**プロダクト機能ではなく開発体験そのものへの投資**の系統。`docs/metrics/ai-friendliness.md` はこの系統の効果を月次で観測するダッシュボード。

## 運用

- **新規作成**: [`0000-template.md`](./0000-template.md) をコピーし、[CONTRIBUTING.md](../../CONTRIBUTING.md) の命名規則・ステータス運用に従う。作成したら本索引の「全 ADR 一覧」（Accepted なら「現在有効な決定」にも）へ行を追加する
- **ステータス変更（supersede / deprecate）**: CONTRIBUTING.md の手順に従い旧 ADR を更新した後、本索引のステータス列・「置き換え・関連」列・決定系統図を更新する
- **検証**: `make lint-adr-index`（CI でも実行される）が「ADR ファイル ↔ 索引の行」の存在・ステータス・見出し番号の突合を行う
