# ADR-0021: backend Python 環境の Nix フルマネージド化（.venv 廃止）

## ステータス

Proposed

## 関連 ADR

- Supersedes: なし
- Superseded by: なし
- 関連:
  - ADR-0017（ミューテーションテスト）: 「backend は uv 管理でなく `requirements.txt` を lockfile とする」という現状の前提を明記している。本 ADR はその前提を更新する（Accepted 昇格時に 0017 の該当記述を追従させる）。
  - ADR-0014（Renovate による依存更新の自動化）: 依存の完全固定 + Renovate 自動追従。対象 6 manager のうち pip(requirements) を uv/nix 系へ置き換えるため、Renovate 設定に影響する。
  - ADR-0007（OpenAPI → TypeScript codegen）: 「開発ツールはすべて Nix devshell 経由」というラップ規約の出典。本 ADR はその devshell を Python パッケージ本体まで拡張する。

## コンテキスト

発端は VS Code の `.vscode/settings.json` が `backend/.venv/bin/python` を**絶対パスでハードコード**していたこと。このハードコード依存を根本から解消する策として、「Python パッケージ本体まで Nix（`flake.nix`）で管理し `.venv` を廃止する」方向を検討する。

調査で判明した現状:

- backend の Python 環境は既に **3 経路**に分岐している。
  - **ローカル開発**: Nix devshell（`python313` + `uv`）→ `uv` が `backend/.venv` に `requirements.txt` を導入
  - **CI（`.github/workflows/test.yml`）**: **uv 単体（Nix 非経由）**。`uv pip install -r requirements.txt`
  - **本番 Docker（`backend/Dockerfile`）**: **plain pip**。`pip wheel` → `pip install --no-index --find-links=/wheels`（Nix も uv も使わない）
- 3 経路とも依存の SSoT は **手書きの `backend/requirements.txt`**（`==` 完全固定 + CVE 対策のピン留めコメント付き）。`pyproject.toml` には `[project]` / `dependencies` セクションが**無く**、`uv.lock` も**存在しない**。つまり uv は「Python ランナー」として使われているだけで、依存解決のロックには使っていない。
- 本番と開発の実行パス乖離は、`test.yml` の `smoke-backend` ジョブ（本番イメージを実際に build → libSQL 起動 → `/health` が 200 を返すか検証）で担保している。過去に Python 3.14 bump で libsql が起動時 segfault した事象を、このジョブが検知した実績がある。
- **uv2nix は `pyproject.toml` の `[project.dependencies]` + `uv.lock` を前提とする**ため、現構成にそのままは適用できない。フル Nix 化には、前段で依存管理方式そのものの作り替えが必須。

補足として、DevForge の Nix devshell は専用 ADR で明文化されていない**暗黙の基盤選択**（`flake.nix` と `.claude/CLAUDE.md` の「開発ツールはすべて Nix devshell 経由」で規定）である。本 ADR は、その暗黙基盤を初めて ADR として明文化し、Python パッケージ本体まで適用範囲を拡張する性格を持つ。

これは「既存スタック（依存管理方式）の変更」かつ「開発 / CI / 本番のツールチェーン移行」であり、CONTRIBUTING.md の ADR 運用ルール上、実装着手前に ADR を起票する対象に該当する。

## 決定内容

**backend の Python パッケージ本体を Nix（flake）で build・管理する正本とし、`backend/.venv` を廃止する。** ただし影響範囲が広く未確定リスクが残るため、**段階移行（Phase 0〜3）**として定義し、各 Phase を独立に green 確認してから次へ進む（Phase 単位でロールバック可能）。

- **Phase 0 — 依存管理の作り替え（前提整備）**
  - `backend/requirements.txt` を `pyproject.toml` の `[project.dependencies]` へ移行し、`uv lock` で `uv.lock` を生成する。
  - `==` 完全固定と CVE 対策のピン留め根拠コメントは、`pyproject` 側へ移設して保持する（P7 の固定運用を落とさない）。
  - この段階では 3 経路の挙動は変えず、SSoT を requirements.txt → pyproject + uv.lock に差し替えるのみ（uv2nix 適用の前提を満たす）。
- **Phase 1 — devShell の Nix build 化（`.venv` 廃止）**
  - `flake.nix` に uv2nix を導入し、devShell の Python 環境を Nix build で構成する。`backend/.venv` を廃止する。
  - VS Code は direnv（`.envrc` の `use flake`。導入済み）経由で Python を解決させ、`python.defaultInterpreterPath` の `.venv` 絶対パス直書きを撤廃する（本 ADR の発端の解消）。
  - `Makefile` の `.venv/bin/python` 参照（10 箇所以上）を Nix 提供の Python 呼び出しへ置換する。
- **Phase 2 — CI の経路一致**
  - `.github/workflows/test.yml` を uv 単体 → Nix build へ寄せ、dev と CI のビルド経路を一致させる（過渡期の dev/CI 乖離を解消）。
