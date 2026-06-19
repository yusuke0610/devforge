import { useState } from "react";

import type { CreditPackResponse } from "../../api/types";
import { getModelOption } from "../../constants/agentModels";
import {
  BILLING_PAGE_MESSAGES,
  formatCreditAmount,
  formatYen,
  modelChatsEstimateLabel,
  purchaseRangeHint,
} from "../../constants/messages";
import {
  creditsToYen,
  estimateChats,
  MAX_PURCHASE_CREDITS,
  MIN_PURCHASE_CREDITS,
  PAID_REFERENCE_MODEL,
} from "../../utils/creditEstimate";
import styles from "./CreditPurchaseForm.module.css";

const PAID_MODEL_NAME = getModelOption(PAID_REFERENCE_MODEL).name;

/**
 * 任意クレジット数の購入フォーム（ADR-0012）。
 *
 * 入力された数量を onChange でリアルタイムに円換算（1 クレジット = ¥1）し、
 * 「Sonnet 約N回」の回数目安も併せて表示する。パックはクイック選択の preset として使う。
 * 実際の決済（Stripe Checkout）は Phase 2。
 */
export function CreditPurchaseForm({
  packs,
  paidRate,
  onPurchase,
}: {
  packs: CreditPackResponse[];
  paidRate: number | null;
  onPurchase: (credits: number) => void;
}) {
  const [creditInput, setCreditInput] = useState("");

  // 整数文字列のみ受理する。parseInt は "100.9" を 100 に切り詰めてしまい、
  // 誤入力が別の有効額として課金されるのを防ぐ（厳密パース）
  const normalized = creditInput.trim();
  const parsed = Number(normalized);
  const isValid =
    /^\d+$/.test(normalized) &&
    Number.isSafeInteger(parsed) &&
    parsed >= MIN_PURCHASE_CREDITS &&
    parsed <= MAX_PURCHASE_CREDITS;
  const yen = isValid ? creditsToYen(parsed) : null;
  const chats = isValid ? estimateChats(parsed, paidRate) : null;

  return (
    <div className={styles.form}>
      <label className={styles.label} htmlFor="credit-amount">
        {BILLING_PAGE_MESSAGES.INPUT_LABEL}
      </label>
      <div className={styles.inputRow}>
        <input
          id="credit-amount"
          className={styles.input}
          type="number"
          inputMode="numeric"
          min={MIN_PURCHASE_CREDITS}
          max={MAX_PURCHASE_CREDITS}
          step={100}
          value={creditInput}
          onChange={(e) => setCreditInput(e.target.value)}
          placeholder={BILLING_PAGE_MESSAGES.INPUT_PLACEHOLDER}
        />
        <span className={styles.unit}>{BILLING_PAGE_MESSAGES.CREDITS_UNIT}</span>
      </div>

      {yen !== null ? (
        <p className={styles.conversion}>
          <span className={styles.yen}>{formatYen(yen)}</span>
          {chats !== null && (
            <span className={styles.chats}>
              ・{modelChatsEstimateLabel(PAID_MODEL_NAME, chats)}
            </span>
          )}
        </p>
      ) : (
        <p className={styles.hint}>
          {purchaseRangeHint(MIN_PURCHASE_CREDITS, MAX_PURCHASE_CREDITS)}
        </p>
      )}

      <div className={styles.presets}>
        <span className={styles.presetsLabel}>{BILLING_PAGE_MESSAGES.PRESETS_LABEL}</span>
        {packs.map((pack) => (
          <button
            key={pack.id}
            type="button"
            className={styles.preset}
            onClick={() => setCreditInput(String(pack.credits))}
          >
            {formatCreditAmount(pack.credits)}
          </button>
        ))}
      </div>

      <button
        type="button"
        className={styles.purchaseButton}
        disabled={!isValid}
        onClick={() => {
          if (isValid) onPurchase(parsed);
        }}
      >
        {BILLING_PAGE_MESSAGES.PURCHASE_BUTTON}
      </button>
    </div>
  );
}
