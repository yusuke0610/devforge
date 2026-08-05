import type { ResumeDraftCandidateResponse } from "../../api/types";
import {
  RESUME_DRAFT_CANDIDATE_MESSAGES,
  durationLabel,
  implementationVolumeLabel,
  selectionCountLabel,
} from "../../constants/messages";
import { isSelectionFull } from "../../utils/resumeDraftCandidates";
import { InlineSpinner } from "../ui/InlineSpinner";
import dash from "./GitHubLinkDashboard.module.css";
import styles from "./ResumeDraftCandidateList.module.css";

/**
 * ドラフトに載せるリポジトリ候補の選択リスト（ADR-0026 決定 2 / 3）。
 *
 * 候補は機械が落とさず全件表示する。デフォルト非選択のものには理由バッジを添え、
 * ユーザーが常に選び直せるようにする（判定を覆せることが設計上の要件）。
 * 上限に達したときは未選択のチェックボックスだけを無効化し、選択解除は妨げない。
 */
export function ResumeDraftCandidateList({
  candidates,
  selected,
  selectionLimit,
  loading,
  disabled,
  onToggle,
}: {
  candidates: ResumeDraftCandidateResponse[];
  selected: string[];
  selectionLimit: number;
  loading: boolean;
  disabled: boolean;
  onToggle: (fullName: string) => void;
}) {
  if (loading) {
    return <InlineSpinner label={RESUME_DRAFT_CANDIDATE_MESSAGES.LOADING} />;
  }
  if (candidates.length === 0) {
    return <p className={dash.summaryText}>{RESUME_DRAFT_CANDIDATE_MESSAGES.EMPTY}</p>;
  }

  const full = isSelectionFull(selected, selectionLimit);

  return (
    <div className={styles.container}>
      <p className={styles.count}>{selectionCountLabel(selected.length, selectionLimit)}</p>
      {full && <p className={styles.limitNote}>{RESUME_DRAFT_CANDIDATE_MESSAGES.LIMIT_REACHED}</p>}
      <ul className={styles.list}>
        {candidates.map((candidate) => {
          const checked = selected.includes(candidate.full_name);
          return (
            <li key={candidate.full_name} className={styles.item}>
              <label className={styles.itemLabel}>
                <input
                  type="checkbox"
                  checked={checked}
                  // 上限到達時は「未選択の追加」だけを止める（選択解除は常にできる）
                  disabled={disabled || (!checked && full)}
                  onChange={() => onToggle(candidate.full_name)}
                />
                <span className={styles.name}>{candidate.full_name}</span>
              </label>
              {candidate.description && (
                <p className={styles.description}>{candidate.description}</p>
              )}
              <div className={styles.signals}>
                <span>
                  {RESUME_DRAFT_CANDIDATE_MESSAGES.DURATION_LABEL}:{" "}
                  {durationLabel(candidate.duration_days)}
                </span>
                <span>
                  {RESUME_DRAFT_CANDIDATE_MESSAGES.VOLUME_LABEL}:{" "}
                  {implementationVolumeLabel(candidate.implementation_volume)}
                </span>
                {candidate.has_infra && (
                  <span className={styles.infraBadge}>
                    {RESUME_DRAFT_CANDIDATE_MESSAGES.HAS_INFRA_BADGE}
                  </span>
                )}
              </div>
              {(candidate.technology_stacks ?? []).length > 0 && (
                <div className={styles.stacks}>
                  {(candidate.technology_stacks ?? []).map((stack) => (
                    <span key={`${stack.category}-${stack.name}`} className={styles.stack}>
                      {stack.name}
                    </span>
                  ))}
                </div>
              )}
              {(candidate.reasons ?? []).length > 0 && (
                <div className={styles.reasons}>
                  {(candidate.reasons ?? []).map((reason) => (
                    <span key={reason} className={styles.reasonBadge}>
                      {RESUME_DRAFT_CANDIDATE_MESSAGES.REASON_LABELS[reason] ?? reason}
                    </span>
                  ))}
                </div>
              )}
            </li>
          );
        })}
      </ul>
    </div>
  );
}
