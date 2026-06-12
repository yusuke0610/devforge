# ADR-0006: TanStack Query 導入検討

## ステータス

Deprecated

> **見送り**: Phase 1 パイロットを実施しないまま ADR-0010（DevForge Agent）等の優先作業が続き、
> 導入メリットとコスト（バンドルサイズ増・テスト書き換え・学習コスト）が見合わないと判断。
> 現状の手書き fetch + useState 構成を継続する。
> 再導入が必要になった場合は本 ADR を参照して改めて検討すること。

---

> ~~本 ADR は「サーバ状態管理に TanStack Query を導入するか」の判断材料であり、採用確定ではない。
> Phase 1 パイロット（後述）の結果を見て `Accepted` への昇格、または `Deprecated`（現状維持）を判断する。~~

## コンテキスト

DevForge のフロントエンド（React 18 + TypeScript + Vite）には、サーバ状態（API レスポンス）を管理する専用ライブラリが**入っていない**。データ取得は `frontend/src/api/client.ts` の `request<T>()` を起点に、各フックが手書きで取り回している。

現状の構成と痛み:

- **fetch ラッパーは完成度が高い**: `request<T>()` は Cookie 認証・CSRF トークン付与・401 リフレッシュ（重複排除付き、1回のみ再試行）を自前実装済み。ここは温存したい資産。
- **約35エンドポイント / 約10フック**が、それぞれ `useState` で `loading` / `error` / `success` を手書きしている（`useDocumentForm` / `useNotifications` / `useBlogAccountManager` 等）。同じボイラープレートが各所に散在。
- **ミューテーション後は手動で全件再取得**している。例: `hooks/blog/useBlogAccountManager.ts` の `loadData()` は、アカウント追加/更新/削除のたびに accounts と articles を**両方**再取得する（articles が変わっていなくても再取得）。
- **キャッシュは断片的**: `useMasterData` のモジュールレベル ref キャッシュ（有効期限/無効化なし）と、Redux `formCache`（フォーム下書き保持）のみ。サーバ状態の横断キャッシュ・重複排除・stale-while-revalidate・background refetch・`AbortController` による中断はいずれも無し。
- **ポーリングは手書き**: `useTaskPolling` は `setTimeout` + 指数バックオフ、`useNotifications` は `setInterval` の30秒固定。

「リクエスト管理を最適化したい」という要望に対し、サーバ状態管理ライブラリの導入是非を整理する必要が生じた。既存の状態管理判断は [ADR-0003](../0003-redux-toolkit-persist.md) で Redux Toolkit + redux-persist を採用済みのため、本 ADR ではその責務境界も併せて明確化する。

## 決定内容

サーバ状態管理に **TanStack Query（`@tanstack/react-query` v5）** を採用する案を提示する。導入する場合の方針は以下のとおり。

### 基本方針

- **`request<T>()` はそのまま `queryFn` として再利用する**。401 リフレッシュ・CSRF・Cookie 認証のロジックは一切変更しない。TanStack Query は `request<T>()` の薄いラッパーとして上に乗せるだけにする。
- TanStack Query の `retry` は**既存リフレッシュと二重化しないよう調整**する。具体的には 401（`AUTH_REQUIRED`）はリトライ対象から外す（リフレッシュは `request<T>()` 内で完結しているため）。
- `frontend/src/main.tsx` に `QueryClientProvider` を追加する（既存の `BrowserRouter` / Redux `Provider` と並列にラップ）。
- **永続化は行わない**: TanStack Query のキャッシュはメモリ上のみとし、`localStorage` への persist プラグインは導入しない（PII 方針との整合。後述）。

### 責務境界（Redux との分担）

| 状態の種類 | 管理場所（提案後） | 備考 |
|---|---|---|
| サーバ GET 結果・一覧・マスタデータ | **TanStack Query** | キャッシュ + `invalidateQueries` による無効化 |
| フォーム編集中の下書き・ページ跨ぎ保持 | Redux `formCache`（現状維持） | クライアント状態であり TanStack の領分外 |
| 認証状態・ユーザー情報 | `App.tsx` の `useState` + `sessionStorage`（現状維持） | [ADR-0003](../0003-redux-toolkit-persist.md) 踏襲 |
| 現在のページ・パラメータ | URL（React Router、現状維持） | — |

要点は **「サーバ状態 = TanStack Query / クライアント状態 = Redux」** の線引きを徹底すること。TanStack Query は Redux を**置換するものではなく補完**する。

### query key 命名規約

エンドポイント単位でドメイン配列キーを用いる（例: `["master-data", "qualifications"]` / `["notifications", "unread-count"]` / `["blog", "accounts"]`）。無効化はドメインプレフィックス単位で行えるようにする。

### テスト方針

各フックテストで `QueryClientProvider` ラップが必要になるため、`renderWithQueryClient` 相当のテストヘルパーを `frontend/src/test/` に用意する（`.claude/rules/frontend/test.md` 準拠）。テストごとに新しい `QueryClient`（`retry: false`）を生成し、テスト間でキャッシュが漏れないようにする。

### 段階移行プラン

