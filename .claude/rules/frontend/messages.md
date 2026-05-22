# メッセージ管理ルール (frontend)

ts/tsx でユーザーに表示される文字列を**リテラルで直接書かない**。
必ず Single Source of Truth から取得すること。

## SSoT の責務分離

| メッセージの種類 | 正本 | 取得経路 |
|---|---|---|
| **API 経由のエラー** (backend → frontend) | `backend/app/messages.json` | `AppErrorResponse.message` を `api/client.ts:buildApiError` 経由でそのまま表示 |
| **API レスポンスに message が無い時の補完** | `frontend/src/constants/errorMessages.ts` (`ERROR_CONFIG`) | `ErrorCode` を引いて補完（既存実装） |
| **frontend 完結のメッセージ** | `frontend/src/constants/messages.ts` | import して定数参照 |

`messages.json` から frontend 用 TS 定数を build-time 生成する仕組みは**入っていない**。
`ERROR_CONFIG` は `backend/app/core/errors.py:ErrorCode` enum と**手動同期**する設計（型エラーで漏れを検出）。

## frontend 完結のメッセージとは

backend を経由しない以下のような文言:

- **フォームの事前バリデーション**: `payloadBuilders.ts` の「氏名を入力してください」など
- **catch ブロックの fallback メッセージ**: `e instanceof Error ? e.message : "..."` の `...` 部分
- **ネットワーク層の fallback**: `api/client.ts` で 5xx / fetch 例外時に出す文言
- **JSX 直書きの UI 文言**: `ErrorBoundary` のタイトルなど
- **開発者向け内部エラー**: `import_id が未設定です` のような状態管理エラー

これらは `frontend/src/constants/messages.ts` に集約する。カテゴリ別の定数:

- `VALIDATION_MESSAGES` — 入力バリデーション
- `NETWORK_MESSAGES` — ネットワーク / API クライアント層
- `FALLBACK_MESSAGES` — catch fallback / toAppError fallback
- `UI_MESSAGES` — JSX 直書き文言
- `INTERNAL_MESSAGES` — 開発者向け内部エラー
- `downloadFailureMessage(filename)` — 動的パラメータが必要なケースは関数

## 新規メッセージ追加の手順

### API 経由のエラー（backend が発火）

1. `backend/app/messages.json` の `error.<category>` にキー追加
2. backend で `get_error("category.key", **kwargs)` または `raise_app_error(code=...)` で使う
3. frontend 側はとくに変更不要（`AppErrorResponse.message` が自動的に画面に出る）

### frontend 完結のメッセージ

1. `frontend/src/constants/messages.ts` の適切なカテゴリに定数追加
2. 使用箇所で import して参照
3. リテラルを書かない

## やってはいけないこと（再発防止対象）

以下は **ESLint または `make lint-frontend-messages` で自動検知され CI で fail する**:

```ts
// ✗ ESLint で error
throw new Error("入力してください");
throw new Error(`${field} を入力してください`);

// ✗ make lint-frontend-messages で error
setError("失敗しました");
setErrorMessage("不正な値です");
setAccountError("取得に失敗");
toast.error("エラー");
alert("確認してください");
```

正しい書き方:

```ts
import { VALIDATION_MESSAGES, FALLBACK_MESSAGES } from "../constants/messages";

throw new Error(VALIDATION_MESSAGES.FULL_NAME_REQUIRED);
setError(FALLBACK_MESSAGES.SAVE);
```

## 例外: 検知から外れているもの

以下はリテラルを書いても検知されない（許容するが推奨しない）:

- 英語の開発者向けメッセージ (`throw new Error("invariant violated")`)
- `console.error` / `console.warn`（UI に表示されないログ用途）
- テストファイル (`*.test.*`, `test/**`)
- `constants/messages.ts` 自身

## 検証

```bash
make lint-frontend                # ESLint（no-restricted-syntax 含む）
make lint-frontend-messages       # grep ベースの追加チェック
```

両方を pass させることが「テスト OK」条件の前提（`.claude/rules/frontend/test.md` 参照）。

## 参考

- `frontend/src/constants/messages.ts` — frontend 完結メッセージの SSoT
- `frontend/src/constants/errorCodes.ts` / `errorMessages.ts` — backend ErrorCode 連携
- `backend/app/messages.json` — backend のメッセージ正本
- `backend/app/core/errors.py` — ErrorCode enum
- `scripts/lint-frontend-messages.sh` — grep ベースの検知スクリプト
- `frontend/eslint.config.js` — no-restricted-syntax ルール定義
