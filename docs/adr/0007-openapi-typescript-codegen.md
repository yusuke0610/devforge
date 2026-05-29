# ADR-0007: OpenAPI → TypeScript 型コード生成の導入検討

## ステータス

Proposed

> 本 ADR は「BE の Pydantic schema と FE の TypeScript 型の二重定義に対し、OpenAPI から TS 型を自動生成する仕組みを導入するか」の判断材料であり、採用確定ではない。
> 後述の Phase 1 パイロット（生成パイプライン基盤の構築 + 1 ドメインの試験移行）の結果を見て `Accepted` への昇格、または `Deprecated`（現状の手動同期を継続）を判断する。
> 本 ADR の起票自体は領域横断リファクタ（`XR_apply`）のスコープ内だが、**パイプライン実装と型移行は本 ADR が定義する後続 PR で行う**（codegen は重い投資であり、env/docs 修正と束ねるとレビュー不能になるため）。

## コンテキスト

DevForge は backend（FastAPI + Pydantic）が REST API の DTO を `backend/app/schemas/**` で定義し、frontend（React + TypeScript）が同じ構造を `frontend/src/types.ts` / `frontend/src/api/*.ts` に**手書きで再定義**している。両者は言語境界で分断されており、フィールド構造（snake_case まで）が一致するよう人手で同期している。

現状の構成と痛み:

- **手動同期の規律は高い**: 一部はクロス参照コメントまで備える。例として `frontend/src/api/shared.ts` は冒頭に「backend の `app/schemas/shared.py` に対応する」と明記し、`frontend/src/api/githubLink.ts` は backend `schemas/github_link.py` と同名・同構造の interface を持つ。
- **ドリフト検知機構が無い**: backend でフィールド追加・rename・型変更を行っても、frontend 側は**型エラーにならず**、ランタイムで `undefined` を踏むまで気づけない。現状は目視同期で破綻していないが、規律に依存しており機械的な保証が無い。
- **対照的にエラーコードは型縛りで守られている**: `backend/app/core/errors.py:ErrorCode`（列挙）↔ `frontend/src/constants/errorCodes.ts:ERROR_CODES` は、`errorMessages.ts` が `Record<ErrorCodeKey, ...>` でキー網羅漏れを **TypeScript の型エラーとして検知**する。DTO にも同等の「漏れたらビルドで落ちる」仕組みが望ましい。
- **API パスは既に FE 側 SSoT が成立**: `frontend/src/api/paths.ts` に `PATHS` として完全集約済み。DTO だけが機械検知の穴として残っている。

機械検出（jscpd）は `.py` と `.ts` を別トークナイザで扱うため cross-realm clone を検出できず（実測 0 件）、DTO の二重定義は**目視でしか捕捉できない最大の盲点**である（領域横断レビュー `report/XR_report_20260529_1006.md` の Medium 指摘）。

該当する DTO ペア（フィールド構造がほぼ完全一致）:

| backend schema | frontend 型 |
|---|---|
| `schemas/github_link.py`（`ContributionDay` / `ContributionCalendar` / `GitHubLinkResponse` / `CachedGitHubLinkResponse`） | `api/githubLink.ts` |
| `schemas/resume.py`（`Experience` / `ResumeBase` / `ResumeResponse`） | `types.ts`（`CareerExperience` / `CareerResumePayload` / `CareerResumeResponse`） |
| `schemas/shared.py`（`TaskStatusResponse` / `SubProgress` / `ProgressResponse`） | `api/shared.ts` |
| `schemas/master_data.py`（`MasterItem` / `TechStackMasterItem`） | `types.ts` |
| `schemas/blog.py`（`BlogAccountResponse` / `BlogArticleResponse`） | `types.ts`（`BlogAccount` / `BlogArticle`） |
| `schemas/auth.py`（`TokenResponse`） | `api/auth.ts`（`AuthResponse`） |

## 決定内容

FastAPI が出力する OpenAPI スキーマから **`openapi-typescript`** で TypeScript 型を生成するパイプラインを導入する案を提示する。導入する場合の方針は以下のとおり。

### 基本方針

- **backend（Pydantic schema）を DTO の Single Source of Truth とする**。frontend の手書き型は生成物に置き換えていく。
- 生成先は `frontend/src/api/generated.ts`（コミット対象・**手編集禁止**をファイル冒頭コメントで明示）。
- **`request<T>()`（`api/client.ts`）の 401 リフレッシュ・CSRF・Cookie 認証ロジックは一切変更しない**。生成された型を `request<T>()` の型引数として渡すだけにする。
- **API パスの SSoT である `api/paths.ts` は維持**する。codegen は型のみを対象とし、パス定数は置き換えない。

### パイプライン構成

1. **OpenAPI エクスポート**: backend の FastAPI app から `app.openapi()` を JSON にダンプする backend スクリプト（`backend/scripts/export_openapi.py` 想定）を追加。出力は `backend/openapi.json`（または一時ファイル）。
2. **型生成**: `openapi-typescript` を frontend の devDependency に追加し、`backend/openapi.json` → `frontend/src/api/generated.ts` を生成。
3. **make ターゲット**: 既存の Nix devshell ラップ規約（`.claude/CLAUDE.md`）に従い、`make codegen-types`（= openapi エクスポート + 型生成）を追加。`Makefile` は `nix develop --command bash -c "..."` でラップする。
4. **CI ドリフト検知**: CI で `make codegen-types` を実行し、`git diff --exit-code frontend/src/api/generated.ts` が非ゼロなら fail させる。これにより「backend を変えたのに型を再生成していない」状態をビルドで落とす（エラーコードの型縛りと同じ思想）。

