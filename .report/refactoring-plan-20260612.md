# DevForge 全体リファクタリング計画書

- **作成日**: 2026-06-12
- **対象**: backend / frontend / infra / CI / docs の全領域
- **目的**: 蓄積した技術的負債をフェーズ分けで段階的に解消し、保守性・テスト容易性・CI 効率を改善する
- **調査方法**: 全領域のソースコード静的調査（ファイルサイズ・責務分離・重複・テスト状態・デッドコード）

---

## エグゼクティブサマリー

調査の結論として、このコードベースは**基盤は健全**（セキュリティ・エラーハンドリング・型生成・ADR 運用は整備済み、TODO/FIXME はほぼゼロ、明確なデッドコードなし）だが、以下の 4 系統の負債が蓄積している。

| 系統 | 代表例 | 深刻度 |
|---|---|---|
| **巨大モジュールの責務混在** | FE `CareerResumeForm.tsx`（534 行・4 モーダル同居）、BE `pdf/generators/resume_generator.py`（408 行・HTML+CSS+WeasyPrint 混在） | 高 |
| **層の境界侵食** | BE router へのビジネスロジック漏れ（`blog/accounts.py`・`github_link.py`）、ORM model への表示ロジック混在（`models/resume.py`） | 高 |
| **CI/インフラの構造的重複** | デプロイジョブ 6 個がほぼ同一（dev/stg/prod × FE/BE）、WeasyPrint ライブラリの重複インストール | 中 |
| **テストの偏り** | BE: 1 ファイル 900 行超の巨大テスト・`_extended` 分裂、FE: API 層・Redux slice・E2E エラーパスが手薄 | 中 |

全 6 フェーズ構成。**各フェーズは独立して PR 化でき、途中で止めても価値が残る**順序で並べている。総工数目安は 40〜60 時間。

```text
Phase 0 ─→ Phase 1 ─→ Phase 2 (BE) ─┬─→ Phase 4 (テスト補強)─→ Phase 5 (CI/インフラ) ─→ Phase 6 (仕上げ)
                       Phase 3 (FE) ─┘
                       ※ Phase 2 と 3 は並行可能
```

---

## Phase 0: 計測基盤とベースライン確定（前提作業）

**目的**: 「リファクタの効果を測れる状態」を先に作る。以降の全フェーズの判断基準になる。

**工数目安**: 2〜3h ／ **リスク**: なし（コード変更を伴わない）

### 作業項目

| # | 作業 | 対象 |
|---|---|---|
| 0-1 | `make dupe-check` を実行して jscpd ベースラインを確定。`report/dupe/jscpd-report.json` の重複率を本計画書に追記し、各フェーズ完了時に比較する | `.jscpd.json` / `report/dupe/` |
| 0-2 | テストカバレッジの現状値を記録（BE: pytest-cov、FE: vitest coverage）。未導入なら計測だけでも一度実行して数値を控える | `backend/tests/` / `frontend/src/` |
| 0-3 | 行数ベースラインの記録: BE app/ 10,266 行・tests/ 8,454 行、FE src/ 約 17,900 行（generated.ts 除く）を起点として記録 | 本ドキュメント |
| 0-4 | 各フェーズの PR 粒度を確認: 1 PR = 1 フェーズ内の 1〜3 項目を上限とし、`make ci` green を必須ゲートとする | 運用ルール |

### 完了条件

- jscpd ベースライン数値が記録されている
- 以降のフェーズで「重複率・行数・カバレッジが悪化していないこと」を機械的に確認できる

---

## Phase 1: 即効性の高い負債解消（クイックウィン）

**目的**: リスクが低く独立性の高い項目を先に片付け、後続フェーズのノイズを減らす。

**工数目安**: 4〜6h ／ **リスク**: 低（1-1 のみ本番シークレット操作を伴うため要注意）

### 作業項目

