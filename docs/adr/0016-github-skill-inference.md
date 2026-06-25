# ADR-0016: GitHub 連携によるスキル推論基盤

## ステータス

Accepted

（既存の決定論パイプライン `backend/app/services/intelligence/`（`skill_extractor.py` + `skill_taxonomy/` の自前辞書）を、本基盤へ段階移行する。機械と人間の責務分離は ADR-0010 の「制約の責務分離」と同一思想を踏襲する。）

## コンテキスト

DevForge には既に GitHub からスキルを推論する決定論的パイプラインがある（`intelligence/pipeline.py` → `skill_extractor.py`、LLM は呼ばない）。現状は **自前の技術タグ辞書**でスキル名へ写像している:

- `skill_taxonomy/language_map.py`（`LANGUAGE_TO_SKILL`）
- `skill_taxonomy/topic_map.py`（`TOPIC_TO_SKILLS`）
- `skill_taxonomy/keyword_map.py`（`DESCRIPTION_KEYWORDS`）

この方式には次の課題がある:

- **辞書のメンテナンスコスト**: 言語・トピック・説明文キーワードの対応表を人手で維持し続ける必要がある。
- **シグナルが弱い**: リポジトリ言語（byte 比率）・GitHub topics・description のキーワードマッチ止まりで、「実際に何のライブラリ・フレームワークを使ったか」を捉えられない。
- **証跡性が立てにくい**: 経歴書に載せる GitHub URL と、推論したスキルの裏付けの対応が曖昧になりやすい。

また、推論結果には「機械が客観的に検出できるもの（幅）」と「人間にしか書けないもの（深さ：習熟度・文脈・成果規模）」が混在しており、両者を同じ層で扱うと、機械の更新が人間の記述を壊す/人間の主観が機械的シグナルを汚染する、という双方向の事故が起きる。

前提として **本基盤は public リポジトリを対象**とする（private は v1 では扱わず、後述の Layer 3 経由で人間が深さを補完する）。

## 決定内容

### D1. スキルを 3 層に分離する

スキルを責務の異なる 3 層に分け、各層を埋める主体を固定する。

| 層 | 内容 | 埋める主体 |
|---|---|---|
| **Layer 1 Skill** | 正規化エンティティ。技術そのもの。`LanguageSkill` / `PackageSkill` に型分割（D2） | 機械（正規化ソースに resolve） |
| **Layer 2 Evidence** | 技術 × 根拠リポの N:N。`signal_source` / `confidence` / 量的シグナル（byte 数・出現回数等）を持つ | 機械が埋める |
| **Layer 3 Proficiency / Narrative** | 深さ・文脈。自己評価レベル / 本文 narrative / 期間・規模 | 人間 or agent 生成 → 人間レビューが確定 |

原則: **機械は「幅」（Layer 1-2）、人間は「深さ」（Layer 3）を埋める**。機械が客観検出できるものと人間にしか書けないものを層で分離することで、双方の更新が干渉しない。ADR-0010 の「機械検証可能な制約はコード、機械検証不能な制約はプロンプト」という責務分離と同一思想である。

### D2. LanguageSkill と PackageSkill を別型にする

Layer 1 を単一型にせず、`LanguageSkill` と `PackageSkill` に型分割する。検出方法と信頼度の出方が本質的に異なるためである。

- **LanguageSkill**: GitHub Linguist による byte 比率で検出。信頼度は「どれだけ書いたか」の量的シグナル。
- **PackageSkill**: manifest の宣言 + import の有無で検出。信頼度は「宣言したか」と「実際に import したか」の二段で出る。

同型に押し込めると、片方にしか存在しないシグナル（byte 数 / `dependency_kind` 等）の置き場所がなくなるため、別型とする。

### D3. 正規化ソースを役割ごとに外部へ委譲する

スキル名の正規化に自前辞書を持たず、役割ごとに既存の正規ソースへ委譲する。

- **言語**: GitHub Linguist の `languages.yml` を正本とする。`aliases` を Layer 1 の alias、`group` を parent へ流用する。data 言語のデフォルト除外だけは経歴書向けに補正する（後述トレードオフ）。
- **ライブラリ**: manifest の package ID が**エコシステム内で一意 = canonical**。したがって**辞書による正規化は不要**。エコシステムを跨いだ名寄せが必要な場合のみ deps.dev を参照する。
- **表示名・粒度の畳み込み**（例: `@aws-sdk/client-eventbridge` → 「Amazon EventBridge」）: 文脈依存で**機械検証不能**。package ID を入力に agent が提案し、人間が確定する（D8）。

### D4. 辞書とマッピング結果を分離し、連携フローから外部依存を排除する

正規化ソース（辞書）の取得と、それを使ったマッピング結果を分離し、GitHub 連携のホットパスに外部依存を持ち込まない。

- **LanguageSkill**: `languages.yml` はビルド時 / 定期バッチで内部マスタ化する。連携時は外部を叩かず**内部マスタへ resolve するだけ**。resolve 結果は保持する。
- **PackageSkill**: 辞書概念が不要（ID が正規）。連携時に外部解決を要しない。

これにより連携ホットパスの速度・信頼性が安定し、GitHub / 外部サービスのレート消費も増やさない。

### D5. ステージを discover / declare / verify に分ける

スキル推論を段階設計とし、安価で確実なものを先に、高コストで精度を上げるものを後追いにする。

- **discover**: `/languages`（Linguist の byte 比率）を他ステージと並列で安価取得する。
- **declare**: manifest をパースし、宣言された依存を取得する（D7）。
- **verify**: import 解析で「宣言」を「実使用」へ昇格させる（D6）。

**declare までで経歴書は出力可能**であり、verify は精度を後追いで上げる位置づけ。verify が未完でも基盤は機能する。

