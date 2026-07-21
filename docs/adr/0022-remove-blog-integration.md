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
- 上記に紐づくテスト一式

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

- これは既知のトレードオフとして受容する。そもそもブログスコアは経歴書へ還流しておらず、Agent への注入も補助的な位置付けだったため、要約品質への影響は限定的と判断する。
- ADR-0010 の DB 非更新原則・context_builder の責務は不変。`_build_blog_context` の削除は入力データの縮小であり、Agent の契約（スキーマ / プロンプトの責務分離）には触れない。

## 代替案

- **スコアリングだけ外して一覧は残す**: 逆効果の指摘には応えるが、経歴書への還流がない島がそのまま残り、保守・外部仕様追従コストは消えない。中途半端な dead feature が残るため却下。
- **休眠のまま温存する**: 将来ブログ活用の余地を残せるが、還流のない機能の保守・依存追従・codegen 同期コストが継続する。利用価値が低い以上、温存の利点は薄いと判断し却下。
- **コードだけ消して DB テーブルは残す**: schema drift と「使われていないテーブル」が残る。ADR-0008 と同様、完全撤去の方が状態が単純になるため却下。

## トレードオフ・既知のリスク

- Agent コンテキストからブログスコアが消える（上記「Agent への波及」）。
- 将来ブログ連携を再導入する場合は、テーブル・router・service・web ページをゼロから再構築する必要がある（ただし git 履歴と本 ADR から設計を復元可能）。
- blog 系の公開 API パス・レスポンス型の削除は OpenAPI 生成物・web の型に波及する破壊的変更。外部にこの API を消費するクライアントがいないことを前提とする。

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
