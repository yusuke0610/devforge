import { getModelOption } from "../../constants/agentModels";
import {
  BILLING_PAGE_MESSAGES,
  formatCreditAmount,
  modelChatsEstimateLabel,
  transactionAmountLabel,
  transactionTypeLabel,
} from "../../constants/messages";
import { useBillingPage } from "../../hooks/useBillingPage";
import { estimateChats, PAID_REFERENCE_MODEL } from "../../utils/creditEstimate";
import { useToast } from "../ui/toast";
import { CreditPurchaseForm } from "./CreditPurchaseForm";
import styles from "./BillingView.module.css";

const PAID_MODEL_NAME = getModelOption(PAID_REFERENCE_MODEL).name;

/**
 * トークン購入画面（ADR-0012）。残高・購入パック・取引履歴を表示する。
 *
 * 購入導線（Stripe Checkout）は Phase 2 で実装する。現状はパックと購入ボタンを
 * 表示し、押下時に準備中である旨を通知する（画面は確認できる状態に保つ）。
 */
export function BillingView() {
  const { balance, packs, transactions, paidRate, loading, error } = useBillingPage();
  const { showSuccess } = useToast();

  // Phase 2 で onPurchase(credits) を受け、POST /api/billing/checkout → Stripe Checkout へ遷移させる
  const handlePurchase = () => {
    showSuccess(BILLING_PAGE_MESSAGES.CHECKOUT_PREPARING);
  };

  const balanceChats = balance !== null ? estimateChats(balance, paidRate) : null;

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
          {balanceChats !== null && (
            <span className={styles.balanceEstimate}>
              {modelChatsEstimateLabel(PAID_MODEL_NAME, balanceChats)}
            </span>
          )}
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
        <CreditPurchaseForm packs={packs} paidRate={paidRate} onPurchase={handlePurchase} />
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
