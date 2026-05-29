# ADR-0007: OpenAPI → TypeScript 型コード生成の導入（完全移行）

## ステータス

Accepted

> 本 ADR は「BE の Pydantic schema と FE の TypeScript 型の二重定義に対し、OpenAPI から TS 型を自動生成する仕組みを導入するか」を扱う。
> **採用方針は確定**：OpenAPI → TypeScript 型生成を導入し、frontend の手書き DTO 型を生成物へ**完全移行**する（手書き interface を残したまま alias で FE 独自名を温存する折衷案は採らない。詳細は「決定内容」参照）。リリース前のため呼び出し側 rename コストが低く、踏み込んだ移行が可能と判断した。
> Phase 0（基盤構築）+ Phase 1（`api/shared.ts` パイロット移行）が完了し、`make ci` green と CI ドリフト検知の機能（backend schema をわざと変えると `git diff --exit-code frontend/src/api/generated.ts` が fail する）を確認できたため、status を `Accepted` に昇格した（2026-05-29）。後続 Phase 2 / 3 は本 ADR の方針に従って進める。前提が崩れた場合は `Deprecated`（現状の手動同期を継続）に倒す。
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

FastAPI が出力する OpenAPI スキーマから **`openapi-typescript`** で TypeScript 型を生成するパイプラインを導入する。frontend の手書き DTO 型は生成物へ完全移行する。方針は以下のとおり。

### 基本方針

- **backend（Pydantic schema）を DTO の Single Source of Truth とする**。frontend の手書き DTO 型は**全廃し、生成物へ完全移行する**（alias で FE 独自名を温存する折衷はしない）。
- **FE 独自名は廃し backend のクラス名に統一する**。`CareerResumeResponse` のような FE 独自名は呼び出し側ごと BE 名（`ResumeResponse`）へ rename する。`Career` のようなドメイン文脈プレフィックスは割り切って捨てる（命名統一マップは後述）。
- 生成先は `frontend/src/api/generated.ts`（コミット対象・**手編集禁止**をファイル冒頭コメントで明示）。
- ergonomics のため、生成物を **BE 名のまま 1:1 で再エクスポートする薄い層**（例 `frontend/src/api/types.ts`: `export type ResumeResponse = components["schemas"]["ResumeResponse"]`）を置く。呼び出し側は `components["schemas"][...]` を直書きせずこの再エクスポート名を使う。これは FE 独自名ではなく生成物の機械的ミラーであり、二重管理にはならない。
- **`request<T>()`（`api/client.ts`）の 401 リフレッシュ・CSRF・Cookie 認証ロジックは一切変更しない**。生成された型を `request<T>()` の型引数として渡すだけにする。
- **API パスの SSoT である `api/paths.ts` は維持**する。codegen は型のみを対象とし、パス定数は置き換えない。

### 命名統一マップ（FE 独自名 → BE 名）

完全移行では以下の FE 独自名を廃止し、backend のクラス名に統一する（呼び出し側ごと rename）。

| FE 独自名（廃止） | BE 名（統一先） |
|---|---|
| `TaskProgress`（`api/githubLink.ts`） | `ProgressResponse` |
| `AuthResponse`（`api/auth.ts`） | `TokenResponse` |
| `CareerExperience`（`types.ts`） | `Experience` |
| `CareerResumePayload`（`types.ts`） | `ResumeBase` |
| `CareerResumeResponse`（`types.ts`） | `ResumeResponse` |
| `BlogAccount`（`types.ts`） | `BlogAccountResponse` |
| `BlogArticle`（`types.ts`） | `BlogArticleResponse` |

既に BE と同名のため rename 不要（型定義の出どころを生成物へ差し替えるだけ）: `ContributionDay` / `ContributionCalendar` / `GitHubLinkResponse` / `CachedGitHubLinkResponse` / `MasterItem` / `TechStackMasterItem`。

### パイプライン構成

