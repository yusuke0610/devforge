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

### D9. monorepo は recursive Trees API でサブツリー探索する（2026-06 改訂で追加）

当初 v1 は直下 manifest のみとし、monorepo 対応は延期していた（後述「代替案」参照）。実装を精読した結果、延期理由とした 3 コスト（full-tree 走査コスト / vendoring 除外 / 複数 manifest の主従重み付け）のうち 2 つは解消でき、安全に前倒しできると判断したため declare の探索範囲を拡張する。`backend/requirements.txt` や `web/package.json` のようにサブツリーへ分散する構成でも依存を拾えるようにする。

- **(a) 探索手段 = recursive Trees API（1 リポ 1 コール）**: `GET /repos/{owner}/{repo}/git/trees/{default_branch}?recursive=1` を 1 回呼び、`type == "blob"` かつ basename が既知 manifest 名集合（D7 の `MANIFEST_FILENAMES`）に一致するものだけを候補にする。直下 `contents` 1 回の置換であり探索 API コストは同オーダー。`default_branch` は既存の `RepoData` が保持。
- **(b) ノイズ除外 = パスセグメント除外リスト**: パスのいずれかのセグメントが除外集合（`node_modules` / `vendor` / `.venv` / `venv` / `site-packages` / `bower_components` / `third_party` / `testdata` / `dist` / `build` / `.git` 等）に該当したら捨てる。既知 manifest 名のみ fetch するため任意ファイルは取得せず、除外は取得済みツリーの in-memory フィルタで無コスト。将来は Linguist `vendor.yml` 流用も可。
- **(c) コストキャップ = 深さ + 件数で打ち切り**: manifest の深さ上限（例: 4 セグメント）と 1 リポあたり fetch 件数上限（例: 20）を設定値として持ち、**浅い順にソートして打ち切る**（D6 のサンプリング思想と整合）。これが「重くなる危険」の安全弁。
- **(d) truncated / 打ち切りは partial としてマークする**: 巨大リポで Trees API が `truncated: true` を返した場合、または件数キャップ（c）で打ち切った場合は、取得済み分（浅い側優先）を使い `logger.warning` を残す（1 リポの取りこぼしで連携全体を落とさないベストエフォート方針）。加えて、**その走査が網羅的でない（partial）ことを当該リポの evidence にマークして永続化**し、下流が「網羅スキャン」と「ベストエフォートの部分スキャン」を区別できるようにする（保持は細かく / D8。証跡の過信を防ぐ）。
- **(e) 主従重み付けはしない（keep-all）**: 複数 manifest を主従判定して集約せず、全 manifest を evidence として保持する（D1/D8「非可逆な切り捨てを入力時に行わない」に従い、畳み込み・重み付けは後段ビュー変換へ）。延期理由の 3 つ目（主従判定）はこれで回避する。
- **(f) manifest パスを証跡として永続化する**: 検出した相対パス（例: `backend/requirements.txt`）を evidence に保存する（`PackageDeclaration.source_path` → `EvidenceRecord` → `github_skill_evidence.manifest_path`）。対象は public リポ前提で相対パスは公開メタデータ（既存の `repo_url` と同等の性質）、raw code は D6 どおり破棄するため機密情報を持たない設計を崩さない。証跡性が「どのディレクトリの何で宣言したか」まで強化される。
- **(g) 対象は manifest 限定（infra の .tf は対象外）**: Terraform/HCL は package manifest ではなく language 層（Linguist → 表示名「Terraform」/ D3）で捕捉済みのため、本探索は D7 の Tier1 4 エコシステム（Go / Python / JS-TS / Rust。manifest ファイルは Python が 2 種のため計 5 ファイル）の manifest にのみ適用する。（ただし `.tf` から**インフラリソース**（プロバイダ／サービス）を抽出する検出軸は本 manifest 探索とは別物で、後述「将来課題: IaC からのインフラリソース検出」に記載する。）

