---
name: tdd
description: Use when implementing changes to the deterministic logic layer (mutmut/stryker mutation scope) with red→green→refactor phase control, or when the user explicitly asks for TDD. Presents test-case design first, writes a failing test and shows the failure output (red), writes the minimal implementation (green), then refactors while keeping tests green, and finally joins the normal stage flow. Trigger on requests such as "TDD で実装して", "/tdd", "テストファーストで", "red-green-refactor で進めて".
---

# TDD 段階制御（red → green → refactor）

決定論的ロジック層の実装を TDD で進めるための段階制御 skill。
**手順・禁止事項の正本は `.claude/rules/common/tdd.md`**（ADR-0019）。本 skill はそれをセッション内のフェーズ進行（停止・報告のタイミング）に落とす。

## 先に読む

- `.claude/rules/common/tdd.md`（ワークフロー正本）
- 対象領域の `test.md`（`.claude/rules/backend/test.md` / `.claude/rules/web/test.md` — OK 基準・アンチパターン）

## Phase 0: 対象判定とテスト設計の提示（停止点）

1. 変更対象の実装ファイルを特定し、TDD スコープ（backend: `[tool.mutmut] only_mutate` / web: stryker `mutate`）に該当するか判定して結果を報告する
   - **スコープ外だった場合**: その旨を伝え、通常のトリガーベース方針で進めるか確認する（ユーザーが明示的に TDD を指定した場合は続行してよい）
2. 実装する**振る舞いの一覧**をテストケース案として提示する（1 行 1 振る舞い。対象領域の OK 基準のケース数を満たす構成にする）
3. **ユーザーの確認を待つ**。テスト設計への合意が取れてから red に進む

## Phase 1: red — 失敗するテストを書く

振る舞い一覧の先頭 1 つについて:

1. テストだけを書く（**実装コードには触れない**）
2. 対象を絞って実行する:
   - backend: `nix develop --command bash -c "cd backend && python -m pytest tests/test_<module>.py -q"`
   - web: `nix develop --command bash -c "cd web && npx vitest run src/<path>/<module>.test.ts"`
3. **失敗出力の要点を会話に提示する**。「期待どおりの理由での失敗」であることを確認する（import エラー・collection error はテスト自体の不備なので直してから再実行）

## Phase 2: green — 最小実装

1. red のテストを通す最小限の実装を書く（先回りの汎用化をしない）
2. 対象テストの pass を実行結果で提示する
3. テスト側は触らない。仕様誤りに気づいた場合のみ、理由を報告してから修正する

振る舞い一覧に残りがあれば Phase 1 に戻る（1 サイクル 1 振る舞い）。

## Phase 3: refactor — 整理して合流

1. green を維持したまま重複抽出・命名整理を行う（`.claude/rules/common/duplication.md` に従う。不要ならスキップしてよい）
2. 領域のテスト全体を回して回帰がないことを確認する
3. `make ci`（`lint-tdd` を含む）を通し、通常のコミット / PR フロー（stage 待ち）に合流する。stage 時のサマリに **red の失敗出力を確認済みであること**を含める

## 注意

- 全フェーズを一気に進めない。Phase 0 の確認と、各 red の失敗出力提示は省略しない
- 振る舞いを変えない変更しか残らなかった場合（純リファクタ等）は、TDD サイクルではなく `Tdd-Exempt: <理由>` トレーラーの適用を提案する
