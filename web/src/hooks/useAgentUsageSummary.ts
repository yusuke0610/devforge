/**
 * モデル別の使用量サマリ（ADR-0012）を取得するフック。
 *
 * モデル選択モーダルが開いたときに取得し、各モデルカードへ
 * 「これまでの利用回数・消費クレジット」と残回数目安を表示する。
 * 取得ライフサイクルは useAsyncResource に委譲し、ここではエイリアス → サマリの
 * 引きやすい Map への変換とアクセサだけを担う。
 */

import { useCallback } from "react";

import { getAgentUsageSummary } from "../api/billing";
import type { AgentModelAlias, AgentUsageSummaryEntry } from "../api/types";
import { FALLBACK_MESSAGES } from "../constants/messages";
import { useAsyncResource } from "./useAsyncResource";

/** エイリアス → サマリの引きやすい Map に変換した状態。 */
export type UsageByModel = Record<string, AgentUsageSummaryEntry | undefined>;

export function useAgentUsageSummary(enabled: boolean) {
  const { data: usageByModel, loading, error, refresh } = useAsyncResource<UsageByModel>(
    async () => {
      const entries = await getAgentUsageSummary();
      const map: UsageByModel = {};
      for (const entry of entries) {
        map[entry.model] = entry;
      }
      return map;
    },
    { enabled, initialData: {}, fallbackMessage: FALLBACK_MESSAGES.USAGE_SUMMARY },
  );

  /** 指定モデルのサマリを返す（未利用なら undefined）。 */
  const getUsage = useCallback(
    (alias: AgentModelAlias): AgentUsageSummaryEntry | undefined => usageByModel[alias],
    [usageByModel],
  );

  return { usageByModel, getUsage, loading, error, refresh };
}
