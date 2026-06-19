import { useEffect, useRef } from "react";

import { createCheckoutSession } from "../../api/billing";
import { getModelOption } from "../../constants/agentModels";
import {
  BILLING_PAGE_MESSAGES,
  FALLBACK_MESSAGES,
  formatCreditAmount,
  modelChatsEstimateLabel,
  transactionAmountLabel,
  transactionTypeLabel,
} from "../../constants/messages";
import { useBillingPage } from "../../hooks/useBillingPage";
import { toAppError } from "../../utils/appError";
import { estimateChats, PAID_REFERENCE_MODEL } from "../../utils/creditEstimate";
import { useToast } from "../ui/toast";
import { CreditPurchaseForm } from "./CreditPurchaseForm";
import styles from "./BillingView.module.css";

const PAID_MODEL_NAME = getModelOption(PAID_REFERENCE_MODEL).name;

// Stripe Checkout の戻り先 URL に付与するクエリ（backend の success_url / cancel_url と一致）
const CHECKOUT_QUERY_KEY = "checkout";
const CHECKOUT_RESULT_SUCCESS = "success";
const CHECKOUT_RESULT_CANCEL = "cancel";

/**
 * トークン購入画面（ADR-0012）。残高・購入パック・取引履歴を表示する。
 *
 * 購入ボタン押下で Stripe Checkout セッションを作成し、決済ページへリダイレクトする。
 * 決済後は success_url / cancel_url（`?checkout=success|cancel`）へ戻り、結果に応じて
 * トーストを表示して残高を再取得する（入金確定は Webhook が正のため反映に遅延がありうる）。
 */
export function BillingView() {
  const { balance, packs, transactions, paidRate, loading, error, refresh } = useBillingPage();
  const { showSuccess, showError } = useToast();
  // 決済結果トーストは初回マウント時に 1 度だけ処理する（refresh による再描画で多重発火させない）
  const checkoutResultHandled = useRef(false);

  useEffect(() => {
    if (checkoutResultHandled.current) return;
    const params = new URLSearchParams(window.location.search);
    const result = params.get(CHECKOUT_QUERY_KEY);
    if (result !== CHECKOUT_RESULT_SUCCESS && result !== CHECKOUT_RESULT_CANCEL) return;
    checkoutResultHandled.current = true;

    if (result === CHECKOUT_RESULT_SUCCESS) {
      showSuccess(BILLING_PAGE_MESSAGES.CHECKOUT_SUCCESS);
      void refresh();
    } else {
      showSuccess(BILLING_PAGE_MESSAGES.CHECKOUT_CANCELED);
    }
    // クエリを除去してリロード時の再通知を防ぐ（履歴は置き換える）
    window.history.replaceState({}, "", window.location.pathname);
  }, [refresh, showSuccess]);

  const handlePurchase = async (credits: number) => {
    try {
      const { checkout_url } = await createCheckoutSession(credits);
      // Stripe ホストの決済ページへ遷移する
      window.location.assign(checkout_url);
    } catch (e) {
      showError(toAppError(e, FALLBACK_MESSAGES.CHECKOUT));
    }
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