### 段階移行プラン

採用する場合は以下の順で進める。Phase 1 をパイロットとし、効果を見てから先へ進む。

| Phase | 対象 | 内容 | リスク |
|---|---|---|---|
| 0 | 基盤 | `export_openapi.py` / `openapi-typescript` 依存追加 / `make codegen-types` / `generated.ts` 初回生成 / CI ドリフト検知 | 中 |
| 1 | 読み取り（パイロット） | `api/shared.ts`（`TaskStatusResponse` 系）を `generated.ts` の型へ置換。手書き interface を `type X = components["schemas"]["..."]` の再エクスポートに変更 | 低〜中 |
| 2 | 主要レスポンス | `api/githubLink.ts` / `schemas/github_link.py` 系、`api/auth.ts` の `AuthResponse` を移行 | 中 |
| 3 | フォーム入出力含む | `types.ts` の `CareerResume*` / `BlogAccount` / `MasterItem` 系を移行。`payloadBuilders.ts` / `formMappers.ts` への影響を確認 | 中〜高 |

### 移行しないもの（重要）

- **`api/client.ts` の 401/CSRF ロジック**: 変更しない。
- **`api/paths.ts` の `PATHS`**: API パスの SSoT として維持（codegen 対象外）。
- **`frontend/src/constants/errorCodes.ts` / `errorMessages.ts`**: エラーコードは既に型縛りで守られており、OpenAPI codegen とは別系統。本 ADR の対象外。
- **`formTypes.ts` のクライアント専用フォーム状態**: サーバ DTO ではないため対象外。

## 代替案

| 選択肢 | 評価 |
|---|---|
| 現状維持（手動同期 + クロス参照コメント） | 既存資産はそのまま活きるが、ドリフトをビルドで検知できず規律依存のまま。フィールド rename 事故のリスクが残り続ける |
| `openapi-typescript`（本案） | 型のみ生成・ランタイム依存ゼロ・`request<T>()` と非干渉。生成物が大きくなりがちだが影響は型レイヤに閉じる |
| `orval` / `openapi-generator`（クライアント生成） | fetch クライアントごと生成するため、自前の 401/CSRF 付き `request<T>()` と二重化する。既存資産を捨てることになり不適 |
| Pydantic → TS を独自スクリプトで変換 | OpenAPI を経由しないため FastAPI のレスポンスモデル（`response_model`）との整合が取れず、独自実装の保守コストが高い |

## トレードオフ・既知のリスク

1. **生成物の肥大**: `generated.ts` は全 schema を含むため大きくなる。型のみで本番バンドルには乗らない（`import type`）が、差分レビューのノイズにはなる。手編集禁止コメントで誤編集を防ぐ。
2. **backend app の import コスト**: openapi エクスポートは FastAPI app を import する必要があり、WeasyPrint 等のネイティブ依存解決のため **Nix devshell 経由必須**（生シェル直叩き禁止。`.claude/CLAUDE.md` 準拠）。
3. **CI 実行時間の増加**: codegen + `git diff` チェックのステップが増える。
4. **命名差の吸収**: 現行 FE は backend と別名（`CareerResumeResponse` ↔ `ResumeResponse`）を使う箇所がある。移行時は再エクスポート（`export type CareerResumeResponse = components["schemas"]["ResumeResponse"]`）で名前を保ち、呼び出し側の破壊を避ける。
5. **`response_model` 未設定エンドポイントの穴**: OpenAPI に型が出ない（`/auth/me` は `response_model=TokenResponse` を確認済みだが、未設定箇所があると生成されない）。移行前に backend 全 router の `response_model` 付与状況を棚卸しする必要がある。
6. **E2E 影響**: github 連携・ブログ・通知の UI フローに関わる型を移行するため、Phase 2 以降は `npm run test:e2e` 必須。

## 将来の移行条件

- **Accepted への昇格条件**: Phase 0 + Phase 1 パイロットが `make ci` green を満たし、CI ドリフト検知が機能する（backend schema をわざと変えると CI が落ちる）ことを確認できること。
- **Deprecated（現状維持）への判断**: 生成物の肥大・CI コスト・命名吸収の手間が、手動同期で足りている現状の規律に見合わないと判断した場合は、本 ADR を `Deprecated` にし現状の手動同期 + クロス参照コメントを継続する。
- backend の `response_model` 付与が不完全で OpenAPI に型が出ない場合は、先に backend 側の `response_model` 整備を別タスクで完了させる。

## 関連リンク

- 領域横断レビュー: `report/XR_report_20260529_1006.md`（Medium: DTO 二重定義のドリフト検知不在）
- [frontend/src/api/client.ts](../../frontend/src/api/client.ts) — fetch ラッパー（401/CSRF、変更対象外）
- [frontend/src/api/paths.ts](../../frontend/src/api/paths.ts) — API パス SSoT（codegen 対象外）
- [frontend/src/api/shared.ts](../../frontend/src/api/shared.ts) — Phase 1 パイロット対象
- [backend/app/core/errors.py](../../backend/app/core/errors.py) — エラーコードの型縛り（DTO 検知機構の手本）
- openapi-typescript 公式ドキュメント: https://openapi-ts.dev/
