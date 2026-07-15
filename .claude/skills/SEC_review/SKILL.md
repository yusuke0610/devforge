---
name: SEC_review
description: Use when running a security review / vulnerability check against the DevForge codebase based on `.claude/rules/security.md` — secrets leakage, env literal references, input validation, XSS, token storage, auth guards, rate limit, file upload, IAM least-privilege, Secret Manager. Also covers design-level security holes (IDOR / authorization model / trust boundaries / SSRF / OAuth / mass assignment), dependency supply-chain risk (CVE audit, lockfile/version pinning, GitHub Actions SHA pinning, typosquatting / dependency confusion), and missing exploit-style unit tests (attacker-perspective regression tests). Produces a report under `report/SEC_report_<timestamp>.md`. Trigger on requests such as "セキュリティチェック", "security review", "脆弱性を見て", "設計のセキュリティホール", "サプライチェーン", "PR 前のセキュリティ確認", "SEC_review 実行".
---

# Security Review

`.claude/rules/security.md`（全領域横断セキュリティルール）を走査軸に、コードへセキュリティ観点のレビューを当てる skill。
組み込みの汎用 `/security-review` と違い、DevForge 固有の正本（`env_keys.py` / `messages.ts` / Secret Manager 運用 / auth-security）に紐づいて判定する。

実装変更は `SEC_apply` skill が担う。**本 skill はレビューと提案までで止める。**

## 先に読む

- `.claude/CLAUDE.md`
- `.claude/rules/security.md`（**正本**。末尾のチェックリストが走査軸）
- `.claude/rules/backend/auth-security.md`（JWT / Cookie / rate limit / CORS / INTERNAL_SECRET）
- `backend/app/core/env_keys.py`（環境変数名の正本。リテラル参照検出の基準）
- `.claude/rules/web/messages.md`（誤検知除外の基準。テスト・英語開発者向け・console は許容）
- `report/dupe/jscpd-report.json` が存在すれば参考程度に（重複は本 skill の主目的ではない）

## スキャン範囲の決定

引数で範囲を切り替える。**最初に必ず採用した範囲を 1 行でユーザーへ返す。**

```bash
# 省略時 = 現ブランチ差分（PR 前チェック向け・デフォルト）
/SEC_review

# 全体スキャン
/SEC_review full
```

- **差分（デフォルト）**: `git diff --name-only origin/main...HEAD`。`origin/main` が無ければ `origin/dev`、それも無ければ `HEAD~1` にフォールバック。検出されたファイルのうち `backend/** web/** infra/** .github/workflows/**` に該当するものを対象にする。
- **全体（`full`）**: `backend/** web/** infra/** .github/workflows/**` 全体を security.md 全項目で走査する。
- 差分が空（コミットなし）なら全体スキャンに自動フォールバックし、その旨を 1 行で告げる。

```text
スキャン範囲: 差分 (origin/main...HEAD) — 対象 7 ファイル
```

## 成果物の出力先（必須）

レビュー本文はターミナルに垂れ流さず、必ずファイルへ保存する。スクロールで流れて読み返せなくなるのを防ぐためのルール。

- 保存先: `report/SEC_report_<YYYYMMDD_HHMM>.md`
  - 例: `report/SEC_report_20260530_1042.md`
  - `report/` が無ければ作成する (`mkdir -p report`)
  - タイムスタンプはレビュー開始時刻のローカルタイム (`date +%Y%m%d_%H%M`)
- ファイル中身は末尾の「推奨出力フォーマット」に従う
- 既存の `SEC_report_*.md` は削除しない（履歴として残す）

### ターミナルへの出力ルール

- レポート本文を assistant メッセージへ貼らない（ファイルにだけ書く）
- ターミナルには以下だけを返す:
  1. スキャン範囲（差分 / 全体）
  2. 保存先パス（`report/SEC_report_YYYYMMDD_HHMM.md`）
  3. `Verdict` セクションの 3-5 行サマリ（Critical / High の件数を含める）
  4. 次に取るべきアクション 1-2 行（例: `/SEC_apply` を促す）
- Findings などの詳細セクションはファイル参照に留める

## 目的

「security.md のどのルールに、どこで違反しているか」を、根拠（ファイル:行 + 引用ルール）付きで列挙する。
単なる「なんとなく危なそう」ではなく、各 Finding に **どのルール違反か** と **どう直すか** を必ず添える。

加えて、grep で機械検出できる規約違反（後述の「検査項目」）だけでなく、**設計レベルのセキュリティホール**（認可モデルの欠陥・信頼境界の取り違え）と **依存サプライチェーンのリスク** を必ず観点に含める。これらは grep だけでは出ないため、コードフローを追って判断する。

## 設計観点レビュー（Security-by-Design）

