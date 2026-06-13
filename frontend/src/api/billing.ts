import { request } from "./client";
import { PATHS } from "./paths";
import type {
  AgentUsageSummaryEntry,
  CreditBalanceResponse,
  CreditTransactionResponse,
} from "./types";

/**
 * クレジット残高を取得する（ADR-0012）。
 * sonnet（有料モデル）選択時の残高表示と、チャット送信後の残高更新に使う。
 */
export function getCreditBalance(): Promise<CreditBalanceResponse> {
  return request<CreditBalanceResponse>(PATHS.billing.balance, { method: "GET" });
}

/** クレジット台帳履歴（付与・消費）を新しい順に取得する。 */
export function getCreditTransactions(): Promise<CreditTransactionResponse[]> {
  return request<CreditTransactionResponse[]>(PATHS.billing.transactions, { method: "GET" });
}

/** モデル別の使用量サマリ（チャット回数・トークン・消費クレジット）を取得する。 */
export function getAgentUsageSummary(): Promise<AgentUsageSummaryEntry[]> {
  return request<AgentUsageSummaryEntry[]>(PATHS.billing.usageSummary, { method: "GET" });
}