| # | 作業 | 対象 | 備考 |
|---|---|---|---|
| 1-1 | **FIELD_ENCRYPTION_KEY の棚卸し TODO 解消**: `infra/modules/cloud_run/main.tf:14-16` に「廃止予定」と明記されたまま残置。Secret Manager・Cloud Run env・`env_keys.py` の 4 箇所同期手順に従って削除、または廃止しない判断なら TODO コメントを更新 | `infra/modules/cloud_run/main.tf` / `backend/app/core/env_keys.py` / `docs/api.md` / `docker-compose.yml` | **破壊的変更の可能性**。本番影響を確認してから着手 |
| 1-2 | **BE テストファイルの統合**: `test_blog_collector.py`（237 行）+ `test_blog_collector_extended.py`（364 行）を 1 ファイルに統合し、重複 fixture を削除 | `backend/tests/` | Phase 2 の collector 分割の前提整理 |
| 1-3 | **ADR の整理**: ADR-0009 の番号重複（textlint / toast の 2 件）の整理方針決定、ADR-0004 に superseded by 0008 の明記 | `docs/adr/` | docs のみ |
| 1-4 | **cleanup スクリプトの導線整備**: `scripts/cleanup_docker_images.sh` / `cleanup_secret_versions.sh` が Makefile にもドキュメントにも未記載。`docs/runbooks/` に手順を記載するか Makefile ターゲット化 | `scripts/` / `Makefile` / `docs/` | |
| 1-5 | **`response_mapper.py`（15 行）の妥当性判断**: 薄すぎるモジュール。`github_link_service.py` への吸収を検討（Rule of Three 観点で利用箇所が 1 つなら吸収） | `backend/app/services/intelligence/` | |

### 検証

```bash
make ci                # 1-2, 1-5
make infra-validate    # 1-1
```

### 完了条件

- インフラの TODO コメントがゼロ
- `_extended` 命名のテストファイルがゼロ
- ADR の番号体系と supersede 関係が一貫

---

## Phase 2: Backend 責務分離（コア）

**目的**: 層の境界（router / service / repository / model）を回復し、巨大モジュールを分割する。本計画の本丸その 1。

**工数目安**: 10〜14h ／ **リスク**: 中（契約変更を伴わない内部リファクタに限定すれば低い）

**実行手段**: `BE_refacter` スキルで詳細レビュー → `BE_apply` で適用、の既存フローに乗せることを推奨。

### 2A. 巨大モジュールの分割

| # | 作業 | 現状 | 分割案 |
|---|---|---|---|
| 2A-1 | **PDF generator の 3 分割** | `services/pdf/generators/resume_generator.py`（408 行）に HTML 組み立て・CSS ロード・WeasyPrint 統合が混在 | `resume_generator_html.py`（HTML 組み立て）/ CSS・フォント定義モジュール / `resume_generator.py`（WeasyPrint 統合・公開 API）。公開 API のシグネチャは変えない |
| 2A-2 | **blog/collector の 2 層分割** | `services/blog/collector.py`（311 行）に Zenn/note/Qiita の HTTP fetch・正規化・存在確認が同居 | `blog/fetcher.py`（プラットフォーム別 HTTP fetch）+ `blog/account_service.py`（既存 53 行を拡張: 正規化・存在確認・登録オーケストレーション） |
| 2A-3 | **contributions.py の分割** | `services/intelligence/github/contributions.py`（249 行）に GitHub API 呼び出しと分析ロジックが混在 | `github/contributions.py`（API 呼び出しのみ）+ `intelligence/contribution_analyzer.py`（分析ロジック） |

### 2B. 層の境界回復

| # | 作業 | 現状の問題 | 修正方針 |
|---|---|---|---|
| 2B-1 | **blog/accounts router からロジック除去** | `routers/blog/accounts.py:75-96` で `normalize_username()` / `verify_user_exists()` を collector から直接 import し、外部 API の例外→HTTPException 変換が router に露出 | 2A-2 の `account_service` 経由に変更。例外→HTTP コード変換は `core/errors.py` の既存機構（`raise_app_error`）に寄せる |
| 2B-2 | **github_link router のキャッシュ初期化を repository へ** | `routers/github_link.py` の `_get_or_create_cache()` が router 内に DB クエリを持つ | repository（または `dispatch_service`）へ移設。`IntegrityError` 後の再 SELECT `None` 判定ルール（CLAUDE.md「失敗から学んだ知見」）を遵守 |
| 2B-3 | **Resume model から表示ロジック除去** | `models/resume.py`（336 行）が `sort_utils` を import し、`@property` でソート済みリストを返す | ソートは利用側（schema 変換 or service）で `sort_utils` を直接呼ぶ。model は ORM 定義に専念 |
| 2B-4 | **blog repository の `upsert_many` 簡素化** | `repositories/blog.py` の `upsert_many()` が正規化＋複数アカウント横断バッチを抱える | 正規化は service 層（2A-2 の account_service / sync_service）へ引き上げ、repository は単純な upsert に縮小 |

### 注意事項

