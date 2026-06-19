# ADR-0014: Renovate による依存更新の自動化

## ステータス

Accepted

## コンテキスト

DevForge は依存をすべて「固定」運用している。GitHub Actions は SHA(digest) ピン留め
（`uses: actions/checkout@34e1148... # v4`）、Python は `backend/requirements.txt` で
`==` 完全固定、infra プロバイダは `~>` 制約 + `.terraform.lock.hcl`、Nix は `flake.lock`
で固定している。これはサプライチェーン攻撃（レンジ内 yank / 侵害バージョンの混入）に
対して安全な一方で、**固定したバージョンを追従する仕組みが無い**という弱点があった。

- 古いバージョンに固定され続け、機能改善・バグ修正・非互換のないセキュリティ修正を取り
  こぼす。
- CVE 対応が CI の pip-audit による検知頼みで、後追いになる。
- 追従が手作業のため、更新が後回しになりがちで、いざ上げる時の差分が大きくなる。

Dependabot / Renovate のいずれも未導入だったため、依存更新を自動で提案する仕組みを
入れることにした。

## 決定内容

**Renovate（Mend hosted GitHub App）を導入する。** 固定運用は維持したまま、更新の
「提案（PR 起票）」だけを自動化する。

- 設定の正本は `.github/renovate.json5`（コメントを日本語で残すため JSON5）。
- 対象エコシステム: github-actions / pip(requirements) / npm / terraform /
  docker・docker-compose / nix の 6 種。
- 固定方式は維持する:
  - github-actions は `pinDigests: true` で digest 固定 + `# v4` コメントを継続。
  - pip は `rangeStrategy: "pin"` で `==` 固定を維持。
  - docker は `docker:pinDigests` で digest 固定。
  - nix は `flake.lock` の locked input を追従。
- `vulnerabilityAlerts` を優先起票し、pip-audit の後追いを Renovate の先回りで補強する。
- すべての更新は Dependency Dashboard（Issue）で一覧管理する。
- **自動マージは行わない。** 全 PR を人間がレビューし、CI green を確認して手動マージする。

## 代替案

- **Dependabot**: GitHub 純正で導入は容易だが、(1) Nix manager が無い、(2) monorepo の
  グルーピングや digest pin 維持の柔軟性が Renovate に劣る。本リポジトリは Nix を含む
  多エコシステム構成のため Renovate を採用した。
- **セルフホスト Renovate（GitHub Action で cron 実行）**: トークン・権限・ランナーを
  自前管理する必要があり、特に Nix manager 用に nix 入りランナーの用意が要る。hosted
  app なら nix がサポート済みで運用負荷が小さいため採用しなかった。
- **導入しない（現状維持）**: 追従の取りこぼしと CVE 後追いの課題が解消しないため却下。

## トレードオフ・既知のリスク

- 定期的に更新 PR が起票され、レビュー工数が発生する（`schedule` / `prConcurrentLimit`
  / devDependencies のグルーピングで負荷を抑制）。
- 自動マージしないため、PR を放置すると追従が滞る運用リスクは残る。
- `ghcr.io/tursodatabase/libsql-server:latest` は tag 固定不可のため digest 運用となり、
  tag ベースの版差分は追えない。
- Renovate App のインストール（リポジトリへの権限付与）は GitHub 上の手動操作が必要。

## 将来の移行条件

- レビュー負荷が高い場合、`lockfile` / `digest` など低リスク更新に限定した自動マージの
  導入を検討する（最初から有効化はしない）。
- Nix manager の hosted サポートに問題が出た場合は、セルフホスト Action 方式へ切り替える。

## 関連リンク

- 設定: `.github/renovate.json5`
- 関連方針: `.claude/rules/common/duplication.md`（環境変数・バージョン固定の SSoT）
- Renovate ドキュメント: https://docs.renovatebot.com/
