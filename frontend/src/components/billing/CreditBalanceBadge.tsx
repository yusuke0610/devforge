import { BILLING_MESSAGES, formatCreditAmount } from "../../constants/messages";
import { useCreditBalanceContext } from "./creditBalanceContext";
import styles from "./CreditBalanceBadge.module.css";

/**
 * サイドバーフッターに常時表示するクレジット残高（ADR-0012）。
 * 残高はアカウント属性のため、Agent ウィジェットではなくサイドバーで表示する。
 * 値の正本は CreditBalanceProvider（消費後はウィジェットが refresh して更新する）。
 */
export function CreditBalanceBadge() {
  const { balance, error } = useCreditBalanceContext();

  return (
    <div className={styles.badge}>
      {balance !== null ? (
        <>
          <span className={styles.label}>{BILLING_MESSAGES.SIDEBAR_LABEL}</span>
          <span className={styles.value}>{formatCreditAmount(balance)}</span>
        </>
      ) : (
        <span className={error ? styles.error : styles.label}>
          {error ?? BILLING_MESSAGES.BALANCE_LOADING}
        </span>
      )}
    </div>
  );
}
