/**
 * モデル別の標準消費レート（ADR-0012）を取得するフック。
 *
 * 「Sonnet 約N回」の回数目安を出すために使う。利用実績のあるユーザーは
 * 実測平均を優先し、本レート（ベースライン）は新規ユーザーのフォールバック。
 */

import { useCallback, useEffect, useState } from "react";

import { getModelRates } from "../api/billing";
import type { AgentModelAlias, ModelRateEntry } from "../api/types";
import { FALLBACK_MESSAGES } from "../constants/messages";

export type RatesByModel = Record<string, ModelRateEntry | undefined>;

export function useModelRates(enabled: boolean) {
  const [ratesByModel, setRatesByModel] = useState<RatesByModel>({});
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const entries = await getModelRates();
      const map: RatesByModel = {};
      for (const entry of entries) {
        map[entry.model] = entry;
      }
      setRatesByModel(map);
    } catch (e) {
      setError(e instanceof Error ? e.message : FALLBACK_MESSAGES.USAGE_SUMMARY);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (enabled) {
      void refresh();
    }
  }, [enabled, refresh]);

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
