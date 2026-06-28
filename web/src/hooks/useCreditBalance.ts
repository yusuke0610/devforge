/**
 * クレジット残高（ADR-0012）の取得・更新フック。
 *
 * sonnet（有料モデル）選択時のみ取得する（enabled フラグ）。
 * チャット送信後は呼び出し側が refresh() で最新残高に更新する。
 * 取得ライフサイクル（loading / error / seq ガード）は useAsyncResource に委譲する。
 */

import { getCreditBalance } from "../api/billing";
import { FALLBACK_MESSAGES } from "../constants/messages";
import { useAsyncResource } from "./useAsyncResource";

export function useCreditBalance(enabled: boolean) {
  const { data: balance, loading, error, refresh } = useAsyncResource<number | null>(
    async () => (await getCreditBalance()).balance,
    { enabled, initialData: null, fallbackMessage: FALLBACK_MESSAGES.CREDIT_BALANCE },
  );

  return { balance, loading, error, refresh };
}
