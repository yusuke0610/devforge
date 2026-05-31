---
name: SEC_apply
description: Use when applying the security findings produced by the SEC_review skill. Reads `report/SEC_report_<timestamp>.md` (latest by default, or a path passed as argument), confirms scope with the user, implements the fixes against backend / frontend / infra (including design-level authorization/SSRF/OAuth fixes and dependency supply-chain hardening), writes exploit-style regression unit tests for the findings, runs lint/test/audit, then writes a result report to `report/SEC_pr_<timestamp>.md`. Trigger on requests such as "SEC_apply 実行", "セキュリティ指摘を修正", "SEC レポートを適用", "脆弱性を直して", "exploit テストを追加".
---

# Security Fix Apply

`SEC_review` skill が生成したレビュー (`report/SEC_report_*.md`) を入力にして、実際のセキュリティ修正・検証・PR 用レポート作成までを行う skill。

## 先に読む

- `.claude/CLAUDE.md`
- `.claude/skills/SEC_review/SKILL.md`（出力フォーマットの参照元）
- `.claude/rules/security.md`
- `.claude/rules/backend/auth-security.md`
- 影響領域に応じて `.claude/rules/{backend,frontend,infra}/` の該当ルール
- `backend/app/core/env_keys.py`（env 参照の正本）
- `.claude/rules/frontend/messages.md`（frontend メッセージの正本）

## 入力（対象レポートの選択）

引数で明示パスが渡されていればそれを使う。なければ `report/SEC_report_*.md` の中で最新（mtime 降順）を採用する。

```bash
# 明示
/SEC_apply report/SEC_report_20260530_1042.md

# 省略時 = 最新を自動採用
/SEC_apply
```

最初に必ずユーザーへ「採用したレポートのパス」を 1 行返す。

```text
採用レポート: report/SEC_report_20260530_1042.md
```

`report/` 配下に `SEC_report_*.md` が一つも無い場合はここで停止し、`/SEC_review` の実行を促す。

## 実装スコープの確認（必須）

レポートを読み込んだら、Findings を Critical / High / Medium / Low の件数で集計してユーザーへ提示し、どこまで修正するかを **毎回必ず聞く**。勝手に全件着手してはいけない。

提示例:

```text
採用レポート: report/SEC_report_20260530_1042.md
Findings: Critical 1 / High 3 / Medium 5 / Low 2
Design-level: 2（IDOR 1 / SSRF 1）
Dependency & Supply Chain: High CVE 2 / SHA 未固定 1
Secrets Scan: 混入 1
Missing Exploit Tests: 4

どこまで適用しますか？
  1) Critical のみ
  2) Critical + High
  3) 設計観点(IDOR/SSRF/認可)も含める
  4) 依存(CVE 更新 / 固定 / SHA ピン留め)も含める
  5) Secrets 対応(rotate/除去)も含める
  6) Missing Exploit Tests(攻撃者視点テスト追加)も含める
  7) 全部
  8) 個別に選ぶ（番号で指定）
```

`AskUserQuestion` で選ばせるのが望ましい。「個別」が選ばれた場合は、Findings の見出しを番号付きで列挙して再選択させる。

## 実装の進め方

1. **タスク化**: 採用した各 Finding を `TaskCreate` で 1 タスクずつ切り、`in_progress` → `completed` を必ず更新する。
2. **小さく分ける**: 「秘密情報除去」「env_keys 化」「認証ガード追加」「XSS 修正」「依存更新」を別タスクにする。1 タスクあたりの diff は読める範囲に保つ。
3. **DevForge コーディング規約を厳守**:
   - コメント・docstring は日本語、HTTPException の `detail` は日本語
   - frontend のユーザー向け文言はリテラル禁止 → `frontend/src/constants/messages.ts` 経由（`.claude/rules/frontend/messages.md`）
   - 環境変数は `os.getenv(env_keys.XXX)` 経由。リテラル `os.getenv("XXX")` 禁止。新規 env 追加時は env_keys.py の 4 箇所同期手順を踏む
   - `except SomeException: pass` 禁止。最低限 `logger.warning`
   - 黙って return 禁止。失敗パスは適切な例外を `raise`
   - 統合テストで DB をモックしない（実 DB セッション）
