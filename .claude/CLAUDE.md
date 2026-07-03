# DevForge - Claude Code ガイドライン

## このファイルの読み方

- 本ファイルは全体ルールの索引。AI エージェント（Claude Code 含む）が最初に読むべき内容を集約している。
- 領域固有ルール（backend / web / infra）は `.claude/rules/<scope>/*.md` に分割済み。対象パスを編集する際に自動でロードされる。重複は避け、詳細は各 rule ファイルへ寄せる。
- **DevForge Agent（`backend/app/services/agent/` / `backend/app/prompts/agent_*.md` / `backend/app/schemas/agent.py`）を変更する場合は、作業前に必ず `.claude/rules/backend/agent.md` を読むこと。** 制約の責務分離（スキーマ vs プロンプト）・エラー契約・DB 非更新原則など、意図せず壊しやすい不変条件が集約されている。

## AI エージェント実行方法

**原則: 開発ツールはすべて Nix devshell 経由で実行する。** ホスト側に Python / Node / ruff / tofu / WeasyPrint 用ネイティブライブラリは入っていない前提。

### 第一選択: `make` ターゲット

Makefile は `nix develop --command bash -c "..."` でラップ済み。AI は基本これを使う。**最新の一覧と詳細は `make help`** で確認する（本表は AI が即時参照する代表的なターゲットのみ）。

| 用途 | コマンド |
|---|---|
| CI 相当一括 | `make ci` （= `lint + test + build-web`） |
| Backend lint | `make lint-backend` |
| Backend 型チェック | `make typecheck-backend` （pyright。`make lint` に含まれる） |
| Backend test | `make test-backend` |
| Frontend lint | `make lint-web` |
| Frontend test | `make test-web` |
| Lint 自動修正 | `make lint-fix` |
| マイグレーション | `make migrate` / `make migrate-create MSG="..."` |
| インフラ validate | `make infra-validate` |
| コード重複検知 | `make dupe-check` （結果: `report/dupe/jscpd-report.json`） |
| ミューテーションテスト | `make mutation-backend` / `make mutation-web` （**長時間**。通常 CI には含まれない週次実行。詳細: 下記「ミューテーションテスト・Slack 通知」） |

セットアップ詳細・各コマンドの目的は `docs/development.md` を参照。

### 第二選択: `nix develop --command` ラッパー

make に無い操作（特定ファイルだけ ruff したい等）の場合のみ使う:

```bash
nix develop --command bash -c "cd backend && .venv/bin/python -m ruff check app/services/tasks/handlers/blog_summarize.py"
nix develop --command bash -c "cd backend && .venv/bin/python -m pytest tests/test_worker_extended.py -q"
nix develop --command bash -c "cd web && npm run test:e2e"
```

### 禁止: 生シェルでの直接実行

`cd backend && .venv/bin/python -m pytest ...` を nix の外で叩くと、`LD_LIBRARY_PATH` / `DYLD_LIBRARY_PATH` が未設定で WeasyPrint のインポートが `OSError: cannot load library 'libgobject-2.0-0'` で落ちる。AI は nix wrap を必ず通す。

### Sandbox と nix の競合（重要）

Claude Code の sandbox は `~/.cache/nix/fetcher-locks/*.lock` への書き込みを拒否する。`make lint-backend` / `make test-backend` を sandbox 有効で実行すると次のエラーになる:

```text
error: opening lock file "~/.cache/nix/fetcher-locks/...lock": Operation not permitted
```

この場合は sandbox を無効化して再実行する（Bash ツールの `dangerouslyDisableSandbox: true`）。nix の lock 書き込みは安全な操作なので例外として許容してよい。

## コーディング規約（共通）

- **コメント・ドキュメント**: コード内コメント・docstring・JSDoc はすべて**日本語**で記述する。
- **エラーメッセージ**: HTTPException の `detail` 等、ユーザーに返すメッセージはすべて**日本語**。
- **エラーメッセージのハードコード禁止**: ts/tsx でリテラル日本語を直接書かない（`throw new Error("...")` / `setError("...")` / `toast.error("...")` 等）。web 完結のメッセージは `web/src/constants/messages.ts` の定数を参照、API 経由のエラーは backend の `messages.json` 由来の `AppErrorResponse.message` を表示する。詳細: `.claude/rules/web/messages.md`
- **例外の握りつぶし禁止**: `except SomeException: pass` は禁止。最低でも `logger.debug/warning/error` でログを残す。補助処理（通知生成など）で抑制する場合も `logger.warning` でログを出すこと。
- **過剰な抽象化を避ける**: PEP8 を守るな、PEP8 を理解した上で抽象化しろ。

