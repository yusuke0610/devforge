import type { AgentModelAlias } from "../../api/types";
import { getModelOptionsByProvider } from "../../constants/agentModels";
import { AGENT_MODEL_MESSAGES } from "../../constants/messages";
import { useAppDispatch, useAppSelector } from "../../store";
import { setAgentModel } from "../../store/agentModelSlice";
import styles from "./ModelSelectModal.module.css";

/**
 * AI モデル選択モーダル。Claude のプラン選択のようなカード UI。
 *
 * UserMenu から開く。カード選択で即時にグローバル設定（redux）へ反映して閉じる。
 * ADR-0023 で課金を撤去したため、全モデルが無料で利用できる（マルチプロバイダは
 * #523 で Haiku + Ollama へ縮退予定）。
 */
export function ModelSelectModal({ onClose }: { onClose: () => void }) {
  const dispatch = useAppDispatch();
  const currentModel = useAppSelector((state) => state.agentModel.model);

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
        <div className={styles.columns}>
          {getModelOptionsByProvider().map((group) => (
            <div key={group.provider} className={styles.column}>
              <h3 className={styles.columnLabel}>{group.label}</h3>
              <div className={styles.cards}>
                {group.options.map((option) => {
                  const isCurrent = option.alias === currentModel;
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
                        {isCurrent && (
                          <span className={styles.currentBadge}>
                            {AGENT_MODEL_MESSAGES.CURRENT_BADGE}
                          </span>
                        )}
                      </div>
                      <p className={styles.cardTagline}>{option.tagline}</p>
                    </button>
                  );
                })}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
