# レビュー観点（共通）

差分レビューで当てる観点の**正本**。`.claude/skills/RV/SKILL.md`（実装後レビューループ）がこのファイルを読んで差分に当てる。
PR 後の CodeRabbit 指摘対応・手動レビュー・`/code-review` の結果を読むときも同じ観点で判断する。

**このファイルは育てるもの。** RV や PR レビューで新しい種類の指摘が出たら、直したコードだけで終わらせず、**該当カテゴリに 1 行追記する**（同じ手戻りを次回は観点として先に当てるため）。追記のルールは末尾の「観点の追記」を参照。

## 重大度

| 重大度 | 定義 | 扱い |
|---|---|---|
| **High** | バグ・契約違反・SSoT 破綻・CI が落ちる。マージ前に必須 | 自動修正する |
| **Medium** | 直すべきだが即座に壊れはしない（ルール違反・テスト不足・可読性の実害） | 自動修正する |
| **Low** | 好みの範囲・将来の改善余地 | 記録のみ。直さない |

**重大度によらず自動修正しないもの**（レポートに記録してユーザー判断を仰ぐ）:

- **設計判断を伴う指摘**: 実装方針が複数あって選択が要る / API・型契約の変更 / 挙動変更
- **差分範囲を逸脱する指摘**: 直すのに今回の依頼範囲外を触る必要がある

## 観点

差分の行と、その行が依存・被依存する範囲だけを見る。差分に出てこないファイルの粗探しはしない（リポジトリ全体の棚卸しは `*_refacter` 系 skill の担当）。

### 正しさ

- 境界値（0 / 空配列 / 最大値 / off-by-one）
- `None` / `undefined` / 空文字の扱い、Optional の unwrap
- 例外パス: 失敗時に何が起きるか、リソースが解放されるか
- 非同期の競合: await 漏れ、順序依存、並行更新
- 変更した条件分岐の反転・取りこぼし

### 契約

- API / 型 / スキーマの後方互換（レスポンスのフィールド削除・必須化・型変更）
- 層境界（`.claude/rules/backend/layers.md`）: router がドメイン判断や永続化を持っていないか、ORM model に表示ロジックが漏れていないか
- タスクハンドラが黙って `return` していないか（`.claude/rules/backend/architecture.md`）
- service 層が `HTTPException` を持ち込んでいないか

### SSoT

- codegen 生成物の再生成漏れ: `app/schemas/` / `app/routers/`（**docstring の変更を含む**）を触ったのに `web/src/api/generated.ts` に差分が無い
- `backend/pyproject.toml` の依存を変えたのに `backend/uv.lock` が未更新
- 新規環境変数の 4 箇所同期（`backend/app/core/env_keys.py` のコメント手順）
- ADR の新規作成・ステータス変更に対する `docs/adr/README.md` 索引の更新漏れ
- **手順・フローを変えたら、それを記述している他の docs / rules も同じ差分で更新する**（RV 導入時に `rules/common/tdd.md` の「`make ci` → stage」と CLAUDE.md のモデル切り替えタイミングが drift した実例）
- docs / rules に書いてある事実と差分の実装が矛盾していないか
- **設定値を直したら、同じ値に言及している同一ファイル内の他の行も突合する**（手順書は表・チェックリスト・本文で同じ値を繰り返しがち。ENV_CHECKLIST の表だけ直して手順の行が古いままだった実例。PR #571 で CodeRabbit が検出）

### ルール違反

- 例外の握りつぶし（`except X: pass`、ログ無しの `catch {}`）— `.claude/rules/backend/python.md`
- web のユーザー向けメッセージ直書き — `.claude/rules/web/messages.md`
- テストで DB をモックしている — `.claude/rules/backend/test.md`
- `os.getenv("XXX")` の文字列リテラル直接参照 — `.claude/rules/security.md`
- 秘密情報のログ出力・`dangerouslySetInnerHTML` の新規使用 — `.claude/rules/security.md`

### テスト随伴

- TDD 対象（backend: `[tool.mutmut] only_mutate` / web: `stryker.conf.json` の `mutate`）の実装変更にテスト差分が伴っているか（`make lint-tdd` が CI で検知する）
- 変更した分岐が既存テストで踏まれるか（踏まれないなら「テスト不足」として起票）
- 契約を変えたのに既存 assert が古い期待値のまま残っていないか
- 新規エンドポイントに ハッピーパス + 認可失敗 + 不正入力 の 3 ケースがあるか（`.claude/rules/backend/test.md` の OK 基準）

## 観点の追記

RV / PR レビューで**既存の観点に無い**指摘が出たら、その場で本ファイルに追記する。

- **1 指摘 1 行**。該当カテゴリの箇条書きに足す（カテゴリが無ければ新設する）
- **由来を括弧で残す**（「〜した実例」「PR #568 で発覚」など）。なぜその観点があるのかが後から辿れるようにする
- **領域固有の詳細はここに書かない**。1 行の観点だけ置き、詳細は `.claude/rules/{backend,web,infra}/*.md` 側に書いてリンクする
- 既存の観点で拾えた指摘は追記しない（観点の重複はレビューのノイズになる）
- 機械検証できる形（lint / CI ジョブ）に落とせる観点は、追記と併せてスクリプト化を検討する（`scripts/lint-*.sh` の系統）
