# DevForge 設計原則

## このドキュメントの位置づけ

- 本ドキュメントは、蓄積された ADR（[索引](./adr/README.md)）から**帰納的に抽出した**設計原則の言語化。先に原則があって ADR が従ったのではなく、個々の判断に繰り返し現れたパターンを原則として固定したもの。
- **原則の改訂は ADR 経由で行う**。原則と矛盾する判断が必要になったら、本ファイルを直接書き換えるのではなく、その判断を ADR として起票し（矛盾と理由を明記）、Accepted になった時点で本ドキュメントへ反映する。
- 新しい ADR を書くときは、テンプレートの「設計原則との関係」欄でどの原則に沿う/反するかを明示する（[0000-template.md](./adr/0000-template.md)）。

## 原則一覧

| ID | 原則 | 一言 | 代表 ADR |
|---|---|---|---|
| P1 | コスト最適化を第一制約にする | 個人開発規模（〜10 ユーザー）を明示的な設計入力として扱う | [0005](./adr/0005-cloudrun-single-instance.md) |
| P2 | PII を信頼境界の外に出さない | ブラウザストレージ・外部 API・学習データ・国外リージョンに職務経歴を置かない | [0002](./adr/0002-jwt-cookie-auth.md), [0015](./adr/0015-vertex-ai-for-gemini-anthropic.md) |
| P3 | 正本を定め、規律は機械検証で守る | SSoT を 1 箇所に置き、複製との乖離・規律の破れは CI が検知する | [0007](./adr/0007-openapi-typescript-codegen.md), [0017](./adr/0017-mutation-testing-and-slack-notifications.md) |
| P4 | 責務を層で分離する | 機械が埋めるもの / 人間が書くもの、スキーマ / プロンプトを混ぜない | [0010](./adr/0010-devforge-agent.md), [0016](./adr/0016-github-skill-inference.md) |
| P5 | デフォルトは決定論、LLM は対話型に限定する | 推論パイプラインはルールベース。LLM はユーザーが確認して適用する対話機能のみ | [0008](./adr/0008-remove-llm-to-rule-based-design.md), [0010](./adr/0010-devforge-agent.md) |
| P6 | 可逆性を設計する | 撤退条件を先に書く。足さない・使われないものは撤去する | [0006](./adr/0006-tanstack-query.md), [0008](./adr/0008-remove-llm-to-rule-based-design.md) |
| P7 | 依存は固定し、追従は自動化する | SHA / `==` 完全固定でサプライチェーンを守り、更新は Renovate に提案させる | [0014](./adr/0014-renovate-dependency-automation.md) |

## P1: コスト最適化を第一制約にする

### 内容

「想定ユーザー数 〜10 人の個人開発」という規模を、暗黙の前提ではなく**明示的な設計入力**として扱う。可用性・スケーラビリティより先にコスト上限を制約として置き、規模が変わったときの移行条件（P6）とセットで判断する。

### 根拠となった判断

- [ADR-0005](./adr/0005-cloudrun-single-instance.md): Cloud Run を max-instances=1 / min-instances=0 に固定。SPOF・cold start を「個人開発フェーズでは許容する」と明記
- [ADR-0001](./adr/0001-sqlite-gcs-backup.md): マネージド DB ではなく SQLite + GCS バックアップから開始（後に Turso へ移行）
- [ADR-0012](./adr/0012-agent-model-switching-and-prepaid-billing.md): LLM コストをプリペイドクレジットでユーザー転嫁し、任意モデル文字列を拒否してコスト爆発を防ぐ
- [ADR-0010](./adr/0010-devforge-agent.md) / [ADR-0013](./adr/0013-multi-provider-llm-selection.md): 用途に対して過剰なモデルを使わない（差分生成は Haiku 級で足りる）。ローカル開発は Ollama で API コストゼロ

### 例外・緊張関係

- 可用性と真っ向から競合する（0005 の SPOF）。ユーザー数 10 人到達・可用性要件の高まりが P6 の移行トリガーとして明文化されている
- セキュリティ（P2）とは競合させない。コスト削減のために PII 保護を落とす判断はしていない

## P2: PII を信頼境界の外に出さない

### 内容

職務経歴書は氏名・経歴を含む PII の塊である。**ブラウザの永続ストレージ・外部 API・モデル学習データ・国外リージョン**を信頼境界の外とみなし、PII を置かない・送らない・学習させない。

### 根拠となった判断

- [ADR-0002](./adr/0002-jwt-cookie-auth.md): トークンは HttpOnly Cookie。localStorage / sessionStorage / Redux store に生トークンを置かない
- [ADR-0003](./adr/0003-redux-toolkit-persist.md): フォームキャッシュの persist 対象から PII を外す
- [ADR-0011](./adr/0011-frontend-textlint-proofread.md): 文章校正を外部 API ではなくフロントエンド完結（Web Worker）で実装（機能自体は後に撤去）
- [ADR-0015](./adr/0015-vertex-ai-for-gemini-anthropic.md): LLM を Vertex AI 経由にし、学習利用除外とデータ所在地（アジア圏リージョン）を担保

