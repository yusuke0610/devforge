---
name: WEB_refacter
description: Use when reviewing or planning refactors for the DevForge React web, especially for maintainability, redundant or missing unit tests, oversized components or hooks, responsibility separation, and directory structure changes. Trigger on requests such as “web のリファクタリングを見て”, “保守性を確認”, “不要な単体テスト”, “単体テストは十分か”, “責務分離”, or “構成見直し”.
---

# Frontend Refactor Review

## 先に読む

- `.claude/CLAUDE.md`
- `.claude/rules/web/architecture.md`
- `.claude/rules/web/typescript.md`
- `.claude/rules/common/duplication.md`（DRY / 重複検知ポリシー）
- `report/dupe/jscpd-report.json` が存在すれば最新を読み込み、web に該当する clone を抽出して Duplication Findings の素材にする

必要に応じて backend 側 API 契約も確認すること。

## 対象

- `web/src/**`
- `web/tests/**`
- 必要に応じて `web/package.json`, `web/vite.config.ts`, `web/eslint.config.js`

## 成果物の出力先（必須）

レビュー本文はターミナルに垂れ流さず、必ずファイルへ保存する。スクロールで流れて読み返せなくなるのを防ぐためのルール。

- 保存先: `report/WEB_report_<YYYYMMDD_HHMM>.md`
  - 例: `report/WEB_report_20260516_1042.md`
  - `report/` が無ければ作成する (`mkdir -p report`)
  - タイムスタンプはレビュー開始時刻のローカルタイム (`date +%Y%m%d_%H%M`)
- ファイル中身は本ドキュメント末尾の「推奨出力フォーマット」に従う
- 既存の `WEB_report_*.md` は削除しない（履歴として残す）

### ターミナルへの出力ルール

- レポート本文を assistant メッセージへ貼らない（ファイルにだけ書く）
- ターミナルには以下だけを返す:
  1. 保存先パス（`report/WEB_report_YYYYMMDD_HHMM.md`）
  2. `Verdict` セクションの 3-5 行サマリのみ
  3. 次に取るべきアクション（あれば 1-2 行）
- Findings / Test Review / Structure Review / Refactor Plan などの詳細セクションはファイル参照に留める

## 目的

この skill の目的は、React/TypeScript の保守性を「見た目」ではなく、責務分離、状態管理、テスト価値、構成の探索容易性で評価することです。

以下を明確に区別してください。

- 表示ロジックの複雑さ
- データ取得や保存フローの複雑さ
- 再利用可能な hook へ切り出すべき責務
- 低価値テストと不足テスト
- ページ、components、hooks、api の境界不備

## 調査の進め方

### 1. インベントリ

- `rg --files web/src web/tests`
- 大きいファイルを洗う: `rg --files web/src web/tests | xargs wc -l | sort -nr | head -n 30`
- まず以下の層で把握する
  - pages: ルート入口。薄いラッパーであるべき
  - components: 表示と局所状態
  - hooks: 再利用可能な非表示ロジック
  - api: fetch と HTTP 変換
  - payload builder / mapper: 純粋関数

### 2. 保守性レビュー

以下に当てはまれば責務分離候補です。

- 1 component が data fetch、mutation、derived state、modal 制御、描画を全部持つ
- 1 hook が API 通信、フォーム状態、画面文言、UI 制御を全部持つ
- page が薄い wrapper ではなく実質的な feature component になっている
- `api/` にエラーマッピングや認証再試行以外の画面知識が入っている
- `components/` 間で props drilling が深く、state ownership が曖昧

サイズの目安は補助指標です。

- component が 250 行超で責務が複数ある
- hook が 180 行超で複数の state machine を持つ
- file 内の `useState` / `useEffect` が多く、表示以外の判断が散在する
- 同一画面向けの helper が component 本体に埋まり、再利用不能になっている

### 3. 単体テストレビュー

不要と判定する条件:

- static markup や単純な props passthrough しか見ていない
- 実装詳細の state 更新順や内部関数呼び出しだけに依存している
- snapshot が多いのに仕様保護よりノイズが大きい
- TypeScript の型が守る内容を冗長に runtime test している
- 同じ payload 変換や同じ分岐を複数テストが重複している

不足と判定する観点:

- form の load/create/update 失敗時
- API エラー文言、401 refresh、再認証導線
- route guard や認証状態に応じた画面分岐
- payload builder / mapper の境界値
- modal、confirm、preview、download の状態遷移
- AI 分析や同期の loading / success / error 分岐
- 複数 hook や API 呼び出しが絡む画面の統合的な振る舞い

不要テストを挙げるときは、必ず「削っても残る保護」を書くこと。  
不足テストを挙げるときは、必ず「何の仕様を守るためのテストか」を書くこと。

### 4. 重複検知レビュー（Duplication Findings）

