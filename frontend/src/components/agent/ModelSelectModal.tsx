import type { AgentModelAlias } from "../../api/types";
import {
  CREDIT_ESTIMATE_REFERENCE,
  getModelOptionsByProvider,
} from "../../constants/agentModels";
import {
  AGENT_MODEL_MESSAGES,
  creditsForChatsLabel,
  modelUsageLabel,
} from "../../constants/messages";
import { useAgentUsageSummary } from "../../hooks/useAgentUsageSummary";
import { useModelRates } from "../../hooks/useModelRates";
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
  // モーダルが開いている間だけ利用実績と標準レートを取得する
  const { getUsage } = useAgentUsageSummary(true);
  const { getBaselineRate, ratesByModel } = useModelRates(true);

  // 有料/無料判定の runtime 正本は model_rates API（`is_free`）。取得済みならそれを使い、
  // 未取得（初期/ローディング/エラー）の間は agentModels の静的 isPaid をフォールバックにする。
  const isPaidModel = (option: { alias: AgentModelAlias; isPaid: boolean }): boolean => {
    const rate = ratesByModel[option.alias];
    return rate ? !rate.is_free : option.isPaid;
  };

  const select = (alias: AgentModelAlias) => {
    dispatch(setAgentModel(alias));
    onClose();
  };

  /** 基準クレジット（1,000）あたりの平均利用回数の目安。残高には依存しない。
   * 1 回あたりの消費 = 実績があれば実測平均（累計消費 / 回数）、無ければ標準レート。 */
  const estimatePerReference = (
    alias: AgentModelAlias,
    creditCost: number,
    chatCount: number,
  ): number | null => {
    const perChat =
      chatCount > 0 && creditCost > 0 ? creditCost / chatCount : getBaselineRate(alias);
    if (!perChat || perChat <= 0) return null;
    return Math.floor(CREDIT_ESTIMATE_REFERENCE / perChat);
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
                  const paid = isPaidModel(option);
                  // 残高未取得（null: 初期/ローディング/エラー）の間は不足扱いにしない
                  const insufficient = paid && balance !== null && balance <= 0;
                  const usage = getUsage(option.alias);
                  const chatCount = usage?.chat_count ?? 0;
                  const creditCost = usage?.credit_cost ?? 0;
                  const perReference = paid
                    ? estimatePerReference(option.alias, creditCost, chatCount)
                    : null;
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
                        <span className={paid ? styles.paidBadge : styles.freeBadge}>
                          {paid
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
                      <p className={styles.cardUsage}>
                        {chatCount > 0
                          ? modelUsageLabel(chatCount, creditCost)
                          : AGENT_MODEL_MESSAGES.USAGE_NONE}
                        {perReference !== null && (
                          <span>
                            ・{creditsForChatsLabel(CREDIT_ESTIMATE_REFERENCE, perReference)}
                          </span>
                        )}
                      </p>
                      {insufficient && (
                        <p className={styles.insufficient}>
                          {AGENT_MODEL_MESSAGES.INSUFFICIENT_HINT}
                        </p>
                      )}
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
