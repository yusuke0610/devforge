/**
 * 選択可能な AI モデル（ADR-0012）の表示メタデータ。
 *
 * エイリアスの正本は backend `services/agent/model_catalog.py`（実モデル ID・課金レート）。
 * ここはフロントの表示用（製品名・説明・コスト目安）の SSoT で、プランカード UI と
 * サイドバーの使用モデル表示が参照する。
 */

import type { AgentModelAlias } from "../api/types";
import { AGENT_MODEL_MESSAGES } from "./messages";

export type AgentModelOption = {
  alias: AgentModelAlias;
  /** 製品名（翻訳しない） */
  name: string;
  /** クレジットを消費するか（有料バッジ・残高チェックの表示に使う） */
  isPaid: boolean;
  tagline: string;
  costHint: string;
};

// 「N クレジットで平均M回」の目安に使う基準クレジット量（残高に依存しない比率表示）。
// 1 クレジット = ¥1 なので 1,000 クレジット = ¥1,000（手に取りやすい基準額）
export const CREDIT_ESTIMATE_REFERENCE = 1_000;

export const AGENT_MODEL_OPTIONS: readonly AgentModelOption[] = [
  {
    alias: "haiku",
    name: "Haiku",
    isPaid: false,
    tagline: AGENT_MODEL_MESSAGES.HAIKU_TAGLINE,
    costHint: AGENT_MODEL_MESSAGES.HAIKU_COST,
  },
  {
    alias: "sonnet",
    name: "Sonnet",
    isPaid: true,
    tagline: AGENT_MODEL_MESSAGES.SONNET_TAGLINE,
    costHint: AGENT_MODEL_MESSAGES.SONNET_COST,
  },
];

/** エイリアスから表示メタデータを引く。未知の値は先頭（haiku）にフォールバック。 */
export function getModelOption(alias: AgentModelAlias): AgentModelOption {
  return AGENT_MODEL_OPTIONS.find((option) => option.alias === alias) ?? AGENT_MODEL_OPTIONS[0];
}