`make dupe-check` で `report/dupe/jscpd-report.json` を生成し、`web/src` 配下の clone を抽出する。
生成されていない場合は `make dupe-check` を sandbox 無効で 1 回回してから本セクションに進む。

抽出した clone を以下の 3 分類でラベリングする（`.claude/rules/common/duplication.md` の基準に従う）。

- **本質的重複**（抽出すべき）: 同じデータ取得 + フォーム状態管理のロジック、同じ payload 変換、同じエラーマッピング、同じ API 呼び出しパターン、複数 component に散らばった同一 derived state
- **偶発的重複**（抽出しない）: import 文の塊、Redux slice の boilerplate、同形の TypeScript interface 定義（変更理由が違う）、CSS Module の class 列、test の arrange-act-assert の流れ
- **意味的重複**（jscpd では拾えない）: 別 hook で「同じデータ取得 + loading/error 管理 + キャッシュ」を別実装している、複数 component で「同じ条件分岐 + 描画」を別実装している。grep + 目視で別途探す。`useDocumentForm` / `useTaskPolling` / `useAsyncAnalysisPage` のような既存共通フックで吸収できないか確認する

本質的重複は「3 回目で抽出（Rule of Three）」を守る。

抽出先は `.claude/rules/common/duplication.md` の「Frontend」ヒエラルキーに従う:

1. 状態管理を含むロジック → `src/hooks/` の新規フック
2. 純粋関数・文字列変換・日付処理 → `src/utils/`
3. API クライアントの共通パターン → `src/api/client.ts` のラッパー
4. フォーム入出力変換 → `src/formMappers.ts` / `src/payloadBuilders.ts`
5. 共通 UI コンポーネント → `src/components/ui/`
6. 型定義 → `src/types.ts` / `src/formTypes.ts`

### 5. ディレクトリ構成レビュー

以下を確認します。

- `pages/` が本当に薄いか
- `components/` が feature 単位でまとまっているか
- `hooks/` が generic hook と feature hook で混ざっていないか
- `api/`, `types`, `payloadBuilders`, `formMappers` の責務境界が適切か
- CSS Module が component 境界と一緒に保守しやすく配置されているか

構成変更を提案するときは、以下をセットで出してください。

- どの探索コストが高いか
- どの責務をどこへ移すか
- 画面単位か共通部品か
- 過剰抽象化にならない理由

## レビューの厳しさ

- 「長い component」は即分割ではない。状態と責務の分離可能性で判断する
- 「テストが少ない」は弱い指摘。ユーザー影響の大きい分岐が無防備かで判断する
- 「hooks に出せる」は弱い。再利用性か可読性が本当に上がるかまで示す

## 推奨出力フォーマット

下記テンプレートを `report/WEB_report_<YYYYMMDD_HHMM>.md` に書き込む。ターミナルには貼らない。

````markdown
# Frontend Refactor Review

## Verdict
- 保守性の総評を 3-5 行で要約

## Findings
### High
- [path/to/file.tsx:line] 問題点。なぜ保守性を落とすか。どこへ分けるか。

### Medium
- ...

### Low
- ...

## Test Review
### Remove or Merge
- [path] なぜ低価値か。削除しても何が守られるか。

### Add
- [path or feature] どのユーザー挙動を守るテストか。

## Duplication Findings
### High（本質的重複・抽出強く推奨）
- [path1:line] ↔ [path2:line] (jscpd: N tokens) 何が重複しているか。本質的な理由。抽出先候補（`hooks/useXxx.ts` など）

### Medium（意味的重複・要検討）
- [path1] と [path2] の hook が同じデータ取得 + loading/error 管理パターン。既存の `useDocumentForm` で吸収できないか / 新規フックに統合するか。

### Allowed Duplication（記録のみ・抽出しない）
- [path:line] Redux slice / interface 定義などの偶発的重複。jscpd で検出されたが規約上抽出しない理由。

## Structure Review
### Oversized Components or Hooks
- [path] 何の責務が混ざっているか。どう切るか。

### Directory Changes
- 提案する target 構成

```text
web/src/
  pages/
  features/
  components/
  hooks/
  api/
  ...
```

## Refactor Plan
1. まずどの画面・hook を分解するか
2. どのテストを整理・追加するか
3. 最後にどの確認を回すか

## Validation
- 実行したコマンド
- 未実行ならその理由
````

## 最低限の検証コマンド

- `make lint-web`
- `make test-web`
- `make build-web`
- `make dupe-check`（重複検知。`report/dupe/jscpd-report.json` を生成。sandbox は無効化して実行）

個別スクリプトを叩きたい場合は `nix develop --command bash -c "cd web && npm run <script>"` を使う。生シェルでの `cd web && npm ...` は AI エージェントでは禁止。

コード変更を含む場合は、少なくとも影響範囲の画面とテストを確認し、最後に build まで通してください。