4. **秘密情報の扱い（重要）**:
   - すでに git にコミット済みの秘密情報は、ファイル削除だけでは履歴に残る。**該当クレデンシャルの rotate（再発行）が必要**であることを警告し、git 履歴からの除去（filter-repo 等）は破壊的なのでユーザー判断を仰ぐ。勝手に履歴を書き換えない。
   - 今後の混入防止として `.gitignore` への追加は行ってよい。
5. **認証 / IAM 変更**:
   - 認証ガード追加・IAM ロール変更は影響が大きい。変更理由をコメントで残し、最小権限を守る。
6. **設計観点の修正（IDOR / SSRF / OAuth / マスアサインメント）**:
   - **IDOR**: repository / service のクエリに `user_id` 境界フィルタを追加し、所有者不一致を 403/404 にする。エンドポイント単独でなく repository 層まで直す。
   - **SSRF**: 外部 fetch（GitHub クライアント / collector）の宛先を許可スキーム・ホストで検証してから叩く。
   - **OAuth / state**: `state` の backend Cookie 検証、`redirect_uri` の許可リスト固定を確認・補強。
   - **マスアサインメント**: 入力 Pydantic スキーマから `user_id` / 権限系フィールドを除外し、サーバ側で固定。
   - 設計変更は必ず後述の exploit テストとセットで固定する。
7. **依存 / サプライチェーン対応**:
   - CVE 解消のバージョン更新は `--force` で無視せず該当パッケージを更新（`.claude/rules/security.md` の依存関係節）。更新後に再度 audit を回して解消を確認。
   - 緩いバージョン指定は pin（`requirements.txt` の `==` / lockfile commit）に寄せる。
   - GitHub Actions の `uses:` がタグ参照なら commit SHA 固定へ（直近 commit「GitHub Actions のサプライチェーン保護」の方針を踏襲）。
   - 不審な新規依存（typosquatting / dependency confusion / postinstall）は導入を止め、代替を提案。
8. **Missing Exploit Tests（攻撃者視点の回帰テスト）**:
   - レポートの「Missing Exploit Tests」と、今回直した設計穴を **攻撃が失敗することを assert** するテストで固定する。
   - `.claude/rules/backend/test.md` 準拠: DB はモックせず実 SQLite セッション、外部 API（GitHub / LLM / Cloud Tasks / Redis）はモック。失敗パスは `pytest.raises` か HTTP status assert で必ず明示検証（silent return を許容しない）。
   - テスト名に守る仕様を書く（例: `test_他人のresumeはget_404` / `test_internal_secret欠落は拒否` / `test_state不一致のoauth_callbackは拒否`）。
   - 配置先は既存方針: 認可/エンドポイントは `tests/test_<router>.py`、認証は `tests/test_auth.py` / `tests/test_oauth_flow.py`、タスクは `tests/test_worker_*.py`。

## 検証（必須）

修正範囲に応じて検証を回す。スキップ禁止。

```bash
# backend を触ったら
make lint-backend
make test-backend

# frontend を触ったら
make lint-frontend
make lint-frontend-messages
make test-frontend

# infra を触ったら
make infra-fmt-check
make infra-validate

# まとめて
make ci
```

- 認証 / ナビゲーション / 新規ルート / サイドバー / API フロー影響がある場合は E2E も回す:
  `nix develop --command bash -c "cd frontend && npm run test:e2e"`
- **追加した exploit テストが「修正前は落ち、修正後に通る」ことを確認する**（回帰防止として機能しているかの確認。可能なら修正を一時 revert して赤を見る、難しければレビューで論理を担保）。
- 依存更新をした場合は再度 audit を回し、CVE 解消を確認する。SHA 固定・pin 化をした場合は CI の audit ステップ（`.github/workflows/ci.yml`）が通る前提を崩していないか確認。
- sandbox が `~/.cache/nix/fetcher-locks/*.lock` で落ちる場合は `dangerouslyDisableSandbox: true` で再実行する（CLAUDE.md の既知の例外）。
- lint / test / audit に失敗したら、原因を直してから次へ。失敗を残したまま PR レポートを書かない。`--no-verify` で hook を skip しない。

