import {
  BILLING_PAGE_MESSAGES,
  formatCreditAmount,
  formatYen,
  transactionAmountLabel,
  transactionTypeLabel,
} from "../../constants/messages";
import { useBillingPage } from "../../hooks/useBillingPage";
import { useToast } from "../ui/toast";
import styles from "./BillingView.module.css";

/**
 * トークン購入画面（ADR-0012）。残高・購入パック・取引履歴を表示する。
 *
 * 購入導線（Stripe Checkout）は Phase 2 で実装する。現状はパックと購入ボタンを
 * 表示し、押下時に準備中である旨を通知する（画面は確認できる状態に保つ）。
 */
export function BillingView() {
  const { balance, packs, transactions, loading, error } = useBillingPage();
  const { showSuccess } = useToast();

  const handlePurchase = () => {
    // Phase 2 で POST /api/billing/checkout → Stripe Checkout へ遷移させる
    showSuccess(BILLING_PAGE_MESSAGES.CHECKOUT_PREPARING);
  };

  return (
    <div className={styles.page}>
      <header className={styles.header}>
        <h1 className={styles.title}>{BILLING_PAGE_MESSAGES.TITLE}</h1>
        <div className={styles.balanceCard}>
          <span className={styles.balanceLabel}>{BILLING_PAGE_MESSAGES.BALANCE_LABEL}</span>
          <span className={styles.balanceValue}>
            {balance !== null ? formatCreditAmount(balance) : "—"}
            <span className={styles.balanceUnit}>{BILLING_PAGE_MESSAGES.CREDITS_UNIT}</span>
          </span>
        </div>
      </header>

      {error && <p className={styles.error}>{error}</p>}
      {loading && <p className={styles.loading}>{BILLING_PAGE_MESSAGES.LOADING}</p>}

      <section className={styles.section}>
        <div className={styles.sectionHead}>
          <h2 className={styles.sectionTitle}>{BILLING_PAGE_MESSAGES.PACKS_TITLE}</h2>
          <span className={styles.preparingBadge}>{BILLING_PAGE_MESSAGES.PREPARING_BADGE}</span>
        </div>
        <p className={styles.sectionNote}>{BILLING_PAGE_MESSAGES.PACKS_NOTE}</p>
        <div className={styles.packs}>
          {packs.map((pack) => (
            <div key={pack.id} className={styles.packCard}>
              <span className={styles.packName}>{pack.name}</span>
              <span className={styles.packCredits}>
                {formatCreditAmount(pack.credits)}
                <span className={styles.packCreditsUnit}>
                  {BILLING_PAGE_MESSAGES.CREDITS_UNIT}
                </span>
              </span>
              <span className={styles.packPrice}>{formatYen(pack.price_jpy)}</span>
              <button type="button" className={styles.purchaseButton} onClick={handlePurchase}>
                {BILLING_PAGE_MESSAGES.PURCHASE_BUTTON}
              </button>
            </div>
          ))}
        </div>
      </section>

      <section className={styles.section}>
        <h2 className={styles.sectionTitle}>{BILLING_PAGE_MESSAGES.HISTORY_TITLE}</h2>
        {transactions.length === 0 ? (
          <p className={styles.sectionNote}>{BILLING_PAGE_MESSAGES.HISTORY_EMPTY}</p>
        ) : (
          <ul className={styles.history}>
            {transactions.map((tx) => (
              <li key={tx.id} className={styles.historyRow}>
                <span className={styles.historyType}>{transactionTypeLabel(tx.transaction_type)}</span>
                <span className={styles.historyDesc}>{tx.description ?? ""}</span>
                <span
                  className={tx.amount < 0 ? styles.historyMinus : styles.historyPlus}
                >
                  {transactionAmountLabel(tx.amount)}
                </span>
                <span className={styles.historyDate}>
                  {new Date(tx.created_at).toLocaleDateString("ja-JP")}
                </span>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
