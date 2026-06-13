/**
 * クレジット → 利用回数の目安計算（ADR-0012）。
 *
 * 1 クレジット = ¥1。回数の目安は「クレジット ÷ 1回あたりの消費」で算出する。
 * 「回数」の基準モデルは有料モデル（Sonnet）。無料モデル（消費 0）は目安を出さない。
 */

import type { AgentModelAlias } from "../api/types";

/** 回数アンカーの基準にする有料モデル。 */
export const PAID_REFERENCE_MODEL: AgentModelAlias = "sonnet";

/** クレジット量と 1 回あたりの消費から利用回数の目安を返す。算出不能なら null。 */
export function estimateChats(
  credits: number,
  creditsPerChat: number | null | undefined,
): number | null {
  if (!creditsPerChat || creditsPerChat <= 0) return null;
  return Math.floor(credits / creditsPerChat);
}
