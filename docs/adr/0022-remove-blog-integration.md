# ADR-0022: ブログ連携機能の撤去

## ステータス

Accepted

## 関連 ADR

- 関連: [ADR-0008](0008-remove-llm-to-rule-based-design.md)（撤去 ADR の体裁・全量列挙の流儀を手本にする）、[ADR-0010](0010-devforge-agent.md)（本撤去で Agent コンテキストの入力データが変わる。DB 非更新原則は不変）、[ADR-0016](0016-github-skill-inference.md)（撤去後もスキル推論・GitHub 連携は Agent の主要データ供給源として残る）

## コンテキスト

機能の要否をユーザ目線で棚卸しした結果（#517）、ブログ連携（Zenn / note 同期・記事一覧・投稿スコアリング）を撤去する方針を決めた。

- **経歴書への還流がない**: ブログ連携は記事一覧 + スコア表示止まりで、職務経歴書ドメインへデータが流れていない。ユーザの成果物（経歴書）に寄与しない独立した島になっている。
- **スコアリングが逆効果になり得る**: 投稿頻度スコアは、育休・療養・多忙などでブランクのあるユーザに「求めていない通知表」を突きつける。ユーザ価値としてマイナスに働く場面がある。
- **外部仕様への脆弱性**: note は公式 API がなく RSS スクレイピング依存で、外部仕様変更に弱い。継続的な追従コストが機能価値に見合わない。
- **保守コストの継続発生**: テーブル 3 つ・router 3 系統・service 群・repository・schema・web ページ一式が、還流のないまま lint / test / codegen / 依存追従の対象として保守コストを積み上げている。

休眠に近い島を残すと、依存追従・「使われている」という誤った前提・env / codegen 同期の負担が積み上がる。ADR-0008（LLM 全撤去）と同じ判断で、還流のない機能は残さず消す。

## 決定内容

ブログ連携機能と関連資産を全て撤去する。撤去は ADR-0008 の流儀（env・ErrorCode・フロント定数・docs まで残さず消す）に倣い、次の実装 PR（#519）のチェックリストとして使える粒度で全量を列挙する。

### 撤去対象（全量）

**DB テーブル（3 つ）** — Alembic の drop マイグレーションを新規追加して撤去する:

- `blog_accounts`（`0011_create_blog_tables.py` で作成、`0029_add_last_synced_at_to_blog_accounts.py` で列追加）
- `blog_articles`（`0011_create_blog_tables.py`）
- `blog_article_tags`（`0011_create_blog_tables.py`）

**backend コード**:

- `app/routers/blog/`（`accounts.py` / `sync.py` / `score.py` / `__init__.py`）と `main.py` / `routers/__init__.py` の `blog_router` 登録
- `app/services/blog/`（`account_service.py` / `collector.py` / `scorer.py` / `sync_service.py` / `tech_keywords.json` / `__init__.py`）
- `app/repositories/blog.py`（`BlogArticleRepository` 他）
- `app/models/blog.py`（`BlogAccount` / `BlogArticle` / `BlogArticleTag`）と `models/__init__.py` の export
- `app/schemas/blog.py`（`BlogScoreResponse` / `BlogScoreArticleResponse` 他）と `schemas/__init__.py` の export
- `app/messages.json` の blog メッセージキー（`error.blog` 6 件: `account_not_found` / `account_link_not_found` / `account_check_failed` / `sync_failed` / `platform_not_supported` / `account_already_registered`、`success.blog` 3 件: `account_added` / `account_removed` / `sync_complete`）
- 上記に紐づくテスト一式（`tests/` 配下の blog 関連テスト）

**backend 側で「存在しないため撤去不要」を確認済みの資産**（#519 が存在しない資産を探して迷わないよう明記）:

- **blog 専用の環境変数は無し**（`env_keys.py` に blog / zenn / note キー無し。ADR-0008 のような env 4+1 箇所同期は不要）
- **blog 専用の ErrorCode enum は無し**（`app/core/errors.py` の `ErrorCode` に blog エントリ無し。ユーザー向け文言は上記 `messages.json` のキーのみ。OpenAPI の ErrorCode union には波及しない）
- **blog 専用の非同期タスクハンドラは無し**（`services/tasks/handlers/` に blog ハンドラ無し。記事同期は `routers/blog/sync.py` の同期処理。撤去後に孤児化するスケジュール済みジョブ / Cloud Tasks 設定は無い）

**docs**:

- `docs/api.md`「ブログ連携」節（`/api/blog/*` エンドポイント一覧）
- `docs/data-model.md` の blog テーブル記述（`blog_accounts` / `blog_articles` / `blog_article_tags` と関連する日付・タグの記載）

**web コード**:

- `web/src/pages/BlogPage.tsx`、`web/src/components/blog/`（`BlogPage.tsx` / `BlogArticleList.tsx` / `BlogPlatformList.tsx` / `BlogScoreCard.tsx` と各 `*.module.css`）
- `web/src/api/blog.ts`、`web/src/hooks/blog/`（`useBlogAccountManager.ts` とテスト）
- `web/src/router/routes.tsx` の `/blog` ルートと `BlogPage` import
- `web/src/components/SidebarLayout.tsx` の `/blog` 導線
- `web/src/constants/messages.ts` の `NAV_BLOG_LINK` と blog 系メッセージ関数（`blogLinkedSyncSuccessMessage` / `blogSyncSuccessMessage` / `blogUsernameUpdatedSyncSuccessMessage`）