### 例外・緊張関係

- LLM 機能（P5）は「PII を外部に送らない」の例外を作る判断だった。0015 が所在地・学習除外で境界を引き直すことで両立させている
- バックエンド DB（Turso）と Fernet フィールド暗号化は信頼境界の内側という整理

## P3: 正本を定め、規律は機械検証で守る

### 内容

同じ情報を 2 箇所に書くなら、**正本（SSoT）を 1 つ決め、複製との乖離は CI が落とす**。人間の規律（目視同期・レビュー）に依存した整合性は必ず陳腐化する。検証できない複製は作らない。テストそのものの検出力も機械で計測する。

### 根拠となった判断

- [ADR-0007](./adr/0007-openapi-typescript-codegen.md): Pydantic スキーマを正本に TS 型を自動生成。codegen-drift CI が乖離で fail する
- [ADR-0012](./adr/0012-agent-model-switching-and-prepaid-billing.md) / [ADR-0013](./adr/0013-multi-provider-llm-selection.md): 実モデル ID・料金・プロバイダはサーバー側 `model_catalog.py` が正本。クライアントはエイリアスのみ知る
- [ADR-0017](./adr/0017-mutation-testing-and-slack-notifications.md): 行カバレッジでは測れないテストの検出力を週次ミューテーションテストで計測
- ADR ではないが同系統: `scripts/lint-env-keys.sh`（env 名・エラーコードの drift 検知）、`scripts/lint-adr-index.sh`（ADR 索引の drift 検知）、`.claude/rules/` の scoped rules

この原則の効果測定が [docs/metrics/ai-friendliness.md](./metrics/ai-friendliness.md)。「AI エージェントが不変条件を壊さず開発できるアーキテクチャ」は P3 の応用形で、機械検証があるほど人間にも AI にも壊しにくいコードベースになる。

### 例外・緊張関係

- 機械検証には実装コストがかかる。`docs/api.md` の環境変数表のように「drift の実害が小さい」複製は意図的に手動同期のまま残している（lint-env-keys.sh のコメント参照）
- DRY と同じで、検証の自動化自体が過剰抽象化（P6）になり得る。Mermaid 図やテーマ分類のような「人間の編集価値が本体」の情報は機械検証しない

## P4: 責務を層で分離する

### 内容

性質の異なる情報・制約を同じ層に混ぜない。**機械が客観的に埋められるもの**と**人間にしか書けないもの**、**機械検証可能な制約（スキーマ・コード）**と**機械検証不能な制約（プロンプト・文体）**を分け、それぞれの更新が互いを壊さないようにする。

### 根拠となった判断

- [ADR-0010](./adr/0010-devforge-agent.md): 「コードでテストが書ける制約はプロンプトに書かない」。構造制約はスキーマ、文体・思考方針はプロンプトへ
- [ADR-0016](./adr/0016-github-skill-inference.md): スキルを 3 層に分離（Layer 1-2 = 機械が埋める「幅」、Layer 3 = 人間が書く「深さ」）。機械の更新が人間の記述を壊す事故を層で防ぐ
- [ADR-0010](./adr/0010-devforge-agent.md) の DB 非更新原則も同型: Agent（提案する側）と保存 API（確定する側）の責務を分け、既存バリデーションを保存側に集約

### 例外・緊張関係

- 層を増やすこと自体が複雑化（P6 の「足さない」と緊張）。0016 は「双方向の事故が実際に起きうる」ことを示してから 3 層化しており、事故パターンの明示が分離の条件

## P5: デフォルトは決定論、LLM は対話型に限定する

### 内容

バックグラウンドの分析・推論パイプラインは**ルールベース（決定論）**を第一選択とする。LLM を使うのは、**ユーザーが結果を確認してから適用する対話型機能**に限る。「LLM の出力を無確認で永続化する」経路を作らない。

### 根拠となった判断

- [ADR-0008](./adr/0008-remove-llm-to-rule-based-design.md): 利用見込みの薄い LLM 抽象を全撤去し、キャリア分析をルールベースへ一本化
- [ADR-0010](./adr/0010-devforge-agent.md): LLM の再導入は「ユーザー対話型のフォアグラウンド機能」に限定。差分はフォーム state にのみ適用し、保存はユーザーの明示操作（DB 非更新原則）
- [ADR-0016](./adr/0016-github-skill-inference.md): スキル推論（Layer 1-2）は決定論を維持。LLM が入りうるのは人間レビューが確定する Layer 3 のみ
- [ADR-0011](./adr/0011-frontend-textlint-proofread.md): 校正も LLM ではなくルールベース（textlint）を選択

### 例外・緊張関係

- 「対話型なら LLM 可」の判断は品質・コスト（P1）・PII（P2）の 3 制約を同時に満たす必要がある。0012（コスト転嫁）・0015（データガバナンス）はこの原則を維持するための補強

## P6: 可逆性を設計する

### 内容

判断には**撤退条件（「将来の移行条件」）を先に書く**。導入は「3 つ目の利用箇所が現れてから」（Rule of Three）、撤去は「使われないと分かったら躊躇なく」。休眠コード・使われない抽象を「いつか使うかも」で残さない。