「個々の行は規約に沿っているが、設計として穴がある」類を拾う。DevForge のアーキテクチャ（`.claude/rules/backend/architecture.md` / `auth-security.md`）を踏まえて以下を見る。

- **オブジェクトレベル認可 / IDOR**: エンドポイントが `user_id` 境界を必ず効かせているか。`resumes` / `blog_accounts` 等のリソースを ID 直指定で取得・更新する経路で「他人のリソースを取れてしまう」穴がないか（`get_current_user` で認証だけ通して認可（所有者一致）を確認していないケースが典型）。repository のクエリに `user_id` フィルタが入っているかまで追う。
- **信頼境界（Trust boundary）**: Cloudflare Pages → Cloud Run の `INTERNAL_SECRET` ヘッダ検証が `routers/internal.py`（Cloud Tasks → backend）で実際に効いているか。内部 API が認証なしで外部公開されていないか。
- **SSRF / 外部フェッチ**: `services/intelligence/github/api_client.py` や blog collector がユーザー指定の URL / リポジトリ名を使って外部へ fetch する経路で、宛先を検証せず任意 URL を叩けないか（内部メタデータエンドポイントへの到達など）。
- **OAuth フローの設計**: GitHub OAuth の `state` が backend Cookie で検証されているか（web のみ検証は不可）、`redirect_uri` が許可リスト内に固定されているか（オープンリダイレクト防止）。
- **トークンライフサイクル**: アクセス/リフレッシュトークンの失効・ローテーション、ログアウト時の Cookie 破棄、リフレッシュトークン再利用検知の有無。
- **マスアサインメント**: Pydantic スキーマが更新系で「ユーザーが書き換えてはいけないフィールド」（`user_id` / `role` / `is_admin` 相当 / タイムスタンプ）まで受け付けていないか。入力スキーマと DB モデルのフィールド差を確認。
- **ビジネスロジック濫用**: rate limit のない高コスト経路（外部 API / PDF 生成）を繰り返し叩くコスト増幅、冪等性のない副作用の二重実行。
- **エラー / 例外からの情報漏洩**: スタックトレースや内部パス・SQL をユーザー向けレスポンスに返していないか（`detail` に生例外を載せていないか）。
- **暗号設計**: `FIELD_ENCRYPTION_KEY`（Fernet）で暗号化すべき機微フィールドが平文保存されていないか。鍵の取り違え・固定 IV 等。

各設計 Finding には「どのフローのどの前提が崩れると何が起きるか（攻撃シナリオ）」を 1-2 行で添える。

## 検査項目（security.md チェックリストを走査軸にする）

各項目に grep ベースの検出コマンドを付ける。差分モードでは対象ファイルに絞って実行する。

### 1. 秘密情報の混入（Secrets Management）

- `.env` / `.env.*` / `*.pem` / `*.key` / GCP サービスアカウント鍵 / トークンをハードコードした設定が **git 追跡対象に入っていないか**:
  - `git ls-files | rg -n '\.(env|pem|key)$|service.?account.*\.json'`
  - `.gitignore` に上記が入っているかも確認
- ソース中のハードコードされた認証情報: `rg -n '(api[_-]?key|secret|token|password)\s*[:=]\s*["'"'"'][A-Za-z0-9_\-]{16,}' backend web infra`
- 実ツールがあれば併用: `gitleaks detect --no-banner`（無ければ「未実行・要手動」と Secrets Scan に記録）

### 2. 環境変数のリテラル直接参照

- `rg -n 'os\.getenv\("' backend/app`（`env_keys.XXX` 経由でないリテラルは違反）
- `rg -n 'os\.environ\[' backend/app`
- web は `import.meta.env.VITE_...` の散在を確認

### 3. ログへの秘密情報出力

- `rg -n 'logger\.(debug|info|warning|error).*(token|secret|password|email|api[_-]?key)' backend/app`（目視で文脈確認、定数名だけなら誤検知）

### 4. 入力バリデーション / SQL インジェクション

- 新規 router の `Any` / `dict` 素通し: `rg -n ': (Any|dict)\b' backend/app/routers`
- SQL 文字列連結: `rg -n 'text\(f["'"'"']|\.execute\(f["'"'"']|".*SELECT.*"\s*\+' backend/app`
- API エンドポイントの引数が Pydantic モデルで受けているか

### 5. LLM プロンプトのサニタイズ

- DevForge Agent（ADR-0010 で LLM を対話型機能として再導入。マルチプロバイダ = ADR-0013、Vertex AI 経由 = ADR-0015）がユーザー由来文字列（経歴書フィールド・チャット入力）をプロンプトへ埋め込む
- `backend/app/services/agent/context_builder.py` でのユーザー入力の埋め込み方（区切り・エスケープ・指示との分離）を確認する
- プロンプト正本 `backend/app/prompts/agent_*.md` は静的維持が原則（`.claude/rules/backend/agent.md`）。動的にユーザー文字列を連結する変更が入っていないか確認する
- LLM 出力の取り扱い: 構造化出力（`output_schema.py`）を素通しで DB へ書き込んでいないか（Agent は DB 非更新原則）

