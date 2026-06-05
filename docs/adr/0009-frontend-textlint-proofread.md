# ADR-0009: 職務経歴書のフロントエンド完結型 文章校正（textlint + kuromoji）

## ステータス

Accepted

## コンテキスト

職務経歴書は転職で人の目に触れる重要文書だが、DevForge には誤字脱字・表記ゆれ・冗長表現を検出する仕組みが無かった。保存前にユーザーが自分で気づけるよう、保存確認ダイアログ（`CareerDiffModal`）内で文章を校正し、指摘を一覧表示する機能を追加する。

制約・前提:

- **個人情報を外部に送らない**: 職務経歴書は氏名・経歴を含む。外部 API / LLM に本文を送信しない方針（ADR-0008 のルールベース志向とも整合）。
- **コスト**: 追加のサーバー処理・課金を避けたい。
- **既存体験への影響最小化**: 保存フロー（`useDocumentForm.save`）の契約は変えない。

## 決定内容

**ルールベースの校正をフロントエンド完結（Web Worker）で実行する。**

- エンジン: `@textlint/kernel` + `textlint-rule-preset-ja-technical-writing`（全23ルール）+ `textlint-rule-prh`（IT 用語の表記ゆれ辞書を同梱）。
- 実行場所: 専用 Web Worker（`src/proofread/proofread.worker.ts`）。textlint / kuromoji 一式は動的 import で worker チャンクへ分割し、初期バンドル・初回描画から切り離す。
- 形態素解析辞書（kuromoji）: `frontend/public/kuromoji-dict/`（約18MB）に静的配信。worker から `globalThis.kuromojin.dicPath = "/kuromoji-dict"`（ルート相対）で参照。
- UI 統合: メインスレッドは `ProofreadIssue[]` という安定インターフェースのみ知る。`useProofread` フックが保存確認ダイアログ表示中だけ校正を起動し、結果を `CareerDiffModal` 右サイドバー下部に「校正の指摘」として青系・控えめに表示する。**保存はブロックしない**（警告のみ）。
- 辞書ロード失敗時は形態素解析依存ルール（二重助詞・冗長表現など10ルール）を除外し、prh + 非依存ルールで継続する（グレースフルデグラデーション）。

## 代替案

- **LLM / 外部校正 API**: 精度は高いが個人情報の外部送信・コスト・レイテンシで不採用（ADR-0008 の方針に反する）。
- **バックエンド（Python）で textlint 相当を実行**: Node ランタイム追加 or Python 形態素解析の導入が必要でインフラ複雑化。本文をサーバーに送る必要も無いためフロント完結を優先。
- **prh 単体 + 自前正規表現のみ（kuromoji 無し）**: リポジトリ肥大ゼロ・軽量だが、二重助詞・冗長表現などの文法系チェックが落ちる。フォールバック経路としては内包するが、第一選択は全プリセットとした。

## トレードオフ・既知のリスク

- **リポジトリ肥大**: kuromoji 辞書 約18MB を `public/` にコミットするため git 履歴が恒久的に増える（ユーザー承認済みのトレードオフ）。
- **初回ロード遅延**: 初回校正時に辞書（数MB）を fetch するため、最初の指摘表示まで数秒かかる。以降は worker 内でキャッシュ。
- **ブラウザ統合の脆さ**: textlint/kuromoji は Node 前提のため、worker で `window` / `process`（`cwd`/`nextTick` 等）の最小ポリフィル、node 組み込み（`path`/`os`/`assert`）のブラウザ実装エイリアス、辞書 `.gz` を `Content-Encoding: gzip` させない配信（dev: Vite プラグイン / prod: `public/_headers`）が必要。これらは `src/proofread/worker-env-polyfill.ts`・`vite.config.ts`・`public/_headers` に集約しコメントで明示した。
- **辞書 `.gz` の二重展開**: サーバーが `.gz` を gzip 転送エンコーディング扱いすると、ブラウザが自動展開して kuromoji の再 gunzip が失敗する。生バイト配信を強制している。

## 将来の移行条件

- リポジトリ肥大が問題化した場合: 辞書を CDN（jsDelivr 等）配信へ切り替える、または kuromoji 依存ルールを外して辞書同梱をやめる（フォールバック構成へ）。
- 校正精度を上げたい場合: prh 辞書の拡充、もしくは（個人情報の扱いを整理した上で）サーバーサイド校正の再検討。

## 関連リンク

- 実装: `frontend/src/proofread/`・`frontend/src/hooks/career/useProofread.ts`・`frontend/src/components/forms/CareerDiffModal.tsx`
- 関連 ADR: ADR-0008（ルールベース設計への移行）
- 参考: textlint / textlint-rule-preset-ja-technical-writing / kuromoji.js