- `app/services/agent/` と `tasks/` は調査の結果**設計良好**（ADR-0010 準拠・責務分離済み）。**このフェーズでは触らない**。agent 配下を触る場合は `.claude/rules/backend/agent.md` の事前読了が必須
- `app/schemas/` / `app/routers/` のシグネチャ・docstring に触れた場合は **`make codegen-types` → `frontend/src/api/generated.ts` のコミットが必須**（codegen-drift CI）
- タスクハンドラの黙殺 return 禁止・例外握りつぶし禁止ルールを分割時に維持する

### 検証

```bash
make codegen-types && git diff frontend/src/api/generated.ts   # スキーマ/ルーター変更時
make ci
```

### 完了条件

- 400 行超の BE モジュール（テスト・マイグレーション除く）がゼロ
- router 内の DB クエリ・外部 API 例外ハンドリングがゼロ
- model が `sort_utils` を import していない
- jscpd 重複率が Phase 0 ベースラインから悪化していない

---

## Phase 3: Frontend 責務分離（コア・Phase 2 と並行可能）

**目的**: ページコンポーネントの肥大化と props drilling を解消する。本丸その 2。

**工数目安**: 10〜14h ／ **リスク**: 中（UI 挙動の回帰リスク → E2E 必須）

**実行手段**: `FE_refacter` スキルで詳細レビュー → `FE_apply` で適用を推奨。

### 3A. 巨大コンポーネント・フックの分割

| # | 作業 | 現状 | 分割案 |
|---|---|---|---|
| 3A-1 | **CareerResumeForm の分割** | `components/forms/CareerResumeForm.tsx`（534 行）に 10+ フック・3 モーダル状態・4 モーダルコンポーネント・セクション組立・ドラフト復元が同居 | モーダル群を `CareerResumeFormModals.tsx`（仮）へ分離し、開閉状態は専用フック（`useCareerFormModals` 等）に集約。目標 350 行以下 |
| 3A-2 | **useCareerDirty の分割** | `hooks/career/useCareerDirty.ts`（273 行）が experience/client/project/qualification の 4 型の dirty 判定を 5 層ネストで一元処理 | 階層別フック（`useExperienceDirty` / `useProjectDirty` 等）に分割。deep equal 比較の単体テストを各階層に付ける |
| 3A-3 | **useCareerExperienceMutators の分割** | `hooks/career/useCareerExperienceMutators.ts`（210 行）が 13 個のハンドラを返す | client 系ミューテータを `useClientMutators` へ分離 |
| 3A-4 | **AgentChatWidget の UI/ロジック分離** | `components/forms/AgentChatWidget.tsx`（351 行）にパネル操作（ドラッグ・リサイズ）とチャット送受信が混在 | パネル操作を独立フック/コンポーネントへ。チャットロジックは既存 `useAgentChat` へ寄せる |

### 3B. props drilling の解消

| # | 作業 | 現状 | 修正方針 |
|---|---|---|---|
| 3B-1 | **CareerFormContext の導入** | `CareerExperienceEditor.tsx`（327 行・12+ props）→ `ClientEditor` へ 6+ ハンドラを素通しで 3 層 drilling | mutation ハンドラ群を Context で一括提供。3A-3 の分割後に実施すると Context の形が決めやすい |

### 3C. バリデーションの階層化

| # | 作業 | 現状 | 修正方針 |
|---|---|---|---|
| 3C-1 | **payloadBuilders のバリデータ分割** | `payloadBuilders.ts`（448 行）の `validateCareerForm()` が 5 層を all-in-one 検証 | experience / client / project 層別のバリデータへ分割。`payloadBuilders.test.ts`（838 行）も対応して分割 |

### 注意事項

- **E2E 必須トリガーに該当**（レイアウト・フォームフロー変更）。`nix develop --command bash -c "cd frontend && npm run test:e2e"` を各 PR で実行
- メッセージは引き続き `constants/messages.ts` 経由。リテラル直書きは `make lint-frontend-messages` で検知される
- `api/generated.ts` は触らない（codegen 管理）

### 完了条件

- 400 行超の FE コンポーネント・フック（テスト・generated 除く）がゼロ
- `CareerExperienceEditor` → `ClientEditor` のハンドラ素通し props がゼロ
- E2E 全シナリオ green

---

## Phase 4: テスト補強（Phase 2・3 の変更を固定化）

**目的**: リファクタ後の構造を回帰テストで固定し、調査で判明した手薄領域を埋める。

**工数目安**: 8〜10h ／ **リスク**: 低

### Backend