## 成果物の出力先（必須）

実装と検証が完了したら、PR 用のサマリを必ずファイルへ書く。assistant メッセージに本文を貼らない。

- 保存先: `report/SEC_pr_<YYYYMMDD_HHMM>.md`
  - 例: `report/SEC_pr_20260530_1530.md`
  - `report/` が無ければ作成する (`mkdir -p report`)
  - タイムスタンプは **PR レポート書き出し時刻**（ローカル）。`date +%Y%m%d_%H%M`
- 既存 `SEC_pr_*.md` は履歴として残す。上書き禁止
- 採用元レポートのパスを冒頭に明記する

### ターミナルへの出力ルール

- 詳細はファイルにだけ書く
- ターミナルへ返すのは以下のみ:
  1. 採用レポートのパス
  2. PR レポートのパス（`report/SEC_pr_YYYYMMDD_HHMM.md`）
  3. `Summary` セクションの 3-5 行サマリ
  4. 検証結果（lint / test / audit の pass / fail）
  5. 残タスク・要ユーザー判断（rotate 必要など 1-2 行）

## PR レポートのフォーマット

下記テンプレートを `report/SEC_pr_<YYYYMMDD_HHMM>.md` に書き込む。

````markdown
# Security Fix PR Report

- 採用レポート: report/SEC_report_YYYYMMDD_HHMM.md
- 実装ブランチ: <git branch>
- 適用スコープ: <Critical のみ / Critical+High / 全部 など>

## Summary
- 何を直したかを 3-5 行で要約

## Applied Fixes
### Critical
- [path/to/file:line] 何を直したか。元レポートの Finding を引用。（違反ルール: security.md「§...」）

### High
- ...

### Medium
- ...

### Low
- ...

## Design-level Fixes
- [path:line] 直した設計穴（IDOR / SSRF / OAuth / マスアサインメント）。塞いだ攻撃シナリオ。対応する exploit テスト名。

## Dependency & Supply Chain
- CVE 更新: <package> <old> → <new>（解消した CVE）
- バージョン固定 / lockfile: pin / lockfile commit した箇所
- GitHub Actions SHA 固定: <対応した uses>
- 拒否した不審依存（typosquatting / confusion など）があれば記載

## Exploit Tests Added
- [tests/...::test_名] 守る仕様 / 期待結果（401 / 403 / 422 / 429 / 拒否）。修正前に赤・修正後に緑を確認したか。

## Secrets Remediation
- 除去したファイル / .gitignore 追加
- **rotate 要否**: 要 / 不要（要の場合、どのクレデンシャルを再発行すべきか。git 履歴除去はユーザー判断待ち）

## Skipped
- 採用しなかった指摘と理由（影響範囲が大きい / 後続 PR / 要仕様判断）

## Validation
- `make lint-backend`: pass / fail（fail なら抜粋）
- `make test-backend`: pass / fail
- `make lint-frontend` / `lint-frontend-messages` / `test-frontend`: pass / fail
- `make infra-validate`: pass / fail
- 追加 exploit テスト: 件数 / pass。修正前赤・修正後緑の確認: 済 / 未
- 依存 audit 再実行: 解消 / 残あり

## Follow-ups
- 次の PR で対応すべき項目
- 要ユーザー判断で保留にした項目（秘密情報の履歴除去 など）
````

## 進め方の流れ（チェックリスト）

1. 採用レポートを決定し、パスをユーザーへ提示
2. Findings 集計を提示し、`AskUserQuestion` で適用スコープを選ばせる
3. 採用項目を `TaskCreate` で 1 つずつ切る
4. 各タスクを `in_progress` にして実装、終わったら `completed`
5. 影響範囲に応じた lint / test / audit（または `make ci`）を回す
6. fail があれば直す。pass まで PR レポートを書かない
7. `report/SEC_pr_<YYYYMMDD_HHMM>.md` を書く
8. ターミナルにはパスとサマリだけ返す（rotate 等の要判断事項は明示）
