# ADR-0009: フロントエンドの一時通知をトースト方式に統一する

## ステータス

Accepted

## コンテキスト

職務経歴書（Resume）・ブログ連携・ログイン・GitHub 連携の各画面では、操作の成功/失敗メッセージを
`{error && <p>...}` / `{success && <p>...}` のようにフォーム内へインライン表示していた。

この方式には次の課題があった。

- メッセージがレイアウト内に流し込まれるため、スクロール位置によっては見えない・気付かれない。
- 表示位置・スタイルが画面ごとにバラバラ（`shared.error` / `BlogPage.module.css` / `LoginForm.module.css` 等）。
- 成功と失敗で消える/残るの挙動を制御できず、成功メッセージが残り続ける。
- GitHub 連携だけは `ErrorToast` コンポーネントでカード表示していたが、他画面と統一されていなかった。

操作フィードバックを画面横断で一貫した「トースト（画面隅に一時表示する通知）」に統一したい。

## 決定内容

- 外部ライブラリを導入せず、**自前の Toast 基盤**を `frontend/src/components/ui/toast/` に実装する。
  - `ToastProvider`（Context + スタック state）を `main.tsx` の最上位（全ルートを覆う位置）に 1 つ設置。
  - `useToast()` が `showSuccess(message)` / `showError(string | AppErrorState)` / `dismiss(id)` を提供。
  - `ToastViewport` は `createPortal` で body 直下に固定表示し、各ページのスタッキングコンテキスト
    （`LoadingOverlay` 等）に埋もれないようにする。
- **挙動**: 成功トーストは一定時間（`SUCCESS_TOAST_DURATION_MS`）で自動消去、エラートーストは
  自動消去せず × ボタンで手動クローズする。
- **既存フックは変更しない**。`useDocumentForm` / `usePdfActions` / `useBlogAccountManager` /
  `useAsyncTaskPage` は従来通り error/success を state として保持し、表示層の薄いブリッジ
  （`useMessageToast` / `useAppErrorToast`）でトーストへ橋渡しする。これによりフックを Provider に
  依存させず、既存のユニットテストをそのまま維持する。
- 旧 `ErrorToast` コンポーネントは `ToastItem` のエラー表示（`AppErrorState` の回復アクション・
  エラー ID 表示を含む）へ統合し、削除する。
- **適用範囲**: 「ページ全体の成功/失敗」のみをトースト化する。項目バリデーション（保存前の
  入力チェック）とファイル取り込み補助パネルのエラーは、フォーカス・赤枠・パネル状態と密結合した
  文脈情報のため従来通りインライン表示を維持する。

## 代替案

- **トーストライブラリ（sonner / react-hot-toast）導入**: Provider・自動消去・スタックが即利用できるが、
  依存とバンドルサイズが増え、既存の `ErrorToast` / `ERROR_CONFIG`（回復アクション）資産との橋渡しが
  別途必要になる。一時通知のためだけに依存を増やす利得が小さいと判断し却下。
- **フック内部から直接トーストを発火**（`useToast` をフックが呼ぶ）: 表示と state の二重持ちを解消できるが、
  対象フックすべてが ToastProvider 必須となり、既存ユニットテスト（error/success を assert）を
  全面的に書き換える必要がある。契約変更の影響が大きいため、表示層ブリッジ方式を採用した。

## トレードオフ・既知のリスク

- 表示層ブリッジ（`useMessageToast`）は state の文字列変化を `useEffect` で監視する方式のため、
  StrictMode の effect 二重実行や同一文言の連続表示を `ref` でガードしている。この前提が崩れると
  二重表示や表示漏れの恐れがあるため、ガードはテストで固定する。
- フックは「表示されない error/success 文字列」を保持し続ける（presentation はブリッジが読む）。
  state の責務が二段になる点は許容する。
- トーストは画面隅に出るため、長文メッセージや同時多発の通知ではスタックが縦に伸びる。現状は
  自動消去（成功）と手動クローズ（エラー）で許容範囲とする。

## 将来の移行条件

- 通知の同時多発・グルーピング・アクション付き通知（Undo 等）の要件が増えた場合は、専用ライブラリ
  （sonner 等）への移行を再検討する。
- 通知の永続化（既読管理）が必要になった場合は `NotificationBell` 系の仕組みと統合を検討する。

## 関連リンク

- 実装: `frontend/src/components/ui/toast/`
- メッセージ SSoT: `frontend/src/constants/messages.ts`、ルール `.claude/rules/frontend/messages.md`
- エラーコード連携: `frontend/src/constants/errorMessages.ts`（`ERROR_CONFIG`）
