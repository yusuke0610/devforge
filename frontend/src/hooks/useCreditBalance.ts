/**
 * クレジット残高（ADR-0012）の取得・更新フック。
 *
 * sonnet（有料モデル）選択時のみ取得する（enabled フラグ）。
 * チャット送信後は呼び出し側が refresh() で最新残高に更新する。
 */

import { useCallback, useEffect, useState } from "react";

import { getCreditBalance } from "../api/billing";
import { FALLBACK_MESSAGES } from "../constants/messages";

export function useCreditBalance(enabled: boolean) {
  const [balance, setBalance] = useState<number | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await getCreditBalance();
      setBalance(response.balance);
    } catch (e) {
      setError(e instanceof Error ? e.message : FALLBACK_MESSAGES.CREDIT_BALANCE);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (enabled) {
      void refresh();
    }
  }, [enabled, refresh]);

  return { balance, loading, error, refresh };
}
