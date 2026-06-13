import type { AgentModelAlias } from "../../api/types";
import { AGENT_MODEL_OPTIONS } from "../../constants/agentModels";
import { AGENT_MODEL_MESSAGES } from "../../constants/messages";
import { useAppDispatch, useAppSelector } from "../../store";
import { setAgentModel } from "../../store/agentModelSlice";
import { useCreditBalanceContext } from "../billing/creditBalanceContext";
import styles from "./ModelSelectModal.module.css";

/**
 * AI モデル選択モーダル（ADR-0012）。Claude のプラン選択のようなカード UI。
 *
 * UserMenu から開く。カード選択で即時にグローバル設定（redux）へ反映して閉じる。
 * 有料（Sonnet）は残高不足のとき警告を出すが、選択自体は許可する
 * （送信時に 402 で課金導線へ誘導する設計 / ADR-0012）。
 */
export function ModelSelectModal({ onClose }: { onClose: () => void }) {
  const dispatch = useAppDispatch();
  const currentModel = useAppSelector((state) => state.agentModel.model);
  const { balance } = useCreditBalanceContext();

  const select = (alias: AgentModelAlias) => {
    dispatch(setAgentModel(alias));
    onClose();
  };

  return (
    <div className={styles.overlay} onClick={onClose}>
      <div
        className={styles.dialog}
        role="dialog"
        aria-modal="true"
        aria-label={AGENT_MODEL_MESSAGES.MODAL_TITLE}
        onClick={(e) => e.stopPropagation()}
      >
        <header className={styles.header}>
          <h2 className={styles.title}>{AGENT_MODEL_MESSAGES.MODAL_TITLE}</h2>
          <button
            type="button"
            className={styles.close}
            onClick={onClose}
            aria-label={AGENT_MODEL_MESSAGES.CLOSE_LABEL}
          >
            ×
          </button>
        </header>
        <p className={styles.description}>{AGENT_MODEL_MESSAGES.MODAL_DESCRIPTION}</p>
        <div className={styles.cards}>
          {AGENT_MODEL_OPTIONS.map((option) => {
            const isCurrent = option.alias === currentModel;
            const insufficient = option.isPaid && (balance ?? 0) <= 0;
            return (
              <button
                key={option.alias}
                type="button"
                className={`${styles.card} ${isCurrent ? styles.cardCurrent : ""}`}
                onClick={() => select(option.alias)}
                aria-pressed={isCurrent}
              >
                <div className={styles.cardHead}>
                  <span className={styles.cardName}>{option.name}</span>
                  <span className={option.isPaid ? styles.paidBadge : styles.freeBadge}>
                    {option.isPaid
                      ? AGENT_MODEL_MESSAGES.PAID_BADGE
                      : AGENT_MODEL_MESSAGES.FREE_BADGE}
                  </span>
                  {isCurrent && (
                    <span className={styles.currentBadge}>
                      {AGENT_MODEL_MESSAGES.CURRENT_BADGE}
                    </span>
                  )}
                </div>
                <p className={styles.cardTagline}>{option.tagline}</p>
                <p className={styles.cardCost}>{option.costHint}</p>
                {insufficient && (
                  <p className={styles.insufficient}>{AGENT_MODEL_MESSAGES.INSUFFICIENT_HINT}</p>
                )}
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
}