実装で触る想定箇所（後続 PR）: `github/api_client.py`（`fetch_root_filenames` を `fetch_manifest_paths(..., default_branch)` に拡張し、truncated/打ち切りの有無も返す）/ `github_collector.py`（パス一覧反復・`source_path` 付与・partial フラグ伝播）/ `skills/types.py`（`PackageDeclaration.source_path` / `EvidenceRecord.manifest_path` / partial マーカー）/ `skills/aggregator.py`（path・partial 伝播）/ `models/skill.py` + 新規 migration（`github_skill_evidence.manifest_path` と partial フラグを `op.add_column`）/ `schemas/github_skill.py`（`SkillEvidence` への追加、`make codegen-types` 再生成）。

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
- **monorepo サブツリー（subtree）探索の v1 対応**: 当初は full tree 走査コスト / vendoring の除外 / 複数 manifest の主従重み付け、の 3 コスト（特に主従判定が本質的に厄介）を理由に v1 は直下 manifest のみとし延期した。→ 後に recursive Trees API（1 コール）+ パスセグメント除外 + 深さ/件数キャップ + keep-all（主従判定をしない）で解消できると判明し、2026-06 改訂で **D9 として採用**した（本ファイル「決定内容 D9」参照）。
- **dependency graph / SBOM API を起点にする**: 宣言 only 止まりで「宣言」と「実 import」の `signal_source` を区別できず、D1/D6 の思想と不整合。import 解析（C 案、D6）を採用する。
- **desktop 版で実装する**: desktop 固有価値（ローカルリポ直読み / PII ローカル完結 / ローカル LLM）は前提が消滅（PII はクラウドの非学習契約で吸収、LLM はクラウド上位モデルへ移行）。stack 推論は本 ADR の GitHub per-repo manifest 解析で代替する。`devforge-desktop` は塩漬けとして保持する。

## トレードオフ・既知のリスク

- **public 限定**: 主戦場が private なユーザーはスキルが過少評価される。v1 では受容し、将来 Layer 3（人間が深さを補完）で吸収する。
- **import 解析（C 案）の verify コスト**: 言語別 parser が必要で高コスト。サンプリング（D6）と direct 依存への絞り込み（D7）で緩和する。
- **Linguist の data 言語デフォルト除外**: SQL / YAML / GraphQL 等は Linguist がデフォルトで除外する。経歴書的に必要なものは補正する（D3）。
- **monorepo 探索の除外リスト / キャップはヒューリスティック（D9）**: 取りこぼし（cap 超過の深い manifest）や誤除外の可能性を受容する。閾値・除外集合は設定値として保持し運用で調整する。`manifest_path` 永続化はスキーマ拡張（`github_skill_evidence` への ADD COLUMN migration）を後続実装 PR で要する。

## 将来の移行条件

- **verify ステージの詳細設計**: import サンプリング戦略、言語別の import 検出、打ち切り条件。
- **monorepo 対応**: D9 で採用済み（recursive Trees API + パスセグメント除外 + 深さ/件数キャップ + keep-all）。残課題は除外定義の高度化（Linguist `vendor.yml` 流用）・キャップ閾値の実データチューニング・規模シグナルの導入。
- **IaC からのインフラリソース検出**: 後述「将来課題: IaC からのインフラリソース検出」を参照（Terraform/OpenTofu 先行・provider+service 粒度・kind=infra 案・D9 探索流用）。
- **private リポジトリの扱い**: Layer 3 経由で人間が深さを補完する。生データは持ち込まない前提を維持する。
- **deps.dev エンリッチ**: 横断名寄せの範囲・実行タイミング。
- **閾値・粒度のデフォルト**: 言語足切りの初期値、表示名 alias の初期セット。

## 将来課題: IaC からのインフラリソース検出（検討中 / 未採用）

**背景**: Terraform/HCL は Linguist により*言語*スキル「Terraform」として検出済み（D3・D9(g)）。一方「どのクラウドの何のサービスを IaC で構築・運用したか」は捉えられていない。インフラが **IaC で記述されている場合に限り**、宣言から具体的なインフラリソースを抽出すれば、インフラ系スキルの幅と証跡性が上がる。本項は新しい検出軸の**課題提起**であり、採用（実装）は別途判断する。

**スコープ（v1 課題時）**:

- 対象 IaC: まず **Terraform / OpenTofu（HCL `.tf`）** に限定。parser は **plugin 型**（D7 の `ManifestParser` と同思想）とし、CloudFormation(yaml/json) / Pulumi / k8s manifest / Helm / Serverless Framework は後追いで差し込める設計にとどめる（v1 では実装しない）。
- 抽出粒度: **プロバイダとサービスの両方**。
  - `provider` / `required_providers` ブロック → クラウドプロバイダ（AWS / Google Cloud / Cloudflare 等）。
  - `resource "<type>" "<name>"` ブロック → 具体サービス。type 接頭辞でプロバイダを判定（`aws_` → AWS）、type 自体がサービスを表す（`aws_s3_bucket` → S3）。

**3 層モデルへの収め方（案）**:

- Layer 1 に**新 kind `infra`**（`SKILL_KIND_INFRA`）を追加。`package` の「エコシステム内で一意」前提（D3）に乗らないため別 kind とする（D2 の「検出方法と信頼度の出方が違うなら別型」と同思想）。
- canonical は **raw な resource type / provider 名を保持**（例 `aws_s3_bucket`）。`aws_s3_bucket` → 「Amazon S3」のような**表示名・粒度の畳み込みは文脈依存で機械検証不能**なので、D8 同様 **agent 提案 → 人間確定**の human-in-the-loop に委ねる（機械に辞書を確定させない / D3・D8）。「保持は細かく、提案は荒目」を踏襲。
- Layer 2 Evidence に**新 signal_source `infra_declared`**を追加。量的シグナルは resource 出現回数・provider 宣言の有無。`github_skill_evidence.signal_source` は値域拡張のみ（カラム追加不要）。provider version 等の追加メタを持つ場合のみ ADD COLUMN migration を別途。

