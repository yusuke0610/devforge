import { getModelOption } from "../../constants/agentModels";
import {
  BILLING_MESSAGES,
  formatCreditAmount,
  modelChatsEstimateLabel,
} from "../../constants/messages";
import { useModelRates } from "../../hooks/useModelRates";
import { estimateChats, PAID_REFERENCE_MODEL } from "../../utils/creditEstimate";
import { useCreditBalanceContext } from "./creditBalanceContext";
import styles from "./CreditBalanceBadge.module.css";

/**
 * サイドバーに常時表示するクレジット残高（ADR-0012）。1 クレジット = ¥1。
 * 残高に加えて「Sonnet 約N回」の回数目安を併記する（直感的な残量把握のため）。
 * 値の正本は CreditBalanceProvider（消費後はウィジェットが refresh して更新する）。
 */
export function CreditBalanceBadge() {
  const { balance, error } = useCreditBalanceContext();
  const { getBaselineRate } = useModelRates(true);

  const chats =
    balance !== null ? estimateChats(balance, getBaselineRate(PAID_REFERENCE_MODEL)) : null;
  const paidModelName = getModelOption(PAID_REFERENCE_MODEL).name;

  return (
    <div className={styles.badge}>
      <div className={styles.row}>
        <span className={styles.label}>{BILLING_MESSAGES.SIDEBAR_LABEL}</span>
        {balance !== null ? (
          <span className={styles.value}>{formatCreditAmount(balance)}</span>
        ) : (
          <span className={error ? styles.error : styles.label}>
            {error ?? BILLING_MESSAGES.BALANCE_LOADING}
          </span>
        )}
      </div>
      {chats !== null && (
        <span className={styles.estimate}>
          {modelChatsEstimateLabel(paidModelName, chats)}
        </span>
      )}
    </div>
  );
}
