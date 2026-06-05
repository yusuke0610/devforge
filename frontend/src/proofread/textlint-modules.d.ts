/**
 * textlint ルール群の型宣言。これらの npm パッケージは型定義を同梱しておらず、
 * 校正 worker はルール本体を `unwrapModule` 経由で扱うため、ここで any として宣言する。
 * （ルールの内部構造に型安全は不要 — kernel に渡すだけ）。
 */
// textlint-rule-* 系（プリセット同梱の個別ルール）をまとめてワイルドカード宣言する。
declare module "textlint-rule-*";
