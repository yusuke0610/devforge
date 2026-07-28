# ADR-0025: 経歴書ドラフトのフォーム流し込み（payload の JSON 公開）

## ステータス

Accepted

## 関連 ADR

- 継承: [ADR-0010](0010-devforge-agent.md)（DB 非更新・LLM は確認して適用する対話機能）、[ADR-0018](0018-github-resume-draft-generation.md) / [ADR-0020](0020-async-resume-draft-generation.md)（経歴書ドラフト生成・非同期化・最小永続化。**生成設計は変えない**）
- 手本: [ADR-0024](0024-pdf-resume-import.md)（Resume 互換 payload をフォーム注入する流儀）。本 ADR は同じ注入機構（#524）をドラフトにも適用する

## コンテキスト

ADR-0018 のドラフト生成は、生成物を **PDF でしか返さない**。ユーザーは PDF を見て**手でフォームに転記**する運用で、ADR-0018 自身が「フォーム流し込みは将来フェーズ」と明記していた（体験として途中で梯子を外している）。

一方 ADR-0020 で、生成された payload（Resume 互換の dict）は `resume_draft_cache.result` に永続化され、`GET /resume-draft/pdf` がそこから PDF を再レンダリングしている。**payload そのものは既にサーバーに存在する**。ADR-0024 で「Resume 互換 payload → フォーム state 注入」の機構（#524）も実装済み。あとは payload を web に渡してフォームへ流し込むだけで「手で転記」が解消できる。

## 決定内容

**ドラフト payload を JSON で返す取得エンドポイントを追加し、ドラフト結果画面の「フォームに反映」から #524 の注入機構でキャリアフォームへ流し込む。** ADR-0018/0020 の生成設計・非同期構造・DB 非更新原則は変えない（出力の返し方だけ拡張する）。

### backend: payload 取得は別エンドポイント

- **`GET /api/agent/resume-draft/result`** を追加し、`resume_draft_cache.result`（生成済みの Resume 互換 payload）を JSON で返す。
- 既存 `GET /resume-draft/pdf`（PDF 再レンダリング）は**そのまま残す**。PDF プレビュー/DL と payload 取得は用途が異なるため、レスポンス形式パラメータで 1 エンドポイントに混ぜず**別エンドポイントに分ける**（Content-Type の分岐や条件付きレスポンス型を避ける）。
- 生成未完了・結果なしは既存 `/pdf` と同じ 409（`draft_not_ready`）契約に揃える。
- payload は保存契約（`schemas/resume.py` の strict 検証）ではなく**フォーム注入用の緩い schema**で返す（email 等は生成に含まれず、フォームでユーザーが補完する）。ADR-0024 の `ResumeImportResponse` と同じ思想。

### web: 「フォームに反映」→ router state → 注入

- ドラフト結果画面（GitHubLinkDashboard）に「フォームに反映」ボタンを追加。押下で payload を取得し、**`navigate("/career", { state })`** でキャリア画面へ渡す（既存の `location.state` 連携パターンを踏襲。ドラフトを永続化しない）。
- CareerResumeForm は受け取った payload を **#524 の注入機構**でフォーム state へ適用する。入力途中データがある場合は ADR-0024 と同じ**上書き確認**を挟む。反映後はユーザーが確認して既存の保存 API を呼ぶ（**DB 非更新** / ADR-0010）。

### #524 注入機構の汎用化

ドラフト payload は深い Resume 構造（experiences → clients → projects）で、PDF インポート（ADR-0024）のフラット payload より広い。既存の `mapCareerResumeToForm`（`ResumeResponse → CareerFormState` の全構造マッピング）を注入に再利用し、#524 を「Resume 互換 payload → CareerFormState」の共有経路として満たす。空判定 `hasCareerFormContent`（ADR-0024）も共用する。

### マージ規則（#524 共通・欠落/空は既存値保持）

**注入は全フィールドに一様に「payload の値が非空なら上書きし、空・未提供なら現フォーム値を保持する」ルールを適用する**（ADR-0024 の PDF インポートと同一。`applyResumeImportToForm` と挙動を揃える）。**特定フィールドを無条件に上書きする例外は設けない**（生成が想定外に空を返してもユーザーの入力を消さないため）。

- **スカラー**（`full_name` / `email` / `github_url` / `career_summary` / `self_pr`）: payload の値が非空なら上書き、空・未提供なら現フォーム値を保持する。
- **配列**（`experiences` / `qualifications`）: payload に中身があれば置換、無ければ現フォームを維持する（空フォームの blank 要素と「中身の有無」で区別する）。
- 実際のドラフト payload は `full_name`（username）・`career_summary`・`self_pr`・`experiences`・`github_url` を**常に生成・提供する**ためこれらは上書きされ、`email` と資格は**提供しない（空）**ため現フォーム値が残る。ただし上書き/保持は上記の一様ルール（値の非空判定）で決まり、フィールド名で固定分岐はしない。
- この規則により PDF インポート（#524）とドラフト（#525）の注入セマンティクスが一致し、「反映でユーザーの既存データを不用意に消さない」不変条件を共通化する。実装は `applyResumeImportToForm` と対になる形で `utils/resumeImport`（`applyResumeDraftToForm`）に集約する。

## 代替案

- **`/resume-draft/pdf` にフォーマットパラメータを足す**: 1 エンドポイントで PDF/JSON を出し分けると Content-Type とレスポンス型が条件分岐し、OpenAPI 生成物も複雑化する。用途が違うため別エンドポイントに分けて却下。
- **payload を redux/localStorage に stash してクロスページ**: ドラフトは確定物ではなく一時データ。永続化は不要で、router state（揮発）で十分。redux 常設スライスは過剰として却下。
- **ドラフトを直接 `resumes` に保存**: ADR-0010 の DB 非更新原則に反する。ユーザー確認を挟まず確定させない。却下。

## トレードオフ・既知のリスク

- payload を PDF とは別に再取得する（GET が 1 回増える）。ドラフトはキャッシュ済みで安価なため許容。
- router state はページリロードで失われる（反映前にリロードするとやり直し）。ドラフトはサーバーに残るため再取得・再反映でき、実害は小さい。
- ドラフト payload は GitHub 由来の推定を含む（ADR-0018 のトレードオフ）。DB 非更新でフォーム上でユーザーが確認・修正してから保存する設計により、誤りを確定前に直せる。

## 将来の移行条件

- ドラフト生成を同期化・設計変更する場合は ADR-0018/0020 を更新し、本 payload エンドポイントの契約を再評価する。
- 注入対象のフォームが増える場合は #524 の共有注入経路（`mapCareerResumeToForm` / `applyResumeImportToForm`）の一般化を再検討する。

## 設計原則との関係

- **P4（責務を層で分離する）**: 生成（backend・ルールベース+LLM）と反映（web・注入）を分け、PDF 取得と payload 取得もエンドポイントで分離する。
- **P5（LLM は対話型に限定）**: ドラフトは自動確定せず、フォームで確認して保存する（DB 非更新）。
- **P6（可逆性）**: 生成設計を変えず出力の返し方だけ足す小さな拡張。撤退は容易。

## 関連リンク

- [#517 機能整理・体験改善ロードマップ](https://github.com/yusuke0610/devforge/issues/517)（親 issue）
- #524（フォーム注入機構）／#525（本 ADR の実装）
- [ADR-0018](0018-github-resume-draft-generation.md) / [ADR-0020](0020-async-resume-draft-generation.md)（ドラフト生成）／[ADR-0024](0024-pdf-resume-import.md)（注入の手本）
