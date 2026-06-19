import type { ReactNode } from "react";

import { useCreditBalance } from "../../hooks/useCreditBalance";
import { CreditBalanceContext } from "./creditBalanceContext";

/**
 * クレジット残高（ADR-0012）を 1 つだけ保持し、配下のどこからでも
 * `useCreditBalanceContext()` で参照できるようにする Provider。
 *
 * サイドバー（残高表示）と Agent ウィジェット（消費後の `refresh`）が同じ状態を共有する。
 * `enabled`（= 認証済み）の間だけ残高を取得する。未認証では取得しない（401 連発を防ぐ）。
 */
export function CreditBalanceProvider({
  enabled,
  children,
}: {
  enabled: boolean;
  children: ReactNode;
}) {
  const state = useCreditBalance(enabled);
  return (
    <CreditBalanceContext.Provider value={state}>{children}</CreditBalanceContext.Provider>
  );
}