言語別の詳細ルールは `.claude/rules/{backend,web,infra}/` を参照。
領域横断の共通ルール（DRY / 重複検知）は `.claude/rules/common/duplication.md` を参照。

## CI 確認ルール

アプリケーションの改修後は、ローカルで CI 相当を pass させてから完了報告する。

```bash
# 一括（最速・推奨）
make ci
```

詳細なローカル CI 手順・個別コマンドは `docs/development.md`「テスト・リント」セクションを参照。

### E2E テストのトリガー

以下のいずれかに該当する変更を行った場合、E2E を必ず実行する:

- 新しいページまたはルートの追加
- 認証・ナビゲーション・レイアウトの変更
- 通知ベルなどサイドバーコンポーネントの変更
- バックエンド API の追加・変更で、フロントエンドの UI フローに影響するもの

```bash
nix develop --command bash -c "cd web && npm run test:e2e"
```

### SSoT 生成物（codegen）のトリガー — 必須

**SSoT（正本）から自動生成される成果物に影響する変更をしたら、生成物の再生成とコミットは必須。** 正本だけ直して生成物を更新し忘れると、CI の drift チェックで必ず落ちる（コミット段階で気づけず手戻りになる）。

| 正本（変更したら） | 再生成コマンド | コミットすべき生成物 | CI ジョブ |
|---|---|---|---|
| backend の OpenAPI スキーマ（`app/schemas/` の Pydantic、router のシグネチャ・query/path パラメータ・**endpoint/schema の docstring**） | `make codegen-types` | `web/src/api/generated.ts`（`backend/openapi.json` は gitignore で対象外） | `codegen-drift`（ADR-0007） |

- **判定基準**: 「OpenAPI スペックに出るものを変えたか」。エンドポイントの追加・削除、リクエスト/レスポンス型の変更、query/path パラメータの増減はもちろん、**docstring の文言変更だけでも description として spec に反映される**ため再生成が要る（今回の codegen-drift はこれで発生）。
- backend の `app/schemas/` / `app/routers/` を触ったら、`make ci` 前に `make codegen-types` を回して `git diff web/src/api/generated.ts` を確認する。差分が出たら必ず同じ PR でコミットする。
- 新しい SSoT→生成物の系統を追加した場合は、本表に行を足して再発防止の対象に含める。

CI 定義: `.github/workflows/ci.yml`

## ミューテーションテスト・Slack 通知（ADR-0017）

テストの検出力（弱い assertion / 実装なぞり）を週次のミューテーションテストで可視化し、CI 結果は用途別 Slack チャンネルへ通知する。詳細（ローカル実行・レポート確認・Secrets 登録手順）は `docs/development.md`「ミューテーションテスト」「Slack 通知」節が正本。

- **ローカル実行**: `make mutation-backend`（mutmut）/ `make mutation-web`（Stryker）。**フル実行は長時間**のため、対象を絞る場合は `nix develop --command bash -c "cd backend && .venv/bin/python -m mutmut run 'app.services.shared.sort_utils*'"` / `nix develop --command bash -c "cd web && npx stryker run --mutate 'src/utils/text.ts'"`
- **対象スコープの正本**: backend = `backend/pyproject.toml` の `[tool.mutmut]`、web = `web/stryker.conf.json`。決定論的ビジネスロジックに限定（schemas / models / routers / 自動生成コード等は対象外）
- **CI**: `.github/workflows/mutation.yml`（週次 月曜 3:00 JST + workflow_dispatch。**PR/push では動かない・fail しない warn-only**）
- **pytest の `--cov` は addopts に戻さない**: mutmut 干渉回避のため Makefile / test.yml の呼び出し側で付与している（ADR-0017）

| Slack Secret | 用途 | 送信元 workflow |
|---|---|---|
| `SLACK_WEBHOOK_URL_CI` | 通常 CI の失敗のみ | `notify.yml`（workflow_run） |
| `SLACK_WEBHOOK_URL_DEPLOY` | Cloud Run / Cloudflare Pages デプロイ結果（成功・失敗とも） | `notify.yml`（workflow_run） |
| `SLACK_WEBHOOK_URL_QUALITY` | ミューテーションテスト結果（score が閾値未満で ⚠️ 強調） | `mutation.yml` |
| `SLACK_WEBHOOK_URL_DEPS` | Renovate / Dependabot の PR 起票 | `deps-notify.yml`（pull_request_target） |

