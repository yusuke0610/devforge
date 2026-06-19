/**
 * フロントエンド共通ロガー。`console.*` を直接呼ぶ代わりにこれを使う。
 *
 * ## なぜラッパーか
 * ログ出力の方針（本番でのレベル抑制・プレフィックス統一）を 1 か所へ集約し、
 * 各所での console 直書きによる方針のばらつきを防ぐ。console を呼ぶ唯一の
 * モジュールであり、ESLint の no-console ルールはこのファイルだけ例外にしている。
 *
 * ## 環境ゲート
 * ブラウザ環境のため backend のような Cloud Logging 集約・リモート送信は行わず、
 * console への出力に徹する。`import.meta.env.PROD`（Vite 本番ビルド）では
 * `debug` / `info` を抑制し、ユーザーのコンソールを汚さない。`warn` / `error` は
 * 障害調査に必要なため本番でも残す。
 *
 * ## 機密情報
 * ロガーは受け取った引数をそのまま console へ渡すだけ。氏名・メール・トークン等の
 * PII を渡さない責務は呼び出し側にある（`.claude/rules/security.md`）。
 */

/** 出力時に付与する統一プレフィックス。 */
const PREFIX = "[DevForge]";

/** 本番ビルドかどうか。debug / info の抑制判定に使う。 */
const isProd = import.meta.env.PROD;

export const logger = {
  /** 開発時の詳細ログ。本番では抑制される。 */
  debug(message: string, ...args: unknown[]): void {
    if (isProd) return;
    console.debug(PREFIX, message, ...args);
  },

  /** 一般的な情報ログ。本番では抑制される。 */
  info(message: string, ...args: unknown[]): void {
    if (isProd) return;
    console.info(PREFIX, message, ...args);
  },

  /** 警告ログ。本番でも出力する。 */
  warn(message: string, ...args: unknown[]): void {
    console.warn(PREFIX, message, ...args);
  },

  /** エラーログ。本番でも出力する。 */
  error(message: string, ...args: unknown[]): void {
    console.error(PREFIX, message, ...args);
  },
};
