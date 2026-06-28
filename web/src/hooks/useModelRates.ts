/**
 * モデル別の標準消費レート（ADR-0012）を取得するフック。
 *
 * 「Sonnet 約N回」の回数目安を出すために使う。利用実績のあるユーザーは
 * 実測平均を優先し、本レート（ベースライン）は新規ユーザーのフォールバック。
 * 取得ライフサイクルは useAsyncResource に委譲し、ここでは Map 化とアクセサだけを担う。
 */

import { useCallback } from "react";

import { getModelRates } from "../api/billing";
import type { AgentModelAlias, ModelRateEntry } from "../api/types";
import { FALLBACK_MESSAGES } from "../constants/messages";
import { useAsyncResource } from "./useAsyncResource";

export type RatesByModel = Record<string, ModelRateEntry | undefined>;

export function useModelRates(enabled: boolean) {
  const { data: ratesByModel, loading, error, refresh } = useAsyncResource<RatesByModel>(
    async () => {
      const entries = await getModelRates();
      const map: RatesByModel = {};
      for (const entry of entries) {
        map[entry.model] = entry;
      }
      return map;
    },
    { enabled, initialData: {}, fallbackMessage: FALLBACK_MESSAGES.USAGE_SUMMARY },
  );

  /** 指定モデルの 1 回あたり標準消費クレジット（未取得・無料モデルは null）。 */
  const getBaselineRate = useCallback(
    (alias: AgentModelAlias): number | null => {
      const entry = ratesByModel[alias];
      if (!entry || entry.is_free) return null;
      return entry.baseline_credits_per_chat;
    },
    [ratesByModel],
  );

  return { ratesByModel, getBaselineRate, loading, error, refresh };
}