**codegen 生成物**:

- `web/src/api/generated.ts` の blog パス・型（`make codegen-types` で再生成してコミット。codegen-drift 対策）

### Agent への波及（既知のトレードオフ）

`services/agent/context_builder.py` の `_build_blog_context`（`BlogArticleRepository` + `services.blog.scorer.calculate_blog_score` を参照）が、ブログスコアを Agent コンテキスト（`result["blog_context"]`）に注入している。撤去によりこの注入経路と import を消すため、**職務要約・自己PR 提案の生成時に Agent が参照するデータからブログスコアが失われる**。

`blog_context` は context_builder だけの内部変数ではなく **Agent の入力契約の一部**になっており、以下が同フィールドを前提にしている。`context_builder.py` から `_build_blog_context` を消すだけでは prompt・test と乖離するため、**#519 で以下を同一 PR で必ず一緒に更新する**（契約移行として扱う）:

- `backend/app/prompts/agent_career_summary.md`（`# GitHub・ブログ情報の使い方` 節の `blog_context` 参照・ブログ言及の指示）
- `backend/app/prompts/agent_self_pr.md`（同上。`blog_context` を自己 PR の根拠に使う指示・ブログ発信への言及）
- `backend/tests/test_agent.py`（`test_chat_career_summary_includes_github_and_blog_context` 等、user_prompt に `blog_context` が含まれることを assert）
- `backend/tests/test_agent_context_builder.py`（`test_blog_context_*` 系の `result["blog_context"]` アサーション一式）

トレードオフの受容:

- そもそもブログスコアは経歴書へ還流しておらず、Agent への注入も補助的な位置付けだったため、要約品質への影響は限定的と判断する。
- ADR-0010 の DB 非更新原則・context_builder の責務境界（スキーマ / プロンプトの責務分離）は不変。今回の変更は「入力データ 1 種の削除」であり、prompt・test を随伴させることで契約の内部整合を保つ（`.claude/rules/backend/test.md`「契約変更時の assert 見直し」に沿う）。

## 代替案

- **スコアリングだけ外して一覧は残す**: 逆効果の指摘には応えるが、経歴書への還流がない島がそのまま残り、保守・外部仕様追従コストは消えない。中途半端な dead feature が残るため却下。
- **休眠のまま温存する**: 将来ブログ活用の余地を残せるが、還流のない機能の保守・依存追従・codegen 同期コストが継続する。利用価値が低い以上、温存の利点は薄いと判断し却下。
- **コードだけ消して DB テーブルは残す**: schema drift と「使われていないテーブル」が残る。ADR-0008 と同様、完全撤去の方が状態が単純になるため却下。

## トレードオフ・既知のリスク

- Agent コンテキストからブログスコアが消える（上記「Agent への波及」）。
- 将来ブログ連携を再導入する場合は、テーブル・router・service・web ページをゼロから再構築する必要がある（ただし git 履歴と本 ADR から設計を復元可能）。
- blog 系の公開 API パス・レスポンス型の削除は OpenAPI 生成物・web の型に波及する破壊的変更。外部にこの API を消費するクライアントがいないことを前提とする。

## 撤去の前提条件（#519 の実装ゲート）

blog 系の公開 API パス削除は破壊的変更のため、#519 の実装前に以下を検証ゲートとして満たす。

- **内部消費者の不在確認**: web 側の blog API 参照（`web/src/api/blog.ts` とその利用箇所）が本 PR の撤去対象に完全に含まれ、撤去後に `/api/blog/*` を叩くコードが web に残らないことを確認する（`grep` で `/api/blog` の残存 0 を確認）。
- **外部消費者の不在確認**: 本 API は認証（GitHub OAuth + Cookie）必須の自サービス専用で、外部に公開クライアント・ドキュメント・API キー発行の仕組みを持たない。この前提のもと外部消費者は存在しないものとして撤去する。
- 万一いずれかの検証で消費者が見つかった場合は、撤去のみの計画を撤回し、非推奨化・移行導線を用意する計画（deprecation / migration plan）に切り替える。

## 将来の移行条件

- ブログ連携を再開する場合は、本 ADR を `Superseded` とした上で新規 ADR を起票し、「経歴書への還流」を設計の前提に組み込む（一覧 + スコア止まりの島を再び作らない）。
- 投稿頻度スコアを再導入する場合は、ブランクのあるユーザに逆効果とならない提示方法（スコアではなく事実の列挙など）を設計段階で解消すること。

## 設計原則との関係

- **P6（可逆性を設計する）**: 撤去は git 履歴と本 ADR から復元可能な可逆操作として実施する。全量列挙により、再導入時の設計復元コストを下げる。
- **P1（コスト最適化を第一制約にする）**: 還流のない機能の保守・外部仕様追従・codegen 同期コストを削減し、以降の機能整理（#517）で Agent 周りを最小構成に保つ。

## 関連リンク

- [#517 機能整理・体験改善ロードマップ](../../README.md)（親 issue。ブログ撤去の議論の結論）
- #518（本 ADR 起票の issue）／#519（撤去実装 PR）
- [ADR-0008: LLM プロバイダ抽象化の撤去とルールベース設計への統一](0008-remove-llm-to-rule-based-design.md)（撤去 ADR の手本）
- [ADR-0010: DevForge Agent 機能の導入](0010-devforge-agent.md)
