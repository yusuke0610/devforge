import { request } from "./client";
import { PATHS } from "./paths";
import type {
  AgentUsageSummaryEntry,
  CheckoutSessionResponse,
  CreditBalanceResponse,
  CreditPackResponse,
  CreditTransactionResponse,
  ModelRateEntry,
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

/** 購入可能なクレジットパック一覧を取得する。 */
export function getCreditPacks(): Promise<CreditPackResponse[]> {
  return request<CreditPackResponse[]>(PATHS.billing.packs, { method: "GET" });
}

/** モデル別の標準消費レート（回数目安用）を取得する。 */
export function getModelRates(): Promise<ModelRateEntry[]> {
  return request<ModelRateEntry[]>(PATHS.billing.modelRates, { method: "GET" });
}

/**
 * クレジット購入の Stripe Checkout セッションを作成し、決済ページの URL を取得する（ADR-0012）。
 * 返却された URL へリダイレクトすると Stripe ホストの決済ページに遷移する。
 */
export function createCheckoutSession(credits: number): Promise<CheckoutSessionResponse> {
  return request<CheckoutSessionResponse>(PATHS.billing.checkout, {
    method: "POST",
    body: JSON.stringify({ credits }),
  });
}