### D6. verify は import 解析（C 案）で行う

宣言依存（declare）のうち **direct 依存に絞って import 解析**し、実際に import されているものを `signal_source = 実使用` へ昇格させる。

- 生コードは fetch → parse → **破棄**（永続化しない）。
- 全量走査せず**サンプリングで打ち切る**（verify コスト抑制、後述トレードオフ）。

依存グラフ / SBOM API 起点ではなく import 解析を選ぶ理由は「代替案」を参照。

### D7. declare のスコープと出力契約

- **対応エコシステム**:
  - Tier1（v1 必須）: Go（`go.mod`）/ Python（`pyproject.toml`, `requirements.txt`）/ JS-TS（`package.json`）/ Rust（`Cargo.toml`）
  - Tier2（後追い）: Java-Kotlin / Ruby / PHP
  - 上記以外は対象外
- **parser は plugin 型**: `ManifestParser`（入力 = ファイル内容、出力 = `[]PackageDeclaration`）。v1 では Tier1 のみ実装し、後から差し込めるようにする。
- **出力に `dependency_kind`（direct / dev / indirect / peer / build）を保持する**:
  - `go.mod` の `// indirect` は除外する。
  - `package.json` の `devDependencies` は実績スキルに混ぜない。
  - verify の絞り込み入力 + 経歴書提案の重み付けの素になる。**捨てると復元不能**なため、入力段では落とさず保持する。

### D8. 非決定性を human-in-the-loop で封じ込める

機械検証不能な判断（粒度・足切り）は機械に確定させず、提案に留めて人間が確定する。

- **粒度の畳み込み**: agent が提案し、人間が確定する。確定後は固定。
- **言語の足切り**（上位 N 位 / X% 以上）: デフォルト値を設定として保持し、agent は例外提案のみ行う。
- **原則「保持は細かく、提案は荒目」**: 検出データは全量保持し、畳み込み・絞り込みは後段のビュー変換として行う。**非可逆な切り捨てを入力時に行わない**。

### この設計で得られるもの

- エビデンス系スキルに裏付けが付き、経歴書の GitHub URL との整合（証跡性）が立つ。
- 自前の技術タグ辞書（`skill_taxonomy/`）のメンテが不要になる（言語 = Linguist、package = エコシステム ID）。
- 連携ホットパスに外部依存が無く、速度・信頼性・レート消費が安定する（D4）。
- declare までで出力でき、verify で段階的に精度を上げられる（D5）。
- 既存のリトライ基盤（`backend/app/services/tasks/exceptions.py`）を流用できる:
  - GitHub rate limit（403 / 429）= `RetryableError`（`Retry-After` / reset 時刻まで待機）
  - リポジトリ削除 / private 化 = `NonRetryableError`（即 `dead_letter` 終端）

## 代替案

- **package 正規化の自前辞書を持つ**: package ID がエコシステム内で一意のため不要。辞書メンテのコストだけが残るので却下。
- **monorepo サブツリー（subtree）探索の v1 対応**: full tree 走査コスト / vendoring の除外 / 複数 manifest の主従重み付け、の 3 コストを生む（特に主従判定が本質的に厄介）。v1 は直下 manifest のみとし延期する。
- **dependency graph / SBOM API を起点にする**: 宣言 only 止まりで「宣言」と「実 import」の `signal_source` を区別できず、D1/D6 の思想と不整合。import 解析（C 案、D6）を採用する。
- **desktop 版で実装する**: desktop 固有価値（ローカルリポ直読み / PII ローカル完結 / ローカル LLM）は前提が消滅（PII はクラウドの非学習契約で吸収、LLM はクラウド上位モデルへ移行）。stack 推論は本 ADR の GitHub per-repo manifest 解析で代替する。`devforge-desktop` は塩漬けとして保持する。

## トレードオフ・既知のリスク

- **public 限定**: 主戦場が private なユーザーはスキルが過少評価される。v1 では受容し、将来 Layer 3（人間が深さを補完）で吸収する。
- **import 解析（C 案）の verify コスト**: 言語別 parser が必要で高コスト。サンプリング（D6）と direct 依存への絞り込み（D7）で緩和する。
- **Linguist の data 言語デフォルト除外**: SQL / YAML / GraphQL 等は Linguist がデフォルトで除外する。経歴書的に必要なものは補正する（D3）。

## 将来の移行条件

- **verify ステージの詳細設計**: import サンプリング戦略、言語別の import 検出、打ち切り条件。
- **monorepo 対応**: Trees API + Linguist の除外定義流用、ファイル位置・規模シグナル、複数 manifest の主従重み付け。
- **private リポジトリの扱い**: Layer 3 経由で人間が深さを補完する。生データは持ち込まない前提を維持する。
- **deps.dev エンリッチ**: 横断名寄せの範囲・実行タイミング。
- **閾値・粒度のデフォルト**: 言語足切りの初期値、表示名 alias の初期セット。

## 関連リンク

- ADR-0010（DevForge Agent / 制約の責務分離の元思想）/ ADR-0013（マルチプロバイダ LLM）/ ADR-0015（Vertex AI 経由）
- 既存実装（移行対象）: `backend/app/services/intelligence/`（`pipeline.py` / `skill_extractor.py` / `skill_taxonomy/{language_map,topic_map,keyword_map}.py` / `github/api_client.py`）
- リトライ基盤: `backend/app/services/tasks/exceptions.py`（`RetryableError` / `NonRetryableError` / `dead_letter`）
- [GitHub Linguist `languages.yml`](https://github.com/github-linguist/linguist/blob/main/lib/linguist/languages.yml)
- [deps.dev](https://deps.dev/)
