import { getModelOption } from "../../constants/agentModels";
import { AGENT_MODEL_MESSAGES } from "../../constants/messages";
import { useAppSelector } from "../../store";
import styles from "./AgentModelBadge.module.css";

/**
 * サイドバーに常時表示する「使用モデル」（ADR-0012）。表示専用。
 * 切り替えは UserMenu → モデル選択モーダルで行う（ここからは切り替えない）。
 */
export function AgentModelBadge() {
  const model = useAppSelector((state) => state.agentModel.model);
  const option = getModelOption(model);

  return (
    <div className={styles.badge}>
      <span className={styles.label}>{AGENT_MODEL_MESSAGES.SIDEBAR_LABEL}</span>
      <span className={styles.value}>{option.name}</span>
      {option.isPaid && <span className={styles.paid}>{AGENT_MODEL_MESSAGES.PAID_BADGE}</span>}
    </div>
  );
}