**既存基盤の流用**:

- **探索は D9 をそのまま流用**: `.tf` は `infra/modules/...` 等サブツリーに分散するのが常で、recursive Trees API + パスセグメント除外 + 深さ/件数キャップ + keep-all がそのまま効く。除外集合に `.terraform`（プロバイダキャッシュ）を追加する。manifest 探索とは別の対象集合（`*.tf`）として扱う。
- **証跡**: D9(f) と同様、検出した `.tf` の相対パスを evidence に保持。raw HCL は D6 同様 parse 後に破棄。

**ステージ**: declare 相当（宣言検出）に位置づく。`resource` ブロックは「宣言 ≒ 実構築」に近く、import 解析（verify / D6）のような昇格段階は基本不要。

**新規値オブジェクト（案）**: `InfraResourceDeclaration(tool, provider, resource_type, source_path)` を IaC parser plugin が返し、aggregator に `_collect_infra()` を追加して `kind=infra` で集約する（`_collect_languages` / `_collect_packages` と並ぶ）。

**触る想定箇所（将来実装時）**: `skills/types.py`（`SKILL_KIND_INFRA` / `InfraResourceDeclaration`）/ `skills/manifests/`（IaC parser plugin・Protocol 一般化 or `InfraParser` 別定義）/ 新規 `skills/manifests/terraform.py`（HCL の provider・resource 抽出）/ `skills/aggregator.py`（`_collect_infra`）/ `github_collector.py`（`.tf` 探索・除外集合に `.terraform` 追加）/ `models/skill.py`・`schemas/github_skill.py`（kind / signal_source の値域・docstring 更新、必要なら provider_version の ADD COLUMN migration + `make codegen-types`）。

**トレードオフ・リスク**:

- **IaC 限定の取りこぼし**: コンソール手動構築・他者管理基盤など IaC 化されていないインフラスキルは検出不能。public 限定（既知リスク）と同様、Layer 3 で人間が補完する。
- **HCL の動的生成**: `module` 呼び出し・`count` / `for_each` / `dynamic` で resource が動的に増える構成は静的列挙しきれない。v1 課題は**静的 `resource` ブロックの type 抽出**に限定し、module 解決は将来課題とする。
- **resource type → 表示名マッピングの維持コスト**: D3「辞書を持たない」思想とテンション。canonical を raw type 保持・表示名のみ human-in-the-loop 提案にすることで、機械辞書の常時メンテを避ける。横断名寄せが要る場合のみ Terraform Registry を参照し、D4 のホットパス非依存に合わせ内部マスタ化を検討する。

## 関連リンク

- ADR-0010（DevForge Agent / 制約の責務分離の元思想）/ ADR-0013（マルチプロバイダ LLM）/ ADR-0015（Vertex AI 経由）
- 既存実装（移行対象）: `backend/app/services/intelligence/`（`pipeline.py` / `skill_extractor.py` / `skill_taxonomy/{language_map,topic_map,keyword_map}.py` / `github/api_client.py`）
- リトライ基盤: `backend/app/services/tasks/exceptions.py`（`RetryableError` / `NonRetryableError` / `dead_letter`）
- [GitHub Linguist `languages.yml`](https://github.com/github-linguist/linguist/blob/main/lib/linguist/languages.yml)
- [GitHub REST API: Git Trees（`recursive`）](https://docs.github.com/en/rest/git/trees)
- [GitHub Linguist `vendor.yml`](https://github.com/github-linguist/linguist/blob/main/lib/linguist/vendor.yml)
- [deps.dev](https://deps.dev/)
- [Terraform Registry](https://registry.terraform.io/)（resource type ↔ provider/service 正規化の参照元 / 将来課題「IaC リソース検出」用）
- [OpenTofu](https://opentofu.org/)

## 改訂履歴

- **2026-06**: 当初「代替案」で延期していた monorepo サブツリー探索を **D9 として採用**（recursive Trees API + パスセグメント除外 + 深さ/件数キャップ + keep-all + manifest パス永続化）。3 層モデル・D1〜D8 は不変。当初は別 ADR 案だったが、0016 の核を維持する refine であり 1 箇所の追補に留まるため、本 ADR への統合とした。
- **2026-06**: IaC からのインフラリソース検出（provider+service 粒度・HCL 先行・kind=infra 案・D9 探索流用・D8 同様の human-in-the-loop 正規化）を**将来課題として追記**。決定（D1〜D9）・3 層モデルは不変。
