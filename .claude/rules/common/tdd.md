---
paths:
  - backend/**
  - web/**
---

# TDD ワークフロー（決定論的ロジック層）

決定論的ビジネスロジックの変更は **TDD（red → green → refactor）で行う**（ADR-0019）。
本ファイルが手順の正本。各領域の `test.md` は OK 基準・アンチパターンの正本であり、本ワークフローと併用する。

## 対象判定（最初に必ず行う）

変更しようとしている実装ファイルが以下の glob に該当するか確認する。**スコープの正本はミューテーションテスト設定**（ADR-0017 と共有。ここに複製しない）:

- backend: `backend/pyproject.toml` の `[tool.mutmut] only_mutate`
- web: `web/stryker.conf.json` の `mutate`（`!` の除外パターン込み）

| 判定 | 従うルール |
|---|---|
| 該当する | 本ワークフロー（TDD）が**必須** |
| 該当しない（routers / schemas / UI コンポーネント / infra 等） | 各 `test.md` のトリガーベース方針 |

該当するのにテスト差分なしで PR を出すと `make lint-tdd`（`make ci` に含まれる）が fail する。振る舞いを変えない変更（リネーム・コメント修正・機械的リファクタ）は、コミットメッセージに `Tdd-Exempt: <理由>` トレーラーを付けて除外できる（理由はレビューで妥当性を見る）。

## red — 失敗するテストを先に書く

1. これから実装する**振る舞い 1 つ**について、期待挙動を表すテストを書く（実装コードにはまだ触れない）
2. 対象を絞って実行し、**期待どおりの理由で失敗すること**を確認する:

```bash
# backend
nix develop --command bash -c "cd backend && .venv/bin/python -m pytest tests/test_<module>.py -q"
# web
nix develop --command bash -c "cd web && npx vitest run src/<path>/<module>.test.ts"
```

3. **失敗出力（要点）を会話・PR に提示**してから green に進む

禁止事項:

- **実装を先に書いてから「fail するはずだったテスト」を逆算で書く**（TDD の体裁だけ整える行為。実装なぞりテストの温床）
- **red の省略**: 「自明に失敗するはず」でも必ず実行する。import エラーや collection error での失敗は「期待どおりの理由の失敗」ではない（テスト自体が壊れている）
- **red フェーズで複数の振る舞いのテストを一括作成する**: 1 サイクル 1 振る舞い。次の振る舞いは次のサイクルで

## green — テストを通す最小実装

- red のテストを通す**最小限の実装**を書く。先回りの汎用化をしない（`duplication.md` の Rule of Three）
- **テスト側は触らない**。実装中にテストの仕様誤りに気づいた場合のみ、その旨と理由を報告した上で修正する（黙って assert を実装に合わせて弱めるのは禁止）
- 対象テストが pass したら、周辺の既存テストも回して回帰がないことを確認する

## refactor — green を維持したまま整理

- 重複の抽出・命名の改善・分割を行う。判断基準と抽出先は `.claude/rules/common/duplication.md` に従う
- リファクタ後に再度テストを回して green を維持していることを確認する
- サイクル完了後は通常のフロー（`make ci` → stage）に合流する

## OK 基準との関係

TDD で書いたテストも、各領域の既存基準をそのまま満たすこと:

- backend: `.claude/rules/backend/test.md` の OK 基準（主要分岐ごとに 1 ケース・失敗パスは `pytest.raises`・DB はモックしない等）
- web: `.claude/rules/web/test.md` の OK 基準（フックは loading/success/error の 3 パス等）

1 サイクル 1 振る舞いで進めるため、変更全体が終わった時点でこれらのケース数を満たしていればよい（1 red で全ケースを書く必要はない）。

## 検証コマンド

```bash
make lint-tdd   # TDD 対象の実装変更にテスト差分が随伴しているか（make lint / make ci に含まれる）
```
