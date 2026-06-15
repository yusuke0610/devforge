/**
 * クレジット残高（ADR-0012）の取得・更新フック。
 *
 * sonnet（有料モデル）選択時のみ取得する（enabled フラグ）。
 * チャット送信後は呼び出し側が refresh() で最新残高に更新する。
 */

import { useCallback, useEffect, useRef, useState } from "react";

import { getCreditBalance } from "../api/billing";
import { FALLBACK_MESSAGES } from "../constants/messages";

export function useCreditBalance(enabled: boolean) {
  const [balance, setBalance] = useState<number | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // refresh が重なったとき、古い応答が新しい状態を上書きしないよう最新だけ反映する
  const requestSeqRef = useRef(0);

  const refresh = useCallback(async () => {
    const seq = ++requestSeqRef.current;
    setLoading(true);
    setError(null);
    try {
      const response = await getCreditBalance();
      if (seq === requestSeqRef.current) setBalance(response.balance);
    } catch (e) {
      if (seq === requestSeqRef.current) {
        setError(e instanceof Error ? e.message : FALLBACK_MESSAGES.CREDIT_BALANCE);
      }
    } finally {
      if (seq === requestSeqRef.current) setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (enabled) {
      void refresh();
    }
  }, [enabled, refresh]);

  return { balance, loading, error, refresh };
}