### 根拠となった判断

- ADR テンプレートに「将来の移行条件」セクションが最初から組み込まれている
- [ADR-0008](./adr/0008-remove-llm-to-rule-based-design.md) → [ADR-0010](./adr/0010-devforge-agent.md): 0008 が規定した再導入手続きに従って LLM を復活させた。**撤退条件を先に書く運用が実際に機能した実例**
- [ADR-0006](./adr/0006-tanstack-query.md): TanStack Query をパイロット未実施のまま導入せず見送り
- [ADR-0011](./adr/0011-frontend-textlint-proofread.md): 実装まで行った校正機能を、運用不要と判断して撤去
- [ADR-0009](./adr/0009-frontend-toast-notification.md): 外部ライブラリを足さず自前 Toast（必要十分の実装）
- [ADR-0013](./adr/0013-multi-provider-llm-selection.md): 既存抽象に無理に載せず、プロバイダ抽象の作り直しを許容

CLAUDE.md の「過剰な抽象化を避ける」・`.claude/rules/common/duplication.md` の Rule of Three は本原則のコーディングレベルの表現。

### 例外・緊張関係

- `lifecycle { prevent_destroy = true }` のような不可逆リソースや、0015 の「シークレット destroy 後は旧リビジョンへロールバック不可」のように、可逆性を意図的に手放す場合は ADR にその旨を明記する

## P7: 依存は固定し、追従は自動化する

### 内容

依存は**完全固定**する（GitHub Actions は SHA ピン、Python は `==`、lockfile 必須）。固定によるサプライチェーン防御と引き換えに生じる「追従されない」弱点は、**自動化（Renovate）で提案させ、人間はレビューだけする**形で補う。固定と追従を人間の記憶に頼らない。

### 根拠となった判断

- [ADR-0014](./adr/0014-renovate-dependency-automation.md): 完全固定運用を維持したまま Renovate を導入。CVE 対応の後追い・更新差分の肥大化を解消
- [ADR-0017](./adr/0017-mutation-testing-and-slack-notifications.md): 新規 workflow でも Actions の SHA ピン運用を踏襲
- [ADR-0007](./adr/0007-openapi-typescript-codegen.md): codegen ツールチェーンも固定の対象

### 例外・緊張関係

- 自動更新 PR の通知はノイズになりやすい。0017 の Slack チャンネル分割（`SLACK_WEBHOOK_URL_DEPS`）が運用面の補完

## 原則 × ADR 対応マトリクス

● = その ADR の中心的な判断軸、○ = 関係する判断軸。

| ADR | P1 コスト | P2 PII | P3 正本+機械検証 | P4 層分離 | P5 決定論 | P6 可逆性 | P7 依存固定 |
|---|---|---|---|---|---|---|---|
| [0001](./adr/0001-sqlite-gcs-backup.md) SQLite + GCS | ● | | | | | ○ | |
| [0002](./adr/0002-jwt-cookie-auth.md) JWT + Cookie 認証 | | ● | | | | | |
| [0003](./adr/0003-redux-toolkit-persist.md) Redux + persist | | ● | | | | | |
| [0004](./adr/0004-llm-provider-abstraction.md) LLM 抽象設計 | ○ | | | | | ● | |
| [0005](./adr/0005-cloudrun-single-instance.md) single instance | ● | | | | | ○ | |
| [0006](./adr/0006-tanstack-query.md) TanStack Query 見送り | ○ | ○ | | | | ● | |
| [0007](./adr/0007-openapi-typescript-codegen.md) OpenAPI → TS codegen | | | ● | | | | ○ |
| [0008](./adr/0008-remove-llm-to-rule-based-design.md) ルールベース一本化 | ○ | | | | ● | ● | |
| [0009](./adr/0009-frontend-toast-notification.md) 自前 Toast | | | | | | ● | |
| [0010](./adr/0010-devforge-agent.md) DevForge Agent | ○ | ○ | | ● | ● | | |
| [0011](./adr/0011-frontend-textlint-proofread.md) textlint 校正（撤去） | ○ | ● | | | ○ | ○ | |
| [0012](./adr/0012-agent-model-switching-and-prepaid-billing.md) モデル切替 + 課金 | ● | | ○ | | | | |
| [0013](./adr/0013-multi-provider-llm-selection.md) マルチプロバイダ | ○ | | ● | | | ○ | |
| [0014](./adr/0014-renovate-dependency-automation.md) Renovate | | | | | | | ● |
| [0015](./adr/0015-vertex-ai-for-gemini-anthropic.md) Vertex AI (ADC) | | ● | | | | | ○ |
| [0016](./adr/0016-github-skill-inference.md) スキル推論 3 層 | | | | ● | ○ | | |
| [0017](./adr/0017-mutation-testing-and-slack-notifications.md) ミューテーションテスト | | | ● | | | | ○ |
| [0018](./adr/0018-github-resume-draft-generation.md) 経歴書ドラフト生成 | ○ | | | ● | ● | ○ | |