| # | 作業 | 対象 |
|---|---|---|
| 4-1 | **巨大テストの責務分割**: `test_agent.py`（921 行）・`test_endpoints.py`（427 行）・`test_schemas.py`（425 行）を対象モジュール単位に分割。テスト名と実装の対応を回復 | `backend/tests/` |
| 4-2 | **drift 検知テストの横展開**: `test_scope_limits_match_resume_schema` 型の schema↔model 整合テストを他の model/schema ペアに拡張 | `backend/tests/` |

### Frontend

| # | 作業 | 対象 |
|---|---|---|
| 4-3 | **API ドメイン別テスト追加**: 現状 `client.test.ts` のみ。`resumes` / `blog` / `githubLink` 各 API の成功・失敗・リトライをテスト | `frontend/src/api/` |
| 4-4 | **Redux formCacheSlice のテスト追加**: cache/clear/persist のテストが皆無。ページ遷移時のデータ喪失を回帰防止 | `frontend/src/store/` |
| 4-5 | **CareerFormEditors のコンポーネントテスト**: Experience/Client エディタはテストゼロ。Phase 3 の分割後の形でテストを書く | `frontend/src/components/forms/CareerFormEditors/` |
| 4-6 | **E2E エラーパス追加**: バリデーション失敗・ネットワークエラー・タイムアウトのシナリオ（現状ゴールデンパスのみ） | `frontend/e2e/` |

### 注意事項

- **DB をモックしない**（CLAUDE.md: 統合テストは実 DB のテスト用 SQLite セッションに当てる）
- 契約を変えた箇所は旧契約を固定化したテストの assert・テスト名の両方を見直す

### 完了条件

- 500 行超のテストファイルがゼロ（分割困難な統合テストは例外として明記）
- FE API 層・Redux slice にテストが存在
- カバレッジが Phase 0 ベースラインから向上

---

## Phase 5: CI / インフラ最適化

**目的**: CI の構造的重複を除去し、実行時間を短縮する。アプリコードと独立なので最後でよいが、効果は全 PR に波及する。

**工数目安**: 6〜8h ／ **リスク**: 中（デプロイパイプライン変更のため stg で先行検証）

**実行手段**: infra 部分は `INFRA_refacter` → `INFRA_apply` フローを推奨。

### CI（.github/workflows/ci.yml: 591 行・15 ジョブ）

| # | 作業 | 現状 | 修正方針 |
|---|---|---|---|
| 5-1 | **デプロイジョブの統合** | `deploy-frontend` / `-stg` / `-prod` と `deploy-backend` / `-stg` / `-prod` の 6 ジョブがほぼ同一（差分は env/secrets のみ） | reusable workflow（`workflow_call` + environment 入力）または matrix 化で 2 ジョブに集約。**dev → stg → prod の順に 1 環境ずつ検証してから展開** |
| 5-2 | **WeasyPrint インストールの共通化** | `test-backend`（L199-204）と `codegen-drift`（L249-254）で同一の apt-get install を重複実行 | composite action 化 + apt キャッシュ。flake.nix（L38-46）のライブラリ一覧との二重管理はコメントで相互参照を明記 |
| 5-3 | **Playwright ブラウザのキャッシュ** | `test-e2e` で毎回 `npx playwright install chromium --with-deps` | `~/.cache/ms-playwright` を actions/cache でキャッシュ |

### インフラ（OpenTofu）

| # | 作業 | 現状 | 修正方針 |
|---|---|---|---|
| 5-4 | **cloud_run env ブロックの整理** | `infra/modules/cloud_run/main.tf`（190 行）で env ブロック 30 行・secret_env 6 個が逐次列挙 | `dynamic "env"` + locals の map 化で宣言的に。`env_keys.py` / `docs/api.md` との 4 箇所同期の正本関係をコメントで明記 |
| 5-5 | **symlink 整合性の自動検証** | `environments/{dev,stg,prod}` の symlink 統合は手動運用。新規ファイル追加時に壊れても気づけない | pre-commit hook または CI ステップで symlink 先の存在チェックを追加。`.jscpd.json` の ignore 追記漏れも同時に検知 |

### 注意事項

- デプロイジョブ変更は **必ず dev 環境で 1 度デプロイを通してから** stg / prod に展開
- セキュリティ上の意図がある「デプロイジョブで npm キャッシュを復元しない」設計は維持する（統合時に消さないこと）

### 完了条件

- ci.yml のデプロイ系ジョブ定義が 6 → 2（+ 呼び出し）に削減
- WeasyPrint install の記述が 1 箇所
- `make infra-validate` green、dev 環境での実デプロイ成功

---

## Phase 6: 仕上げ・再発防止

**目的**: リファクタ成果を制度として固定し、負債の再蓄積を防ぐ。

**工数目安**: 3〜4h ／ **リスク**: 低