Secrets は未登録の間は通知が静かに skip される（CI は green のまま）。チャンネル作成後の登録は `gh secret set SLACK_WEBHOOK_URL_CI --body "https://hooks.slack.com/services/..."`（4 つとも。手順詳細: `docs/development.md`）。

## 作業開始時のブランチ運用（デフォルト）

**新しい作業に着手するときは、最初に main から作業ブランチを切る。** これはデフォルト挙動であり、合言葉や明示指示を待たない。

- 作業開始時に `main`（または `master`）ブランチ上にいる場合、コードに触れる前に `git fetch origin main` してから `origin/main` 起点で feature ブランチを切る（例: `git switch -c feat/<topic> origin/main`）。
- 既に feature ブランチ上にいる場合:
  - 差分（未コミット変更 or main より進んだコミット）が**無い**ならそのまま継続してよい。
  - 差分が**ある**場合は、別作業の続きと混ざる恐れがあるため**勝手に切り直さず、main から新しく作業ブランチを切るべきかユーザーに相談する**。今の差分を引き継ぐのか、退避（commit / stash）してから切るのかも併せて確認する。
- ブランチ名は変更内容が分かる英語の kebab-case（`feat/` `fix/` `docs/` `refactor/` 等のプレフィックス）。
- 例外: 単発の調査・閲覧のみでコミットを伴わない作業は、ブランチを切らなくてよい。

これにより `main` への直接コミットを防ぐ。後続の stage / commit / pr フローはこのブランチ上で進める。

## コミット / PR フロー

修正〜PR は **合言葉ベースの段階制御**で進める。各段で必ず止まる。diff 全文は会話に出さず（ユーザーがエディタで確認する）、要約と判断が必要な事案だけ提示する。

| 合言葉 | やること |
|---|---|
| **stage** | 実装 → `make ci` → `git add` まで。作業開始時にブランチを切り損ねて `main` にいた場合はここで feature ブランチを `origin/main` 起点で切る（本来は「作業開始時のブランチ運用」で切る）。会話に「サマリ＋判断が必要な事案」を提示し、ユーザーのエディタ確認を待つ |
| **commit** | コミットメッセージ案（**日本語**）を提示 → **ユーザー承認を待ってから** commit。承認は必須ゲート |
| **pr** | `git fetch origin main` → `git log --oneline origin/main..HEAD` / `git diff --stat origin/main...HEAD` で**最新の main との差分を確認**（ローカルの古い `origin/main` 参照で誤認しないため）→ `git push` → `gh pr create`（**日本語**タイトル/本文、base = `main`）→ PR URL を返す |
| **pr 後の追従** | PR 作成後、`gh pr checks` / `gh pr view --comments` で **CI と指摘を確認**。こけ・指摘があれば修正 → `make ci` → 同ブランチへ push を green かつ解消まで繰り返す。CI 修正は実装フェーズなので元のモデルで（Haiku のままにしない）。**ただし意思決定を要する指摘（設計・API/型契約・挙動変更）と diff 範囲を逸脱する指摘は、勝手に直さず指摘内容・対応案・影響範囲を提示して承認を待つ**。範囲内の機械的修正（lint / typo 等）は承認不要 |

修正依頼時に「PR まで」等と言われたら、コミットメッセージ承認だけ挟んで一気通貫で進めてよい。段階を飛ばす指定も尊重する。

**stage 時に必ず明示する「判断が必要な事案」**（無ければ `git diff --stat` だけで軽く流す）:

- **破壊的変更**: ファイル削除 / 既存挙動の変更 / API・型の契約変更
- **設計分岐**: 実装方針が複数あって AI が選んだ箇所
- **依頼範囲外**: 直すために範囲外を触る必要が出た
- **CI 注意点**: 落ちた・skip した・新規テスト追加・E2E が必要な変更
- **依存 / 環境変数の追加**: 新パッケージ、env var 追加（`env_keys.py` の 4 箇所同期が要るもの）
- **大量自動生成差分**: lockfile / OpenAPI 生成物など、レビュー対象外として切り分けたいもの
- **未完 / TODO**: 一部を後回しにした場合

## モデル切り替えルール（コスト最適化）

git 定型作業は Haiku で十分なため、適切なタイミングでユーザーにモデル切り替えを案内する。
Claude Code は `/model` コマンドを自分では実行できないため、案内を出してユーザーに切り替えてもらう。