1. **OpenAPI エクスポート**: backend の FastAPI app から `app.openapi()` を JSON にダンプする backend スクリプト（`backend/scripts/export_openapi.py` 想定）を追加。出力は `backend/openapi.json`（または一時ファイル）。
2. **型生成**: `openapi-typescript` を frontend の devDependency に追加し、`backend/openapi.json` → `frontend/src/api/generated.ts` を生成。
3. **make ターゲット**: 既存の Nix devshell ラップ規約（`.claude/CLAUDE.md`）に従い、`make codegen-types`（= openapi エクスポート + 型生成）を追加。`Makefile` は `nix develop --command bash -c "..."` でラップする。
4. **CI ドリフト検知**: CI で `make codegen-types` を実行し、`git diff --exit-code frontend/src/api/generated.ts` が非ゼロなら fail させる。これにより「backend を変えたのに型を再生成していない」状態をビルドで落とす（エラーコードの型縛りと同じ思想）。

### 段階移行プラン

以下の順で進める。Phase 1 をパイロットとし、効果を見てから先へ進む。各 Phase は別 PR で実施する。

| Phase | 対象 | 内容 | リスク |
|---|---|---|---|
| 0 ✅完了 | 前提・基盤 | ①`response_model` 棚卸し（未設定 14 個を「DTO 不要」と「schema 化必要」に仕分け）②不足 schema 追加 + `response_model` 付与（`/github/login-url`→`GitHubLoginUrlResponse`、202 系→共通 `TaskAcceptedResponse`）③`backend/scripts/export_openapi.py` 追加 ④`openapi-typescript` を devDependency 追加 ⑤`make codegen-types`（Nix wrap）⑥`generated.ts` 初回生成 ⑦CI ドリフト検知（`git diff --exit-code`）| 中 |
| 1 ✅完了 | 読み取り（パイロット） | `api/shared.ts`（`TaskStatusResponse`）を完全移行。手書き interface を削除し、生成物の薄い再エクスポート層 `api/types.ts` へ統合。論点B（`str \| None`→`string \| null`）に伴い消費側 `useTaskPolling` / `useAsyncTaskPage` の `checkStatus` 契約を `string \| null` 許容へ更新。`make ci` green と「BE schema をわざと変えると `git diff --exit-code` が fail する」ことを確認済み | 低〜中 |
| 2 ✅完了 | 主要レスポンス | `api/githubLink.ts`（`TaskProgress`→`ProgressResponse`、`{status}`→`TaskAcceptedResponse`、`GitHubLinkResponse` / `Contribution*` / `CachedGitHubLinkResponse`）・`api/auth.ts`（`AuthResponse`→`TokenResponse`、login-url→`GitHubLoginUrlResponse`）を完全移行。`CachedGitHubLinkResponse.result` を backend で `GitHubLinkResponse \| None` に絞り OpenAPI へ出力（型安全の後退を防止）。論点B（生成型 optional 化）に伴い `useAsyncTaskPage` の loadCache / `ContributionHeatmap` の weeks を null 合体で追従。`make ci` green・backend 68 passed・E2E 22 passed・codegen 冪等を確認済み。request 型 `GitHubLinkPayload`（default 値あり）は論点A により手書き温存 | 中 |
| 3 | フォーム入出力含む | `types.ts` の `CareerResume*`（→`Resume*`）/ `BlogAccount`（→`BlogAccountResponse`）/ `MasterItem` 系を完全移行。`payloadBuilders.ts` / `formMappers.ts` の追従。E2E 必須 | 中〜高 |

> **完全移行の前提（Phase 0 に内包）**: 生成できるのは `response_model` 付きエンドポイントのみ（実測 40 中 26）。DTO を持つのに `response_model` 未設定のエンドポイント（`/github/login-url` の `{authorization_url, state}`、`/run`・`/run/retry` の `{status}`）を schema 化・付与する作業を、完全移行の前提として Phase 0 で実施する。これを怠ると「生成物と手書きが混在する中途半端な状態」になり完全移行が成立しない。

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

