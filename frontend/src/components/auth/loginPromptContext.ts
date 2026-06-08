import { createContext, useContext } from "react";

/**
 * ログイン促進モーダルを開く関数を配布するコンテキスト。
 * 未ログインで要ログイン機能（プレビュー / ダウンロード / 連携への遷移など）を使おうとしたときに、
 * サイドバーとお試し入力フォームの双方から同じ 1 つのモーダルを開くために使う。
 *
 * Provider 本体は {@link ../auth/LoginPromptProvider} を参照。
 */
export const LoginPromptContext = createContext<(() => void) | null>(null);

/** ログイン促進モーダルを開く関数を取得する。Provider 配下でのみ利用できる。 */
export function useLoginPrompt(): () => void {
  const ctx = useContext(LoginPromptContext);
  if (!ctx) {
    // 配線ミスを握りつぶさず即座に気付けるようにする（開発者向け内部エラー）。
    throw new Error("useLoginPrompt must be used within a LoginPromptProvider");
  }
  return ctx;
}
