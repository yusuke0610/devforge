/**
 * トークン購入画面（ADR-0012）のデータ取得フック。
 *
 * 残高・購入パック・取引履歴をまとめて取得する。購入後は呼び出し側が refresh する。
 * 取得ライフサイクル（loading / error / seq ガード）は useAsyncResource に委譲する。
 */

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
import { useAsyncResource } from "./useAsyncResource";

/** 購入画面に必要なデータをまとめて取得した結果。 */
type BillingPageData = {
  balance: number | null;
  packs: CreditPackResponse[];
  transactions: CreditTransactionResponse[];
  // 回数目安の基準: 有料モデル（Sonnet）の標準消費レート（null なら回数を出さない）
  paidRate: number | null;
};

const INITIAL_DATA: BillingPageData = {
  balance: null,
  packs: [],
  transactions: [],
  paidRate: null,
};

export function useBillingPage() {
  const { data, loading, error, refresh } = useAsyncResource<BillingPageData>(
    async () => {
      const [balanceRes, packsRes, transactionsRes, ratesRes] = await Promise.all([
        getCreditBalance(),
        getCreditPacks(),
        getCreditTransactions(),
        getModelRates(),
      ]);
      const paid: ModelRateEntry | undefined = ratesRes.find(
        (r) => r.model === PAID_REFERENCE_MODEL,
      );
      return {
        balance: balanceRes.balance,
        packs: packsRes,
        transactions: transactionsRes,
        paidRate: paid && !paid.is_free ? paid.baseline_credits_per_chat : null,
      };
    },
    { initialData: INITIAL_DATA, fallbackMessage: FALLBACK_MESSAGES.CREDIT_BALANCE },
  );

  return { ...data, loading, error, refresh };
}