採用する場合は以下の順で進める。Phase 1 をパイロットとし、効果を見てから先へ進む。

| Phase | 対象 | 内容 | リスク |
|---|---|---|---|
| 0 | 基盤 | 依存追加 / `QueryClientProvider` 設置 / query key 規約 / テストヘルパー | 低 |
| 1 | 読み取り（パイロット） | `useMasterData`（module ref → `useQuery` + `staleTime: Infinity`）、`useNotifications`（30秒 `setInterval` → `refetchInterval`） | 低 |
| 2 | ミューテーション + 無効化 | `useBlogAccountManager`（`loadData()` 全件再取得 → `useQuery` + `useMutation` + `invalidateQueries`） | 中 |
| 3 | ポーリング（任意・要検証） | `useTaskPolling` / `useAsyncTaskPage` を `refetchInterval`（終端ステータスで `false` 返却）で表現できるか検証。指数バックオフ + 終端コールバックは独自実装のため、無理なら現状維持 | 中〜高 |

### 移行しないもの（重要）

- **`useDocumentForm`**: 編集中フォーム・dirty 判定（baseline 比較）・ページ跨ぎ保持は**サーバ状態ではなくクライアント状態**であり、TanStack Query の領分外。Redux のまま残す。`loadLatest()` のサーバ取得部分だけは将来 `useQuery` 化の余地があるが、今回スコープ外とする。
- **`request<T>()` の 401/CSRF ロジック**: 変更しない。

## 代替案

| 選択肢 | 評価 |
|---|---|
| 現状維持（手書き fetch + `useState`） | 既存資産（401/CSRF）はそのまま活きるが、キャッシュ・重複排除・SWR・無効化を都度手実装する負債が残り続ける |
| SWR | 軽量で導入は容易だが、ミューテーション/無効化フロー・devtools が TanStack Query ほど充実しておらず、Phase 2 以降の要件に弱い |
| RTK Query | 既存 Redux と統合できる利点はあるが、サーバ状態とフォーム下書きを同一 store に混在させる設計になり責務境界が曖昧化する。ボイラープレートも相対的に重く、`request<T>()` の流用も馴染みにくい |

## トレードオフ・既知のリスク

1. **バンドルサイズ増**: TanStack Query コアで +約12〜13KB(gz)。devtools は dev ビルド限定にすれば本番には乗らない。
2. **状態システムの二重化**: TanStack Query（サーバ状態）と Redux（クライアント状態）が併存する。境界を明文化しないと「サーバ最新値をどちらが持つか」が曖昧になる。特に `useDocumentForm` の `baseline`（サーバ最新スナップショット）と編集中 `form` は二重ソースになりやすい。当面は両方とも Redux 側に留め、移行するなら baseline 取得のみ TanStack 化する余地がある旨を残す。
3. **学習コスト**: query key 設計・`staleTime` / `gcTime`・無効化フローの理解が必要。
4. **テスト影響**: 各フックテストに `QueryClientProvider` ラッパーが必要。`useNotifications` 等、既存テストの assert 見直しが発生する（`.claude/rules/frontend/test.md`）。
5. **E2E 影響**: `useNotifications` / `AuthenticatedLayout`（通知ベル）周りは E2E トリガーに該当するため、移行時は `npm run test:e2e` 必須。
6. **PII 方針**: TanStack Query のキャッシュはメモリ上のみとし `localStorage` に persist しない。[ADR-0003](../0003-redux-toolkit-persist.md) の `formCache` blacklist（PII を localStorage に保存しない方針）と整合させる。persist プラグインは導入しない。

## 将来の移行条件

- **Accepted への昇格条件**: Phase 1 パイロットが `make ci` green / E2E green を満たし、かつボイラープレート削減・無効化フローの改善が体感できること。
- **Deprecated（現状維持）への判断**: 上記を満たせない、またはバンドルサイズ増・二重状態管理のコストが効果に見合わない場合は、本 ADR を `Deprecated` にし現状の手書き fetch を継続する。
- Phase 2 以降に進む場合、`useDocumentForm` の baseline 取得を TanStack Query 化するかを改めて検討する。

## 関連リンク

- [ADR-0003: Redux Toolkit + redux-persist の採用](../0003-redux-toolkit-persist.md)
- [frontend/src/api/client.ts](../../frontend/src/api/client.ts) — fetch ラッパー（401/CSRF）
- [frontend/src/hooks/useMasterData.ts](../../frontend/src/hooks/useMasterData.ts) — module ref キャッシュ（Phase 1 対象）
- [frontend/src/hooks/useNotifications.ts](../../frontend/src/hooks/useNotifications.ts) — 30秒ポーリング（Phase 1 対象）
- [frontend/src/hooks/blog/useBlogAccountManager.ts](../../frontend/src/hooks/blog/useBlogAccountManager.ts) — ミューテーション後の全件再取得（Phase 2 対象）
- [frontend/src/hooks/useDocumentForm.ts](../../frontend/src/hooks/useDocumentForm.ts) — フォーム下書き（移行対象外）
- TanStack Query 公式ドキュメント: https://tanstack.com/query/latest
