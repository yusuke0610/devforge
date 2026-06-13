import { createContext, useContext } from "react";

/**
 * クレジット残高（ADR-0012）をアプリ横断で配布するコンテキスト。
 *
 * 残高は「Agent の機能」ではなく「アカウントの属性」のため、サイドバー（常時表示）と
 * Agent ウィジェット（消費後の再取得）の双方が同じ 1 つの状態を共有する。
 * Provider 本体は {@link ./CreditBalanceProvider} を参照。
 */
export type CreditBalanceContextValue = {
  /** 現在残高。未取得・無効化中は null。 */
  balance: number | null;
  loading: boolean;
  error: string | null;
  /** 最新残高を取り直す（有料モデル消費後に呼ぶ）。 */
  refresh: () => Promise<void>;
};

export const CreditBalanceContext = createContext<CreditBalanceContextValue | null>(null);

/** クレジット残高の状態を取得する。Provider 配下でのみ利用できる。 */
export function useCreditBalanceContext(): CreditBalanceContextValue {
  const ctx = useContext(CreditBalanceContext);
  if (!ctx) {
    // 配線ミスを握りつぶさず即座に気付けるようにする（開発者向け内部エラー）。
    throw new Error("useCreditBalanceContext must be used within a CreditBalanceProvider");
  }
  return ctx;
}
