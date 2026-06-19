/**
 * クレジット → 利用回数の目安計算（ADR-0012）。
 *
 * 1 クレジット = ¥1。回数の目安は「クレジット ÷ 1回あたりの消費」で算出する。
 * 「回数」の基準モデルは有料モデル（Sonnet）。無料モデル（消費 0）は目安を出さない。
 */

import type { AgentModelAlias } from "../api/types";

/** 回数アンカーの基準にする有料モデル。 */
export const PAID_REFERENCE_MODEL: AgentModelAlias = "sonnet";

// 1 クレジット = ¥1（ADR-0012）。購入フォームの円換算に使う。
// ※ペッグの正本は backend（pricing / model_catalog）。表示用の換算係数として保持する
export const YEN_PER_CREDIT = 1;

// 任意クレジット購入の入力範囲（誤入力の桁あふれ・極小購入を防ぐ）
export const MIN_PURCHASE_CREDITS = 100;
export const MAX_PURCHASE_CREDITS = 1_000_000;

/** クレジット数を円に換算する（1 クレジット = ¥1）。 */
export function creditsToYen(credits: number): number {
  return credits * YEN_PER_CREDIT;
}

/** クレジット量と 1 回あたりの消費から利用回数の目安を返す。算出不能なら null。 */
export function estimateChats(
  credits: number,
  creditsPerChat: number | null | undefined,
): number | null {
  // 負残高（ADR-0012 の有界損失で発生しうる）では「約 -N 回」になり混乱するため出さない
  if (credits < 0) return null;
  if (!creditsPerChat || creditsPerChat <= 0) return null;
  return Math.floor(credits / creditsPerChat);
}
