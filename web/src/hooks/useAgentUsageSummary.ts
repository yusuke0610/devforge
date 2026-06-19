/**
 * モデル別の使用量サマリ（ADR-0012）を取得するフック。
 *
 * モデル選択モーダルが開いたときに取得し、各モデルカードへ
 * 「これまでの利用回数・消費クレジット」と残回数目安を表示する。
 */

import { useCallback, useEffect, useState } from "react";

import { getAgentUsageSummary } from "../api/billing";
import type { AgentModelAlias, AgentUsageSummaryEntry } from "../api/types";
import { FALLBACK_MESSAGES } from "../constants/messages";

/** エイリアス → サマリの引きやすい Map に変換した状態。 */
export type UsageByModel = Record<string, AgentUsageSummaryEntry | undefined>;

export function useAgentUsageSummary(enabled: boolean) {
  const [usageByModel, setUsageByModel] = useState<UsageByModel>({});
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const entries = await getAgentUsageSummary();
      const map: UsageByModel = {};
      for (const entry of entries) {
        map[entry.model] = entry;
      }
      setUsageByModel(map);
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

  /** 指定モデルのサマリを返す（未利用なら undefined）。 */
  const getUsage = useCallback(
    (alias: AgentModelAlias): AgentUsageSummaryEntry | undefined => usageByModel[alias],
    [usageByModel],
  );

  return { usageByModel, getUsage, loading, error, refresh };
}