### 6. Frontend XSS

- `rg -n 'dangerouslySetInnerHTML|\.innerHTML|eval\(|new Function\(' web/src`
- `target="_blank"` の `rel="noopener noreferrer"` 欠落: `rg -n 'target=["'"'"']_blank' web/src` → 各箇所で rel を確認
- Markdown レンダラの sanitize 無効化（`react-markdown` の `rehype-raw` 等）

### 7. トークン保管（Frontend）

- `rg -n '(localStorage|sessionStorage)\.(set|get)Item' web/src` でトークン保存がないか
- Redux store に生のトークン文字列を載せていないか

### 8. 認証ガード

- 新規エンドポイントに `get_current_user` 依存が付いているか: `rg -n '@router\.(get|post|put|patch|delete)' backend/app/routers` の各関数で `Depends(get_current_user)` 有無を確認（公開エンドポイントは理由を Info に）

### 9. Rate limit

- 高コスト処理（外部 API 呼び出し等）に `slowapi` の `@limiter.limit` が付いているか

### 10. ファイルアップロード

- アップロード機能があれば: MIME(magic bytes)検証 / サイズ上限 / ファイル名サニタイズ(UUID リネーム) / 保存先（本番は GCS）の 4 点を確認

### 11. Infra: IAM 最小権限

- `rg -n 'roles/(owner|editor)' infra/` が Cloud Run SA に付いていないか
- 新規ロール付与に「なぜ必要か」のコメントがあるか（`infra/modules/service_account/`）

### 12. Infra: Secret Manager

- シークレットを扱う resource に `sensitive = true` が付いているか: `rg -n 'sensitive\s*=\s*true' infra/`（欠落候補を目視）
- 平文シークレットの埋め込みがないか

### 13. 依存監査 / サプライチェーン攻撃リスク（Dependency & Supply Chain）

既知 CVE だけでなく「依存経路そのものが攻撃面になる」観点で見る。CI には既に audit が配線済み（`.github/workflows/ci.yml`: `npm audit --audit-level=high` / uv.lock を export した requirements への `pip-audit`）なので、ローカルでは差分の妥当性確認に重点を置く。

- **既知 CVE スキャン**（実行可能なら）:
  - `nix develop --command bash -c "cd web && npm audit --audit-level=high"`
  - `nix develop --command bash -c "cd backend && uv export --frozen --no-emit-project --no-hashes --format requirements-txt --output-file /tmp/req-audit.txt && uv tool run --python 3.13 pip-audit -r /tmp/req-audit.txt"`（実行できなければ「未実行・要手動」と記録。**本 skill で新規ツール導入はしない**）
  - High / Critical を Findings に取り込む
- **バージョン固定 / lockfile 整合**: 直接依存にレンジ指定（`^` / `~` / `*` / `>=` のみ）が無いか、lockfile（`package-lock.json` / `uv.lock` 等）が commit され integrity hash を持つか。`backend/pyproject.toml` の `[project.dependencies]` が pin（`==`）されているか（ADR-0021 Phase 0）。
- **GitHub Actions のピン留め**: `uses:` がタグ（`@v4`）ではなく commit SHA で固定されているか（直近 commit「GitHub Actions のサプライチェーン保護」で対応済みの方針を維持。`rg -n 'uses:.*@v[0-9]' .github/workflows` で SHA 未固定を検出）。
- **新規・更新依存の素性**: 差分で追加された依存があれば、メンテ状況・ダウンロード規模・typosquatting（正規パッケージ名との1文字違い）・dependency confusion（社内名と公開名の衝突）を確認。`postinstall` / ビルドスクリプトを持つ npm パッケージは特に注視。
- **取得元の信頼性**: パッケージ取得が公式レジストリ（npm / PyPI）以外（任意 git URL / 直リンク tarball）を指していないか。
- **transitive 依存の急増**: 1 パッケージ追加で推移的依存が大量に増えていないか（攻撃面の拡大）。
- 上記は Findings の重大度に「サプライチェーン」観点を明記して取り込む。

## 重大度分類

- **Critical**: 秘密情報の git 混入、認証バイパス、SQL インジェクション、本番 SA への owner/editor
- **High**: env リテラル参照、認証ガード欠落、`dangerouslySetInnerHTML` 新規使用、High CVE
- **Medium**: rate limit 欠落、`rel` 欠落、`sensitive` 欠落、ログ漏洩の疑い
- **Low**: 軽微な hardening 余地
- **Info / Allowed**: 誤検知・許容例外（テストコード / `constants/messages.ts` / 英語開発者向けメッセージ / `console.*` / 意図的な公開エンドポイント）。**理由を必ず残す**（`.claude/rules/web/messages.md` の例外節に準拠）。

