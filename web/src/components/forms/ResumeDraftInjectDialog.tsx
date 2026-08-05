import { useState } from "react";

import type { ResumeDraftResultResponse } from "../../api/types";
import { RESUME_DRAFT_MESSAGES, UI_MESSAGES } from "../../constants/messages";
import type { CareerFormState } from "../../payloadBuilders";
import type { DraftInjectionTarget } from "../../utils/resumeImport";
import styles from "./ResumeDraftInjectDialog.module.css";

/**
 * 経歴書ドラフトの案件を、既存の職歴・取引先へ**追加**するためのダイアログ（ADR-0026 決定 5）。
 *
 * 追加先はユーザーが明示的に選ぶ（機械が推測しない）。職務要約・自己PR は上書きせず、
 * 候補として提示し、ユーザーが個別に反映を選ぶ。職歴が 1 件も無い場合はセレクトを出さず、
 * 空の職歴・取引先を 1 件ずつ作って追加する旨だけを案内する。
 */
export function ResumeDraftInjectDialog({
  form,
  payload,
  onAppend,
  onApplyCandidate,
  onClose,
}: {
  form: CareerFormState;
  payload: ResumeDraftResultResponse;
  onAppend: (target: DraftInjectionTarget | null) => void;
  onApplyCandidate: (field: "career_summary" | "self_pr", value: string) => void;
  onClose: () => void;
}) {
  const [experienceIndex, setExperienceIndex] = useState(0);
  const [clientIndex, setClientIndex] = useState(0);

  const experiences = form.experiences;
  const hasExperience = experiences.length > 0;
  const clients = hasExperience ? (experiences[experienceIndex]?.clients ?? []) : [];
  const projects = payload.projects ?? [];
  // 職歴があるのに取引先が無い場合、追加先を確定できない（clientIndex 0 は範囲外になる）。
  // 追加先はユーザーが明示指定する契約なので、機械が取引先を作らず操作を止める
  const missingClientTarget = hasExperience && clients.length === 0;

  const handleExperienceChange = (index: number) => {
    setExperienceIndex(index);
    // 職歴を切り替えたら取引先の選択位置を先頭へ戻す（範囲外の指定を作らない）
    setClientIndex(0);
  };

  return (
    <div className={styles.overlay} onClick={onClose}>
      <div className={styles.dialog} onClick={(e) => e.stopPropagation()}>
        <h2 className={styles.heading}>{RESUME_DRAFT_MESSAGES.INJECT_HEADING}</h2>
        <p className={styles.description}>{RESUME_DRAFT_MESSAGES.INJECT_DESCRIPTION}</p>

        <h3 className={styles.sectionHeading}>
          {RESUME_DRAFT_MESSAGES.INJECT_PROJECTS_HEADING}
        </h3>
        <ul className={styles.projectList}>
          {projects.map((project) => (
            <li key={project.name}>{project.name}</li>
          ))}
        </ul>

        {hasExperience ? (
          <div className={styles.targets}>
            <label className={styles.field}>
              <span>{RESUME_DRAFT_MESSAGES.INJECT_EXPERIENCE_LABEL}</span>
              <select
                value={experienceIndex}
                onChange={(e) => handleExperienceChange(Number(e.target.value))}
              >
                {experiences.map((experience, index) => (
                  <option key={index} value={index}>
                    {experience.company.trim() || RESUME_DRAFT_MESSAGES.UNNAMED_EXPERIENCE}
                  </option>
                ))}
              </select>
            </label>
            <label className={styles.field}>
              <span>{RESUME_DRAFT_MESSAGES.INJECT_CLIENT_LABEL}</span>
              <select
                value={clientIndex}
                onChange={(e) => setClientIndex(Number(e.target.value))}
              >
                {clients.map((client, index) => (
                  <option key={index} value={index}>
                    {client.name.trim() || RESUME_DRAFT_MESSAGES.UNNAMED_CLIENT}
                  </option>
                ))}
              </select>
            </label>
          </div>
        ) : (
          <p className={styles.description}>{RESUME_DRAFT_MESSAGES.INJECT_NO_EXPERIENCE}</p>
        )}
        {missingClientTarget && (
          <p className={styles.description}>{RESUME_DRAFT_MESSAGES.INJECT_NO_CLIENT}</p>
        )}

        {/* 職務要約・自己PR は上書きになるため、候補として個別に反映させる */}
        {payload.career_summary && (
          <CandidateBlock
            heading={RESUME_DRAFT_MESSAGES.CAREER_SUMMARY_CANDIDATE}
            value={payload.career_summary}
            onApply={() => onApplyCandidate("career_summary", payload.career_summary ?? "")}
          />
        )}
        {payload.self_pr && (
          <CandidateBlock
            heading={RESUME_DRAFT_MESSAGES.SELF_PR_CANDIDATE}
            value={payload.self_pr}
            onApply={() => onApplyCandidate("self_pr", payload.self_pr ?? "")}
          />
        )}

        <div className={styles.actions}>
          <button
            type="button"
            onClick={() =>
              onAppend(hasExperience ? { experienceIndex, clientIndex } : null)
            }
            disabled={projects.length === 0 || missingClientTarget}
          >
            {RESUME_DRAFT_MESSAGES.INJECT_SUBMIT}
          </button>
          <button type="button" onClick={onClose}>
            {UI_MESSAGES.CONFIRM_CANCEL}
          </button>
        </div>
      </div>
    </div>
  );
}

/** 職務要約・自己PR の候補 1 件（本文プレビュー + 反映ボタン）。 */
function CandidateBlock({
  heading,
  value,
  onApply,
}: {
  heading: string;
  value: string;
  onApply: () => void;
}) {
  return (
    <div className={styles.candidate}>
      <h3 className={styles.sectionHeading}>{heading}</h3>
      <p className={styles.candidateBody}>{value}</p>
      <button type="button" onClick={onApply}>
        {RESUME_DRAFT_MESSAGES.APPLY_CANDIDATE}
      </button>
    </div>
  );
}
