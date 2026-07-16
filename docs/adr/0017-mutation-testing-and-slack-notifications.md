# ADR-0017: ミューテーションテスト週次実行と Slack 通知チャンネル分割

## ステータス

Accepted

## コンテキスト

- backend のテストスイートが 500 件規模（51 ファイル・約 670 テスト）に成長し、行カバレッジ（86%）だけでは「実装をなぞっているだけのテスト」「assertion が弱いテスト」を検出できなくなった。テストの**検出力**そのものを測る仕組みが必要。
- GitHub 通知（メール / Web）は流量が多くノイズに埋もれるため、Slack へ移行し通知の種類ごとにチャンネルを分けたい。
- ミューテーションテストはフル実行に数十分〜時間単位かかるため、PR ごとの CI（ci.yml）に入れるとブロッキングチェックとして開発体験を大きく損なう。

## 決定内容

### ツール選定

| 領域 | ツール | 実行系 |
|---|---|---|
| backend | mutmut 3.x（`requirements.txt` で固定） | pytest を `mutants/` 内で in-process 実行 |
| web | Stryker（`@stryker-mutator/core` + `@stryker-mutator/vitest-runner`） | 既存 vitest（`vite.config.ts` 内蔵設定）をそのまま利用 |

- **backend は uv 管理ではない**（pyproject に `[project]` なし・lockfile は `requirements.txt`）ため、mutmut も既存慣例どおり `requirements.txt` にバージョン固定で追加する。
  - **更新（2026-07-16 / ADR-0021）**: backend は PEP 621 + `uv.lock` 管理へ移行済み。mutmut は `backend/pyproject.toml` の `[project.dependencies]` で `==` 固定し、実体は Nix devshell（uv2nix build）が提供する。
- Stryker の TS checker は使わない（tsconfig が project-references + noEmit 構成のため）。ランナーは vitest-runner（peer: `vitest >=2.0.0`、vitest 4 対応確認済み）。

### 対象スコープ（決定論的ビジネスロジックに限定）

I/O 層・宣言層（schemas / models / routers / LLM クライアント / 自動生成コード / 定数カタログ）はテストで殺せないミュータントがノイズになるため対象外とし、テストで検証すべき純ロジックに絞る。

- backend（`pyproject.toml` の `[tool.mutmut]` が正本）: blog スコアリング、billing（料金・クレジット計算）、skills 推論（aggregator / linguist / パーサ群）、repo_analyzer / contributions、shared（sort_utils / resume_format）、tasks/worker（状態遷移）
- web（`web/stryker.conf.json` が正本）: `src/utils/**`、`formMappers.ts`、`payloadBuilders.ts`、`src/hooks/**`、store の slice、`constants/agentModels.ts`

### 実行タイミングと fail ポリシー

- 週次（毎週月曜 3:00 JST = cron `0 18 * * 0`）+ `workflow_dispatch` の専用ワークフロー `.github/workflows/mutation.yml`。backend / web は並列ジョブ。
- **warn-only**（jscpd の Phase 1 と同じ方針）: 生存ミュータントがあってもワークフローは fail させず、Slack 通知とレポート artifact（14 日保持）で可視化する。閾値ゲート化は baseline 確定後に検討。

### score の定義（backend / web 共通基準）

```
killed   = killed + timeout          # 無限ループ化もテストによる検出とみなす（Stryker と同基準）
survived = survived + no_tests       # どのテストにも触れられない = 検出不能（Stryker の NoCoverage 相当）
score    = killed * 100 / (killed + survived + suspicious + segfault)
```

閾値は `mutation.yml` の env `MUTATION_SCORE_THRESHOLD`（初期値 80%）。未満なら Slack 通知を ⚠️ で強調する。

### pytest-cov との干渉回避

mutmut は `mutants/` に app / tests / pyproject.toml をコピーし pytest を in-process 実行する。pyproject の `addopts` に `--cov` があると全ミュータント実行に coverage 計測が載り干渉するため、**`--cov=app --cov-report=term-missing` は addopts から外し、呼び出し側（Makefile `test-backend` / test.yml の pytest step）で付与する**。カバレッジ出力は従来どおり維持される。

### Slack 通知チャンネル分割（4 Webhook）

| Secret 名 | 用途 | 送信元 workflow | 通知条件 |
|---|---|---|---|
| `SLACK_WEBHOOK_URL_CI` | 通常 CI の失敗 | `notify.yml` | CI conclusion = failure のみ（cancelled は concurrency キャンセルのノイズのため通知しない） |
| `SLACK_WEBHOOK_URL_DEPLOY` | Cloud Run / Cloudflare Pages デプロイ結果 | `notify.yml` | main/stg/dev への push で deploy ジョブが実行された run（成功・失敗とも） |
| `SLACK_WEBHOOK_URL_QUALITY` | ミューテーションテスト結果 | `mutation.yml` | 週次 / 手動実行の完了時（killed / survived / score%、閾値未満は ⚠️ 強調） |
| `SLACK_WEBHOOK_URL_DEPS` | 依存更新 PR の起票 | `deps-notify.yml` | renovate[bot] / dependabot[bot] の PR opened |

