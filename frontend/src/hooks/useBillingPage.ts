/**
 * トークン購入画面（ADR-0012）のデータ取得フック。
 *
 * 残高・購入パック・取引履歴をまとめて取得する。購入後は呼び出し側が refresh する。
 */

import { useCallback, useEffect, useState } from "react";

import {
  getCreditBalance,
  getCreditPacks,
  getCreditTransactions,
} from "../api/billing";
import type { CreditPackResponse, CreditTransactionResponse } from "../api/types";
import { FALLBACK_MESSAGES } from "../constants/messages";

export function useBillingPage() {
  const [balance, setBalance] = useState<number | null>(null);
  const [packs, setPacks] = useState<CreditPackResponse[]>([]);
  const [transactions, setTransactions] = useState<CreditTransactionResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [balanceRes, packsRes, transactionsRes] = await Promise.all([
        getCreditBalance(),
        getCreditPacks(),
        getCreditTransactions(),
      ]);
      setBalance(balanceRes.balance);
      setPacks(packsRes);
      setTransactions(transactionsRes);
    } catch (e) {
      setError(e instanceof Error ? e.message : FALLBACK_MESSAGES.CREDIT_BALANCE);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  return { balance, packs, transactions, loading, error, refresh };
}