各 Finding には **security.md のどのルール違反か** を必ず引用する。

## 脆弱性を突いた unittest の観点（Exploit-style Tests）

「攻撃が失敗することを assert する」テストが存在するかをレビューする。設計観点で見つけた穴は、回帰防止として **攻撃者視点のテスト** で固定すべき。不足しているケースを Findings とは別に列挙する（実際に書くのは `SEC_apply`）。

確認・提案する観点（`.claude/rules/backend/test.md` の方針に沿い、DB はモックせず実 SQLite セッション、外部 API はモック）:

- **認可（IDOR）**: ユーザー A がユーザー B のリソース（resume / blog_account / notification）を ID 直指定で取得・更新・削除 → **403 / 404 を返す**ことを assert。所有者一致を破る試みが通らないこと。
- **認証ガード**: トークン無し / 期限切れ / 改竄トークンで保護エンドポイントを叩く → **401**。`get_current_user` 依存の欠落を検知する。
- **入力境界**: 過大長・型不正・想定外フィールド（マスアサインメント）を投げる → **422 / 無視**。`user_id` 上書きが効かないこと。
- **CSRF / OAuth state**: `state` 不一致・欠落の OAuth コールバック → 拒否。CSRF トークン不正 → 拒否。
- **内部 API 境界**: `INTERNAL_SECRET` 無し / 不正で `routers/internal.py` を叩く → 拒否。
- **SSRF**: collector / GitHub クライアントに内部アドレス・スキーム不正な URL を渡す → 拒否（モックで宛先検証ロジックを通す）。
- **rate limit**: 高コスト経路を上限超で連打 → **429**。
- **暗号**: 機微フィールドが DB 上で平文でないこと（保存後に raw 値が読めない）を assert。

各観点は「守る仕様」がテスト名から読めること（例: `test_他人のresumeはget_404`）。既にカバー済みなら Info に、未カバーなら「Missing Exploit Tests」に挙げる。

## 推奨出力フォーマット

下記テンプレートを `report/SEC_report_<YYYYMMDD_HHMM>.md` に書き込む。ターミナルには貼らない。

````markdown
# Security Review

- スキャン範囲: 差分 (origin/main...HEAD) / 全体
- 対象ファイル数: N

## Verdict
- セキュリティ総評を 3-5 行で。Critical / High の件数、設計観点の穴の有無、サプライチェーンリスク、不足する exploit テスト数を含める。

## Findings
### Critical
- [path/to/file:line] 何が問題か。なぜ危険か。どう直すか。（違反ルール: security.md「§秘密情報管理」など）

### High
- ...

### Medium
- ...

### Low
- ...

## Design-level Findings
- **観点**: <IDOR / 信頼境界 / SSRF / OAuth / マスアサインメント / 暗号 など>
- [path:line] 設計上の穴。**攻撃シナリオ**（何が崩れると何が起きるか 1-2 行）。修正方針。

## Dependency & Supply Chain
- npm audit: <結果 or 未実行理由>
- pip-audit: <結果 or 未実行理由>
- バージョン固定 / lockfile integrity: <OK / 緩い指定の箇所>
- GitHub Actions SHA 固定: <OK / 未固定 uses 一覧>
- 新規・更新依存の素性（typosquatting / dependency confusion / postinstall）: <なし / 懸念箇所>

## Secrets Scan
- git 追跡対象の秘密ファイル: <なし / 検出パス>
- ハードコード認証情報: <なし / 検出箇所>
- gitleaks: <結果 or 未実行>

## Missing Exploit Tests
- [対象エンドポイント / モジュール] 追加すべき攻撃者視点テスト。守る仕様（例: `test_他人のresumeはget_404`）。期待結果（401 / 403 / 422 / 429 / 拒否）。

## False Positives / Allowed
- [path:line] 検出されたが許容する理由（テスト / messages.ts / 英語開発者向け 等）

## Remediation Plan
1. まず直すべき Critical / High
2. 次に対応する Medium
3. 最後に検討する Low

## Validation
- 実行したコマンド（grep / git / audit）
- 未実行のものとその理由
````

## 最低限の検証コマンド

- スキャンは grep / git ベースで破壊なし。差分対象は `git diff --name-only` で取得。
- 依存監査は nix wrap 経由で実行（生シェルで python を直接叩かない。devshell 外では backend の Python 環境も WeasyPrint の動的ライブラリも解決できない）。
- `make lint-*` / `make test-*` は本 skill では必須としない（修正検証は `SEC_apply` 側で回す）。

実装変更は `SEC_apply` skill が担う。本 skill はレビューと提案までで止める。