| 作業フェーズ | 推奨モデル |
|---|---|
| コード修正・実装・調査・CI 修正 | セッション開始時の設定モデル（Sonnet / Opus / Fable 等） |
| `make ci` pass 後の git 操作（add / commit / push / pr） | Haiku |

**案内タイミング**:
1. `make ci` が green になり、git 操作フェーズに入る直前に「git 操作は `/model haiku` に切り替えると節約できます」と案内する
2. `pr` 完了後に「実装作業に戻る場合は `/model <セッション開始時のモデル>` に戻してください」と案内する

**制約**:
- CI が落ちた場合の修正（実装フェーズ）は Haiku のまま行わない。修正は元のモデルで行い、再度 `make ci` を通してから Haiku に切り替える
- `stage` 合言葉を受けた段階ではまだ `make ci` が残っている可能性があるため、CI 完了まで Haiku に切り替えない

## 失敗から学んだ知見

過去の手戻り・障害から導いた再発防止ルール。**領域固有の項目は各 scoped rule に集約済み**（対象パス編集時に自動ロードされる）。ここには領域横断（常に効かせたい）ものだけを残す。

- **テストで DB をモックしない**: 統合テストは実 DB（テスト用 SQLite セッション）に当てる。モック/本番乖離でマイグレーション失敗を見落とした実績がある。
- **ネイティブ／コンテナ起動はスモークテストで必ず検証する**: pytest（`make test-backend`）は標準 SQLite で動き、本番イメージのビルド・libsql ネイティブドライバ・alembic マイグレーション・uvicorn 起動の実行パスを通らない。この穴は CI の `smoke-backend` ジョブ（本番イメージ build → 実 libSQL 起動 → `/health` 200 を検証）で塞ぐ。backend の Dockerfile / 依存 / 起動経路を変えたら smoke-backend が green であることを確認する（Python 3.14 bump で libsql が起動時 segfault した事象の再発防止）。詳細: `.claude/rules/backend/test.md` / `database.md`
- **新規ブランチは `origin/main` 起点で切る**: リリース前は全てを `main` にマージする運用。以前は `origin/dev` 起点だったが dev 環境作業の名残で、現在は廃止。

領域別の再発防止ルールは各 scoped rule に集約（対象パス編集時に自動ロード）:

- **Backend**: 契約変更時の assert 見直し → `rules/backend/test.md` / lint の当該ファイル個別検証 → `rules/backend/python.md` / `IntegrityError` 後の再 SELECT は `None` 判定で `RuntimeError` → `rules/backend/database.md` / タスクハンドラの黙って return 禁止 → `rules/backend/architecture.md` / Router・ORM model の責務境界 → `rules/backend/layers.md`
- **Web**: 300/500 行超コンポーネント・サービスモジュールの分割検討 → `rules/web/component-design.md`

## 命名規約

| 種別 | 名前 |
|---|---|
| 職務経歴書（career history） | `Resume` / `resumes` テーブル |

## 環境変数

**正本**:
- 環境変数名の定数定義: `backend/app/core/env_keys.py`
- 用途と注入経路の一覧: `docs/api.md`「環境変数」セクション
- 本番（Cloud Run）の env block: `infra/modules/cloud_run/main.tf`
- ローカル開発の env: `docker-compose.yml`

backend 内で `os.getenv("XXX")` のように文字列リテラル直接参照は禁止。`from app.core import env_keys` した上で `os.getenv(env_keys.XXX)` を使う。新規環境変数を追加するときは env_keys.py のコメントに記載の手順（4 箇所同期）を必ず実行する。

## ADR（Architecture Decision Record）

技術選定・アーキテクチャ判断を行う際は必ず ADR 索引（`docs/adr/README.md`）から関連 ADR を辿り、既存の判断と矛盾しない実装を行うこと。索引にはテーマ別の決定系統（どの判断がどれを置き換え・前提にしているか）がまとまっている。

新たに重要な技術判断を行う場合は `CONTRIBUTING.md` の ADR 運用ルールに従い、ADR を作成してから実装を開始する。**ADR の新規作成・ステータス変更をしたら、同じ PR で索引も更新する**（存在・ステータス・見出し番号の整合は `make lint-adr-index` が CI で検証する）。

- ADR 索引（一覧・テーマ・決定系統の正本）: `docs/adr/README.md`
- 設計原則（ADR を貫く 7 原則。新規 ADR はどの原則に沿うかを明記する）: `docs/design-principles.md`
- テンプレート: `docs/adr/0000-template.md`
- 運用ルール: `CONTRIBUTING.md`
