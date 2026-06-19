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
  getModelRates,
} from "../api/billing";
import type {
  CreditPackResponse,
  CreditTransactionResponse,
  ModelRateEntry,
} from "../api/types";
import { FALLBACK_MESSAGES } from "../constants/messages";
import { PAID_REFERENCE_MODEL } from "../utils/creditEstimate";

export function useBillingPage() {
  const [balance, setBalance] = useState<number | null>(null);
  const [packs, setPacks] = useState<CreditPackResponse[]>([]);
  const [transactions, setTransactions] = useState<CreditTransactionResponse[]>([]);
  // 回数目安の基準: 有料モデル（Sonnet）の標準消費レート（null なら回数を出さない）
  const [paidRate, setPaidRate] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [balanceRes, packsRes, transactionsRes, ratesRes] = await Promise.all([
        getCreditBalance(),
        getCreditPacks(),
        getCreditTransactions(),
        getModelRates(),
      ]);
      setBalance(balanceRes.balance);
      setPacks(packsRes);
      setTransactions(transactionsRes);
      const paid: ModelRateEntry | undefined = ratesRes.find(
        (r) => r.model === PAID_REFERENCE_MODEL,
      );
      setPaidRate(paid && !paid.is_free ? paid.baseline_credits_per_chat : null);
    } catch (e) {
      setError(e instanceof Error ? e.message : FALLBACK_MESSAGES.CREDIT_BALANCE);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  return { balance, packs, transactions, paidRate, loading, error, refresh };
}