| # | 作業 | 内容 |
|---|---|---|
| 6-1 | **jscpd threshold の引き上げ** | `.jscpd.json` は現在 Phase 1 運用（`threshold` warn-only）。Phase 0 比で改善したベースラインを元に fail 閾値を設定し、CI の `detect-duplication` を enforcing に切り替え |
| 6-2 | **ファイルサイズの lint 化検討** | 「400 行超で警告」のような機械チェックを ESLint（`max-lines`）/ ruff 系で導入するか判断。導入しない場合も判断理由を記録 |
| 6-3 | **ADR の起票** | 本リファクタで行った構造判断（CareerFormContext 導入、CI reusable workflow 化など）のうち ADR に値するものを `CONTRIBUTING.md` の運用ルールに従って起票 |
| 6-4 | **docs 更新** | `docs/development.md` / `.claude/rules/` のうち、分割後のディレクトリ構成・新モジュール配置に言及している箇所を更新 |
| 6-5 | **効果測定** | Phase 0 のベースライン（重複率・行数・カバレッジ・CI 実行時間）と最終値を比較し、本ドキュメント末尾に結果を追記 |

---

## 触らないと決めたもの（スコープ外）

調査の結果、以下は健全と判断したため**意図的にスコープ外**とする。「動いているものを壊さない」ため。

| 領域 | 理由 |
|---|---|
| `backend/app/services/agent/`・`tasks/` | ADR-0010 準拠で責務分離済み。worker のセッション管理は複雑だが Hrana 失効対策としてコメント・テスト完備 |
| `backend/app/core/`（errors / settings / env_keys / security） | エラーコード一元化・環境変数管理は SSoT として機能している |
| `frontend/src/api/client.ts`・`constants/messages.ts` 系 | 401 リフレッシュ・CSRF・メッセージ SSoT は設計良好。ESLint 監視も機能 |
| `infra/environments/` の symlink 統合 | 物理統合済み。Phase 5-5 の自動検証追加のみ |
| `monitoring/` モジュール | 責務別ファイル分割済み |
| タスクハンドラ抽象（handlers/base.py） | 実装が GITHUB_LINK 1 種でややオーバーエンジニアリングだが、削るコストの方が高い。新規タスク追加時に再評価 |
| PDF/Markdown generator の期間フォーマット差異 | 出力形式依存の意図的な分離（偶発的重複ではない） |

---

## 運用ルール（全フェーズ共通）

1. **1 PR = 1〜3 作業項目**。フェーズをまたぐ PR は作らない
2. 各 PR で `make ci` green が必須。schema/router 変更時は `make codegen-types`、UI フロー変更時は E2E を追加実行
3. ブランチは `refactor/<topic>` を `origin/main` 起点で作成
4. 各フェーズ完了時に `make dupe-check` を実行し、重複率がベースラインから悪化していないことを確認
5. 既存の skill フロー（`BE_refacter`→`BE_apply`、`FE_refacter`→`FE_apply`、`INFRA_refacter`→`INFRA_apply`、領域横断は `XR_refacter`）に乗せられる項目は乗せる
6. 「形は同じだが変更理由が違う」コードは抽出しない（`.claude/rules/common/duplication.md` の偶発的重複ポリシー遵守）

## 工数サマリー

| フェーズ | 内容 | 工数目安 | 依存 |
|---|---|---|---|
| Phase 0 | 計測基盤・ベースライン | 2〜3h | なし |
| Phase 1 | クイックウィン | 4〜6h | Phase 0 |
| Phase 2 | Backend 責務分離 | 10〜14h | Phase 1 |
| Phase 3 | Frontend 責務分離 | 10〜14h | Phase 1（Phase 2 と並行可） |
| Phase 4 | テスト補強 | 8〜10h | Phase 2・3 |
| Phase 5 | CI/インフラ最適化 | 6〜8h | なし（いつでも可、推奨は Phase 4 後） |
| Phase 6 | 仕上げ・再発防止 | 3〜4h | Phase 5 |
| **合計** | | **43〜59h** | |

## ベースライン記録欄（Phase 0 で記入）

| 指標 | Phase 0 時点 | 最終 |
|---|---|---|
| jscpd 重複率（全体） | （未計測） | |
| BE app/ 行数 | 10,266 | |
| BE tests/ 行数 | 8,454 | |
| FE src/ 行数（generated 除く） | 約 17,900 | |
| BE テストケース数 | 409 | |
| FE 単体テストファイル数 | 40 | |
| CI 所要時間（main push） | （未計測） | |
