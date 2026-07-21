---
paths:
  - web/**
---

# Frontend アーキテクチャ (React 18 + Vite + TypeScript)

```
web/src/
├── main.tsx              # BrowserRouter + Redux Provider ラップ
├── App.tsx               # 認証ステート管理 + <AppRoutes />
├── App.module.css
├── styles.css / styles/  # グローバルスタイル
├── router/
│   ├── routes.tsx        # 全ルート定義（パス↔ページ対応表）
│   ├── guards.tsx        # PrivateRoute / PublicRoute（Outlet パターン）
│   └── index.ts
├── pages/                # ルートのエントリーポイント（薄いラッパー）
│   ├── LoginPage.tsx / GitHubCallbackPage.tsx
│   ├── CareerPage.tsx
│   ├── GitHubLinkPage.tsx
│   └── NotFoundPage.tsx
├── components/
│   ├── AuthenticatedLayout.tsx  # サイドバー + <Outlet />（フッターに NotificationBell を配置）
│   ├── LoadingOverlay.tsx       # 共通ローディング UI（position:fixed; z-index:100 でビューポート全体を覆う）
│   ├── NotificationBell.tsx     # 通知ベル（未読バッジ・ドロップダウンパネル）
│   ├── ConfirmDialog.tsx        # 確認モーダル
│   ├── ErrorBoundary.tsx        # 例外境界
│   ├── UserMenu.tsx
│   ├── forms/                   # BasicInfoForm, CareerResumeForm, ResumeForm 等
│   ├── github-link/             # GitHubLinkDashboard, LanguageBar 等
│   ├── auth/                    # LoginForm, RegisterForm
│   ├── icons/                   # アイコンコンポーネント（Bell, Eye, GitHubMark 等）
│   └── ui/                      # 汎用 UI（toast/（ToastProvider/useToast）, InlineSpinner, Skeleton, AsyncTaskLoading）
├── hooks/
│   ├── useDocumentForm.ts       # フォーム CRUD の共通フック（loading / saving / error 管理）
│   ├── useMasterData.ts         # マスタデータのモジュールレベルキャッシュ
│   ├── useNotifications.ts      # 通知ベル用フック（30秒ポーリング・パネル開閉・既読処理）
│   ├── usePdfActions.ts         # PDF ダウンロード/プレビュー
│   ├── useTaskPolling.ts        # 非同期タスクの進捗ポーリング（指数バックオフ対応）
│   ├── useAsyncTaskPage.ts      # 「キャッシュ→入力→ポーリング→結果」の phase 管理（useTaskPolling を内包）
│   ├── useAuthSession.ts        # 認証セッション状態
│   ├── useTheme.ts
│   └── career/                  # useCareerDirty / useCareerExperienceMutators / useProjectModalForm / useProjectModalState / usePhotoUpload / useImportPanelLayout / useResumeImportAssist
├── api/
│   ├── client.ts                # fetch ラッパー（Cookie 認証、401 ハンドリング）
│   └── *.ts                     # ドメイン別 API モジュール（auth, resumes, master-data, notifications, download, ai-resume, githubLink）
├── store/                       # Redux Toolkit + redux-persist
│   ├── index.ts                 # store 構成
│   ├── persistConfig.ts
│   └── formCacheSlice.ts        # フォームキャッシュ
├── utils/
│   ├── appError.ts
│   ├── errorId.ts
│   ├── deepEqual.ts             # フォーム dirty 判定用の再帰等価比較（useCareerDirty / useProjectFormDirty で共用）
│   ├── pdfjs.ts
│   └── taskStatus.ts            # 非同期タスクのステータス契約（in-progress 判定）
├── constants/ + constants.ts    # 定数定義
├── types.ts                     # 共通型
├── formTypes.ts / formMappers.ts / payloadBuilders.ts  # フォーム入出力変換
├── test/ + test-setup.ts        # vitest セットアップ
└── styles/
```

**ルーティング**: react-router-dom v7。ガードは Outlet パターン（レイアウトルート）で実装。`/login` 系は PublicRoute、他は PrivateRoute でガード。

**フォームパターン**: `useDocumentForm` フックが load/create/update/loading/saving を一元管理。各フォームはこのフックを使い、`LoadingOverlay` でデータ取得中の操作をブロックする。

**状態管理**: Redux Toolkit + redux-persist。`store/formCacheSlice` でフォームの一時保持を行う。サーバ状態は各 API モジュール経由で取得し、コンポーネントローカルもしくはフックでキャッシュする方針。

**非同期タスクの進捗**: `useTaskPolling` / `useAsyncTaskPage` がバックエンドのタスクステータス（`pending` / `processing` / `retrying` / `completed` / `dead_letter`）をポーリングし、`AsyncTaskLoading`（`components/ui/`）で可視化する。ステータス文字列の正本（`TaskStatus` 型・進行中判定 `isInProgressStatus`）は `utils/taskStatus.ts` に集約してあるので、状態を増減する際はまずそこを更新する。