- 送信は `slackapi/slack-github-action` v2（既存慣例どおり commit SHA ピン。Renovate `helpers:pinGitHubActionDigests` が以後管理）。
- **Secrets はプレースホルダー**: Slack チャンネル未作成のため値は未登録。各通知ステップは `env` 経由の空判定で **Secret 未登録の間は静かに skip** され、ワークフローは green のまま（登録手順は `docs/development.md`）。

### 通知の実装方式

- **CI / デプロイ通知は `workflow_run`**（`workflows: ["CI"]` / `types: [completed]`）で受ける。ci.yml 側には一切手を入れず疎結合にする。workflow_run の payload にはジョブ単位の結果が無いため、jobs API（`permissions: actions: read` + runner 標準の `gh` CLI）で失敗ジョブ名・deploy ジョブ結果（再利用ワークフローは `deploy-dev / deploy-web` 形式で列挙）を補完する。
- **依存更新通知は `pull_request_target` [opened]**: Dependabot actor の `pull_request` イベントは Actions secrets を参照できない（Dependabot secrets に分離される）ため。PR コードは checkout せず、actor をボットに限定しているため安全。
- **インジェクション対策**: PR タイトル・display_title 等の外部入力は `run` スクリプトへ直接式展開せず `env` 経由で渡し、Slack payload へは `toJSON()` でエスケープして埋め込む。

## 代替案

- **mutmut ではなく cosmic-ray（backend）**: 並列実行は強いが設定が重く、pytest との統合と結果の可読性（`mutmut browse` / `export-cicd-stats`）で mutmut が優位。
- **PR ごとの差分ミューテーション（incremental）**: 検出は早いが実行時間が PR CI を直撃する。まず週次で baseline を作る方が導入コストが低い。
- **通知を ci.yml 内のジョブとして追加**: workflow_run より実装が単純だが、ci.yml / test.yml（再利用ワークフロー）に secrets 配線が増え、通知都合の変更が CI 本体の変更履歴に混ざる。疎結合な workflow_run を採用。
- **DEPS 通知を `pull_request` トリガーで実装**: Dependabot の secrets 分離で Webhook が参照できず不成立。
- **Slack App（chat.postMessage）方式**: チャンネル増減に強いが Bot トークン管理が必要。まず Incoming Webhook のチャンネル分割で開始し、必要になれば移行する。

## トレードオフ・既知のリスク

- **実行時間**: backend は実 SQLite に当てる統合テスト主体のため、フル実行が 120 分の timeout に達する可能性がある。その場合は `[tool.mutmut]` の対象を削るか `mutate_only_covered_lines` を検討する。
- **warn-only 期間はスコア悪化を強制できない**: ゲート化までは Slack の ⚠️ 通知と週次レビュー運用が頼り。
- **`slackapi/slack-github-action` の SHA は初回実行で要検証**: 導入時の実行環境から外部リポジトリの SHA 解決ができず、`v2.1.0` の SHA は事後検証前提でピンしている。初回の workflow_dispatch で action 解決に失敗した場合は SHA を修正する（Renovate の `pinDigests` が以後のバージョン追従を管理）。
- **workflow_run のジョブ名依存**: deploy 通知は「ジョブ名が `deploy-` で始まる」ことに依存する。ci.yml のジョブ名を変更する場合は notify.yml の jq フィルタも見直すこと。
- **週次 cron は main ブランチの定義でのみ発火**: feature ブランチ上の mutation.yml は schedule では動かない（workflow_dispatch で検証する）。

## 将来の移行条件

- baseline が安定したら `MUTATION_SCORE_THRESHOLD` を実測に合わせて調整し、`thresholds.break`（Stryker）/ CI ゲート化（mutmut）へ移行する。
- 通知チャンネルが増えたら Incoming Webhook 方式から Slack App（Bot トークン + チャンネル指定）へ移行する。
- ~~backend が uv 管理（PEP 621 + uv.lock）へ移行した場合、mutmut は dev dependency group（`uv add --dev`）へ移す。~~ → ADR-0021 Phase 0 で移行済み（dependency group ではなく `[project.dependencies]` に一本化。uv2nix の mkVirtualEnv が default 依存のみを build するため）。

## 関連リンク

- `.github/workflows/mutation.yml` / `notify.yml` / `deps-notify.yml`
- `backend/pyproject.toml`（`[tool.mutmut]` / pytest addopts）
- `web/stryker.conf.json`
- `docs/development.md`「ミューテーションテスト」節（ローカル実行・Secrets 登録手順）
- ADR-0014（Renovate。Action の SHA ピン運用）
- mutmut: https://mutmut.readthedocs.io/ / Stryker: https://stryker-mutator.io/docs/

---

> **追記（2026-07-16）**: ADR-0021（backend Python 環境の Nix フルマネージド化）の Accepted 昇格に伴い、本文中の「uv 非管理・requirements.txt が lockfile」という前提記述を更新した。
