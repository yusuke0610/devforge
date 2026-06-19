---
paths:
  - web/**
---

# Frontend テスト方針

## いつテストを書く・回すか（トリガー）

### ユニット / コンポーネントテスト（vitest + node:test）

- **新規フック追加**: 必ず `*.test.ts` を作成（loading / success / error の 3 パス最低限）
- **既存フックの契約変更**: 戻り値・副作用が変わる場合、既存 `*.test.ts` の assert を見直す
- **payloadBuilders / formMappers の変更**: `payloadBuilders.test.ts` を更新（node:test 経由）
- **api/client.ts の変更**: `api/client.test.ts` を更新（401 リダイレクト、Cookie 認証の挙動）
- **コンポーネント追加**: ロジックを含むものはテストを追加。表示のみのものは省略可

### E2E テスト（Playwright）

以下のいずれかに該当する変更を行った場合、E2E を必ず実行:

- 新しいページまたはルートの追加
- 認証・ナビゲーション・レイアウトコンポーネントの変更
- 通知ベル / サイドバー / `AuthenticatedLayout` の変更
- バックエンド API の追加・変更で、web の UI フローに影響するもの

## 実行コマンド

```bash
make test-web                                              # unit + vitest
nix develop --command bash -c "cd web && npm run test:e2e" # E2E（Playwright）
```

特定の vitest スイートだけ回す場合:
```bash
nix develop --command bash -c "cd web && npx vitest run src/hooks/useDocumentForm.test.ts"
```

## OK 基準（達成条件）

以下をすべて満たして初めて「テスト OK」と判定する:

1. **全 unit / vitest pass**: `make test-web` が exit 0
2. **lint が pass**: `make lint-web` も同時に通ること
3. **build が通る**: `make build-web`（tsc + vite build）が通ること。TypeScript の型エラーが残っていないこと
4. **E2E トリガーに該当する場合は E2E pass**: 上記トリガーリストに該当する変更では `npm run test:e2e` を必ず実行し、全シナリオが green
5. **新規・変更コードに対応するテストが存在する**:
   - 新規フック → 主要分岐ごとに 1 ケース（最低 3 ケース）
   - 新規 API モジュール → 成功 / 4xx / 5xx の 3 パス
   - E2E は authenticated layout 経由でゴールデンパスを 1 本通す

## E2E の注意点（重要 — 過去にハマった）

- **ルートモックは LIFO 登録**: キャッチオールを先、具体的モックを後（`.claude/rules/web/typescript.md` 参照）
- **`LoadingOverlay` 対策**: `waitForAuthenticatedLayout(page)` を必ず呼び出す。`position: fixed; z-index: 100` が要素クリックを邪魔する
- **キャッチオールパターン**: `http://localhost:8000/**` を使う。`**/api/**` は Vite dev server のソースファイルにもマッチして壊れる

## アンチパターン

- `await new Promise(r => setTimeout(r, ms))` での同期待ち（フレーキー）
- `data-testid` 過剰依存（ユーザー視点のセレクタを優先: role / name / placeholder）
- E2E でテスト用バックエンドを起動せずモックだけで済ませる（API 統合バグを取り逃す）
- snapshot testing で大きな DOM 全体をスナップショットする（差分の意味が不明瞭になる）
