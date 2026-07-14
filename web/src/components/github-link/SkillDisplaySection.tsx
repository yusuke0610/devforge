import { useGitHubSkills } from "../../hooks/useGitHubSkills";
import { useAppErrorToast } from "../ui/toast";
import { InlineSpinner } from "../ui/InlineSpinner";
import { SKILL_DISPLAY_MESSAGES } from "../../constants/messages";
import type { AgentModelAlias } from "../../api/types";
import dash from "./GitHubLinkDashboard.module.css";
import styles from "./SkillDisplaySection.module.css";

/**
 * 検出済みスキルの一覧と、表示名・畳み込みの human-in-the-loop 確定フロー（ADR-0016 D11）。
 *
 * 一覧はグループ化して実効表示名（確定 > 機械 > canonical）で表示する。「AIに提案してもらう」で
 * agent の提案を受け取り、表示名を編集して確定する。確定は独立 Layer 3 に保存され再連携でも残る。
 *
 * @param model 提案に使う LLM モデル（ユーザーメニューのグローバル設定）
 */
export function SkillDisplaySection({ model }: { model: AgentModelAlias }) {
  const {
    groups,
    loading,
    error,
    proposal,
    proposing,
    confirming,
    propose,
    updateProposalName,
    discardProposal,
    confirm,
  } = useGitHubSkills(model);

  useAppErrorToast(error);

  return (
    <div className={dash.section}>
      <h2>{SKILL_DISPLAY_MESSAGES.HEADING}</h2>
      <p className={dash.summaryText}>{SKILL_DISPLAY_MESSAGES.HINT}</p>

      {loading ? (
        <InlineSpinner label="読み込み中..." />
      ) : groups.length === 0 ? (
        <p className={dash.summaryText}>{SKILL_DISPLAY_MESSAGES.EMPTY}</p>
      ) : (
        <>
          <div className={styles.skillList}>
            {groups.map((group) => (
              <span key={group.key} className={styles.skillChip}>
                <span className={styles.kindBadge}>{group.skills[0].kind}</span>
                <span className={styles.skillLabel}>{group.label}</span>
                {group.skills.length > 1 && (
                  <span className={styles.skillSub}>
                    {SKILL_DISPLAY_MESSAGES.memberCountLabel(group.skills.length)}
                  </span>
                )}
              </span>
            ))}
          </div>

          <button
            type="button"
            className={dash.downloadButton}
            onClick={() => void propose()}
            // レビュー中（proposal 表示中）は再提案を止め、確定待ちの提案を取りこぼさない
            disabled={proposing || confirming || proposal !== null}
          >
            {proposing ? (
              <InlineSpinner label={SKILL_DISPLAY_MESSAGES.PROPOSING} />
            ) : (
              SKILL_DISPLAY_MESSAGES.PROPOSE
            )}
          </button>
        </>
      )}

      {proposal !== null && (
        <div className={styles.reviewPanel}>
          <div className={styles.reviewHeading}>
            {proposal.length === 0
              ? SKILL_DISPLAY_MESSAGES.PROPOSE_EMPTY
              : SKILL_DISPLAY_MESSAGES.REVIEW_HEADING}
          </div>

          {proposal.map((group, index) => (
            <div key={index} className={styles.groupRow}>
              <input
                className={styles.nameInput}
                type="text"
                value={group.displayName}
                // 各行を支援技術で区別できるよう、対象スキルを含めた aria-label にする
                aria-label={`${SKILL_DISPLAY_MESSAGES.DISPLAY_NAME_LABEL}: ${group.members
                  .map((m) => m.canonical_name)
                  .join(", ")}`}
                onChange={(e) => updateProposalName(index, e.target.value)}
              />
              <span className={styles.groupMembers}>
                {group.members.map((m) => m.canonical_name).join(", ")}
              </span>
            </div>
          ))}

          <div className={styles.reviewActions}>
            {proposal.length > 0 && (
              <button
                type="button"
                className={dash.downloadButton}
                onClick={() => void confirm()}
                disabled={confirming}
              >
                {confirming ? (
                  <InlineSpinner label={SKILL_DISPLAY_MESSAGES.CONFIRMING} />
                ) : (
                  SKILL_DISPLAY_MESSAGES.CONFIRM
                )}
              </button>
            )}
            <button
              type="button"
              className={styles.secondaryButton}
              onClick={discardProposal}
              disabled={confirming}
            >
              {SKILL_DISPLAY_MESSAGES.DISCARD}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