1. **生成物の肥大**: `generated.ts` は全 schema を含むため大きくなる。型のみで本番バンドルには乗らない（`import type`）が、差分レビューのノイズにはなる。手編集禁止コメントで誤編集を防ぐ。なお本 repo の schema は約 36 クラス（最大 `resume.py` 12 クラス）と小さく、肥大の影響は軽微。
2. **backend app の import コスト**: openapi エクスポートは FastAPI app を import する必要があり、WeasyPrint 等のネイティブ依存解決のため **Nix devshell 経由必須**（生シェル直叩き禁止。`.claude/CLAUDE.md` 準拠）。
3. **CI 実行時間の増加**: codegen + `git diff` チェックのステップが増える。
4. **完全移行に伴う一括 rename**: FE 独自名を BE 名へ統一するため呼び出し側を広範に rename する（命名統一マップ参照）。リリース前のため破壊的だが許容。`Career` 等のドメイン文脈プレフィックスは名前から失われる（割り切る）。
5. **入出力兼用 schema の `-Input`/`-Output` 分裂（論点A）**: 同一 Pydantic モデルを request body と response の双方に使うと、required/optional 解釈が入出力で変わるため openapi-typescript が 2 系統の型を生成しうる。`resume.py` の `ResumeBase` 等が候補。Phase 0 で入出力兼用 schema を棚卸しし、分裂が起きる箇所を把握する。
6. **optional/required の解釈ズレ（論点B）**: Pydantic のデフォルト値（例 `TokenResponse.is_github_user: bool = False`）は OpenAPI で optional 扱いになり、生成物が `is_github_user?: boolean` になりうる。手書きの required と乖離し呼び出し側が型エラー/挙動変化になる。移行時に「本当に optional で良いか」を BE schema 側で見直す好機とする。
7. **`response_model` 未設定エンドポイントの穴 / 新規 schema 命名（論点C）**: OpenAPI に型が出るのは `response_model` 付きのみ（実測 40 中 26）。完全移行の前提として Phase 0 で未設定箇所を棚卸し・付与する。匿名 `{...}` には BE 命名規約で名前を付ける（`/github/login-url`→`GitHubLoginUrlResponse`、202 受付応答は複数箇所で使い回せるため共通 `TaskAcceptedResponse` に集約して DRY 化）。
8. **E2E 影響**: github 連携・ブログ・通知の UI フローに関わる型を移行するため、Phase 2 以降は `npm run test:e2e` 必須。

## 将来の移行条件

- **Accepted への昇格条件**: Phase 0 + Phase 1 パイロットが `make ci` green を満たし、CI ドリフト検知が機能する（backend schema をわざと変えると CI が落ちる）ことを確認できること。
- **Deprecated（現状維持）への判断**: 生成物の肥大・CI コスト・一括 rename の手間が、手動同期で足りている現状の規律に見合わないと判断した場合は、本 ADR を `Deprecated` にし現状の手動同期 + クロス参照コメントを継続する。
- **`response_model` 整備は Phase 0 に内包**: 完全移行の前提として、未設定エンドポイントの schema 化・付与を Phase 0 内で実施する（別タスク化しない）。これにより「生成物と手書きの混在」を避ける。

## 関連リンク

- 領域横断レビュー: `report/XR_report_20260529_1006.md`（Medium: DTO 二重定義のドリフト検知不在）
- [frontend/src/api/client.ts](../../frontend/src/api/client.ts) — fetch ラッパー（401/CSRF、変更対象外）
- [frontend/src/api/paths.ts](../../frontend/src/api/paths.ts) — API パス SSoT（codegen 対象外）
- [frontend/src/api/shared.ts](../../frontend/src/api/shared.ts) — Phase 1 パイロット対象
- [backend/app/core/errors.py](../../backend/app/core/errors.py) — エラーコードの型縛り（DTO 検知機構の手本）
- openapi-typescript 公式ドキュメント: https://openapi-ts.dev/
