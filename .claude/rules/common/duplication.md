# コード重複 / DRY ポリシー（共通）

このルールは backend / frontend / infra すべての領域に適用される。
領域別のコーディング規約（`.claude/rules/{backend,frontend,infra}/`）と併せて参照すること。

## 原則

### Rule of Three

- **1 回目**: そのまま書く
- **2 回目**: 重複を認識する（まだ抽象化しない）
- **3 回目**: 抽出する。共通化先は下記「抽出先ヒエラルキー」に従う

2 回目で先回り抽象化すると、想定外の差分が出た時に逆に複雑化する。3 つ目の利用箇所が現れた時点で、共通点と差分が明確になっているはずなので、そこで初めて抽出する。

### 過剰な抽象化を避ける

CLAUDE.md にある通り「PEP8 を守るな、PEP8 を理解した上で抽象化しろ」。重複検知 (jscpd) のレポートに引っかかったからといって、機械的に DRY 化してはいけない。「同じ形をしているが意味が違う」コードは別物として残すべき。

判断基準:

- **形は同じだが変更理由が違う** → 抽出しない（偶発的重複）
- **形は違うが変更理由が同じ** → 抽出する（本質的重複）

## 禁止される重複（本質的重複）

以下が複数箇所に書かれていたら、原則として抽出対象とする。

- **ドメインロジック**: スコア計算 / 正規化 / バリデーション / 状態遷移
- **エラーマッピング**: バックエンドのエラーコード ↔ ユーザー向けメッセージの対応表
- **API パス文字列**: `/api/v1/...` のリテラルが複数モジュールに散在
- **環境変数名のリテラル**: `os.environ["TURSO_DATABASE_URL"]` のような文字列を `settings.py` 以外で参照
- **DTO / 型定義**: backend `app/schemas/` ↔ frontend `src/types.ts` の二重定義（同じフィールド構造を別言語で持つこと自体は許容、ただし片方の変更がもう片方の更新を忘れさせるなら検知できる仕組みが必要）

## 許容される類似（偶発的重複）

機械検出 (jscpd) で重複として検出されても、抽出してはいけないもの。

- **pytest fixture の最小スキャフォールド**: テスト個別の準備コード（`db_session` 等の共通 fixture と区別）
- **Pydantic schema の field 列**: 似た形のレスポンス schema を 1 つにまとめると変更理由が混ざる
- **`infra/environments/{dev,stg,prod}/terraform.tfvars` の同名キー**: 値が環境別なので冗長ではない
- **テストの arrange-act-assert ブロック**: 「同じ流れ」は読みやすさのために残す
- **JSDoc / docstring のテンプレート文言**: 「### Args」「### Returns」等のセクション見出し
- **import 文の塊**: 同じライブラリ群を多くのモジュールが import すること自体

## 抽出先ヒエラルキー

重複を抽出すると決めたら、以下の順で配置先を決める。

### Backend (FastAPI)

1. **同一サブパッケージ内の純粋関数** → 同じディレクトリの `_utils.py` か `_helpers.py`
2. **ドメイン横断のロジック** → `backend/app/services/shared/`
3. **永続化に関する重複** → `backend/app/repositories/base.py` の共通メソッド
4. **HTTP 入出力の変換** → `backend/app/routers/<scope>/_responses.py`
5. **モデル / DTO** → `backend/app/schemas/shared.py`

参考: 既存の `backend/app/services/shared/sort_utils.py` がドメイン横断 util の配置例。

### Frontend (React + TypeScript)

1. **状態管理を含む共通ロジック** → `frontend/src/hooks/` の新規フック（`useDocumentForm`, `useTaskPolling` パターン）
2. **純粋関数 / 文字列変換 / 日付処理** → `frontend/src/utils/`
3. **API クライアントの共通パターン** → `frontend/src/api/client.ts` のラッパー追加
4. **フォーム入出力変換** → `frontend/src/formMappers.ts` / `frontend/src/payloadBuilders.ts`
5. **共通 UI コンポーネント** → `frontend/src/components/ui/`（ErrorToast, Skeleton 等の配置例）
6. **型定義** → `frontend/src/types.ts` / `frontend/src/formTypes.ts`

### Infra (OpenTofu)

1. **2 環境以上で同じ resource block** → `infra/modules/` に切り出し、各 environment から呼ぶ
2. **環境別の値だけが違う構成** → モジュール側を `variable` 化、`environments/<env>/main.tf` で値を渡す
3. **モジュール内部の重複** → サブモジュール化は慎重に（HCL のサブモジュール深掘りは可読性を下げる）

参考: `infra/modules/cloud_run/` `artifact_registry/` `cloud_tasks/` `cloudflare/` `monitoring/` `service_account/` が既存モジュール例。

### 領域横断 (BE ↔ FE ↔ infra)

1. **エラーコード**: backend の `app/core/errors.py` を Single Source of Truth とし、frontend の `utils/appError.ts` は OpenAPI 経由で同期できないか検討する
2. **環境変数名**: backend の `app/core/settings.py` で定義したフィールド名を、infra 側 (`infra/modules/cloud_run/main.tf` の `env` ブロック) と CI (`.github/workflows/ci.yml`) で参照する。リテラル文字列のコピペは避ける
3. **手順書 / README / docs**: 重複しがちな手順は `docs/` に正本を置き、README からはリンクで参照する

## 検知の運用

### 機械検出 (jscpd)

`make dupe-check` で `report/dupe/jscpd-report.json` を生成する。Phase 1 は warn-only（CI 落とさない）。
PR 前に 1 度走らせて、新規重複が増えていないか確認する。

しきい値 (`.jscpd.json`):

- `minTokens: 50` / `minLines: 5` — これ未満の小片は無視
- `threshold: 0` — Phase 1 は fail させない（baseline 確定後に引き上げ）

### symlink 採用に伴う計測の前提（infra）

`infra/environments/{dev,stg,prod}/{variables,moved,outputs}.tf` は `../shared/<file>.tf` への symlink で 1 ファイルに物理統合してある。jscpd は symlink 経由で同一ファイルを 3 回スキャンすると 100% 重複として誤検出するため、`.jscpd.json` の `ignore` で 9 件（3 環境 × 3 ファイル）を明示除外している。

そのため `make dupe-check` の HCL 重複率は「真の重複ゼロ」ではなく「symlink 除外後の重複ゼロ」を意味する。`infra/environments/shared/` 配下の正本だけがスキャン対象になっている前提で読むこと。新規に環境別 symlink を増やす場合は同様に `.jscpd.json` に追記する。

### AI レビュー (refacter skill)

- 領域内: `BE_refacter` / `FE_refacter` / `INFRA_refacter`
- 領域横断: `XR_refacter`

各 skill は `report/dupe/jscpd-*.json` を読み込んでから、「形だけ似ているのか / 本質的に重複しているのか」を判定する。
本ルールの「禁止される重複」「許容される類似」を基準に分類する。

### Stop hook (`.claude/settings.local.json`)

Claude Code のセッション終了時に `make dupe-check` を background 実行する設定が入っている場合、
次のセッションで `report/dupe/jscpd-report.json` を最初に読むこと。古い情報を引きずらないように。
