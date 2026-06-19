---
paths:
  - web/**
---

# TypeScript/React コーディング規約

- ESLint / Prettier の設定に従うこと
- リントは `make lint-web`、テストは `make test-web` を使う（Nix devshell 経由で解決される）
- 個別スクリプトを叩きたい場合は `nix develop --command bash -c "cd web && npm run <script>"` を使う。生シェルでの `cd web && npm ...` は AI エージェントでは禁止
- 重複検知 / DRY ポリシーは `.claude/rules/common/duplication.md` を参照（抽出先は `src/hooks/` `src/utils/` `src/components/ui/`）

## E2E テスト（Playwright）

E2E テストは `web/e2e/` に配置する。

### 実行タイミング
新しいページ・ルート・認証フロー・ナビゲーション・レイアウトコンポーネントを追加・変更した場合は必ず実行すること（Makefile に E2E ターゲットは無いため nix wrap で叩く）:
```bash
nix develop --command bash -c "cd web && npm run test:e2e"
```

### ルートモックの注意点（重要）

Playwright のルートハンドラーは **LIFO（後登録優先）**。登録順序を必ず守ること:

1. **最初**にキャッチオール（低優先）を登録する
2. **後から**具体的なモック（高優先）を登録する

```typescript
// 正しい登録順序
await page.route("http://localhost:8000/**", catchAllHandler);  // ① キャッチオール（最初）
await page.route("**/auth/me", specificMock);                   // ② 具体的モック（後）
```

キャッチオールパターンは **`http://localhost:8000/**`** を使うこと。`**/api/**` は Vite の開発サーバー（`localhost:5173`）上のソースファイルにもマッチし、モジュールロードが壊れる。

### LoadingOverlay への対処

`LoadingOverlay` は `position: fixed; inset: 0; z-index: 100` でビューポート全体（サイドバーを含む）を覆う。E2E テストで要素がクリックできない場合はオーバーレイが残っている可能性がある。`waitForAuthenticatedLayout()` を必ず呼び出すこと:

```typescript
import { waitForAuthenticatedLayout } from "./helpers/auth";

await page.goto("/basic_info");
await waitForAuthenticatedLayout(page);  // LoadingOverlay が消えるまで待機
```