- **Phase 3 — 本番 Docker と smoke の追従**
  - `backend/Dockerfile` を pip → Nix build 化し、`smoke-backend` ジョブを新ビルド経路前提に再設計する。本番パリティの担保方法を新経路に合わせて維持する。

## 代替案

- **方向A（`.venv` 維持 + direnv でハードコードのみ解消）**: `mkhl.direnv` 拡張で VS Code に devshell 環境を読み込ませ、`.venv` 絶対パス直書きだけを撤廃する。低リスク・小変更で「ハードコード解消」は達成できるが、`.venv` 自体は uv が作り続けるため「`.venv` を物理的に無くす」ゴールは満たさない。→ ゴール不一致で非採用（ただし Phase 1 が破綻した場合の後退先として「将来の移行条件」に残す）。
- **poetry2nix**: Nix で Python パッケージを build する別系統。poetry（`pyproject` の `[tool.poetry]` + `poetry.lock`）を前提とするため、Phase 0 の移行先が uv.lock ではなく poetry.lock になる。DevForge は既に uv を devshell に採用済みで、uv2nix の方が既存ツールとの連続性が高いため非採用。
- **現状維持**: 3 経路とも requirements.txt で揃っており本番パリティも担保できているが、`.venv` の絶対パス依存（本 ADR の発端）と、Python 3.13 の複数箇所への手動複製が残る。→ 発端の課題が解消しないため却下。

## トレードオフ・既知のリスク

- **過渡期の乖離**: Phase 1 完了時点では dev だけが Nix build、CI（uv）と本番（pip）は旧経路のままとなり、一時的に 3 経路が乖離する。Phase 2・3 完了までは本番パリティの検証を `smoke-backend`（旧経路）に依存し続ける必要がある。
- **uv2nix のビルドコスト**: Nix build は初回・キャッシュミス時のビルド時間が uv pip install より長くなりうる。macOS / Linux（開発機 / CI / 本番）でのビルド差・キャッシュ戦略の検証が要る。
- **smoke-backend 再設計コスト**: 本番イメージのビルド方式が変わるため、`smoke-backend` の前提（`docker compose up --build` → libSQL 起動 → `/health`）を作り直す必要がある。ここは本番障害検知の最後の砦なので慎重な移行が要る。
- **他 ADR への波及**: Accepted 昇格時に ADR-0017 の「backend は uv 非管理・requirements.txt が lockfile」記述の更新、ADR-0014 の Renovate 対象 manager 構成（pip → uv/nix）の見直しが連動する。
- **可逆性の担保**: 各 Phase を独立に検証・ロールバックできるよう小さく刻む。破綻時は方向A（direnv のみ）へ後退する。

## 将来の移行条件

- **後退条件**: uv2nix の Nix build 維持コスト（ビルド時間・キャッシュ運用・macOS 差）が開発体験を損なうと判断された場合、または uv2nix が upstream で破綻した場合は、Phase 1 を巻き戻し **方向A（`.venv` 維持 + direnv でハードコードのみ解消）** へ後退する。
- **段階停止**: Phase 0〜3 は独立して止められる。Phase 0（pyproject + uv.lock 化）だけでも「依存管理を uv 標準へ寄せる」独立価値があり、Phase 1 以降に進まない判断も許容する。
- **昇格条件**: Phase 1〜3 が実装で検証され、本番パリティ（smoke 相当）が新経路で担保できた時点で本 ADR を Accepted へ昇格し、ADR-0017 / ADR-0014 の関連記述を追従させる。

## 設計原則との関係

- **P7（依存は固定し、追従は自動化する）— 中心軸**: lockfile を `requirements.txt` から `uv.lock` + `flake.lock` へ一元化し、完全固定運用を維持したまま Nix / uv 標準のロック機構へ寄せる。ピン留めの根拠は pyproject へ移設して保持する。
- **P3（正本を定め、規律は機械検証で守る）— 副次**: 現状 Python 3.13 が `Dockerfile`（digest ピンの事実上の正本）/ `flake.nix` / `test.yml` / `pyproject [tool.pyright]` に**手動複製**されている。Nix を Python 環境の正本に集約することで、この複製を機械検証可能な単一定義へ寄せる余地を作る。
- **P6（可逆性を設計する）— 副次**: `.venv` と Nix build を併存させて残さず、Phase 単位で撤去・ロールバックできる形にする。後退先（方向A）を先に明記する。

## 関連リンク

- 対象ファイル: `flake.nix` / `backend/Dockerfile` / `.github/workflows/test.yml` / `backend/pyproject.toml` / `backend/requirements.txt` / `Makefile`
- Nix devshell 原則: `.claude/CLAUDE.md`（「開発ツールはすべて Nix devshell 経由で実行する」）
- 本番パリティ検証: `.github/workflows/test.yml` の `smoke-backend` ジョブ
- uv2nix: https://github.com/pyproject-nix/uv2nix
- 関連 ADR: [ADR-0017](./0017-mutation-testing-and-slack-notifications.md) / [ADR-0014](./0014-renovate-dependency-automation.md) / [ADR-0007](./0007-openapi-typescript-codegen.md)
