/**
 * 職務経歴フォーム（`CareerFormState`）から校正対象のテキスト項目を平坦化する純粋関数。
 *
 * ## 方針
 * - 校正は「保存される自由記述」を対象にする。日付・数値・真偽・選択値（技術スタック等）は除外する。
 * - 収集条件は `payloadBuilders.ts` の包含判定（`experienceIncluded` / `clientIncluded` /
 *   `projectIncluded`）を再利用し、payload に載らない（=保存されない）行は校正しない。
 * - `id`（ドット区切りパス）と `label`（パンくず）は `utils/careerDiff.ts` の体系に揃える。
 *   そうすることで、ダイアログのサイドバーで「変更点」と「校正の指摘」が同じラベルで並ぶ。
 *
 * 空白のみの値は除外する（指摘の意味がないため）。
 */
import { CAREER_DIFF_LABELS as L, DIFF_DIALOG_MESSAGES as D } from "../constants/messages";
import {
  clientIncluded,
  experienceIncluded,
  projectIncluded,
  type CareerFormState,
} from "../payloadBuilders";
import type { CareerTextItem } from "./types";

/** ラベルセグメントを区切り文字で連結する（careerDiff の joinLabel と同一）。 */
function joinLabel(segments: string[]): string {
  return segments.join(D.PATH_SEPARATOR);
}

/** 値が非空（trim 後）なら 1 項目 push する。 */
function pushText(
  items: CareerTextItem[],
  id: string,
  labelSegments: string[],
  value: string,
): void {
  if (!value.trim()) return;
  items.push({ id, label: joinLabel(labelSegments), value });
}

/**
 * フォームを走査し、校正対象テキストを順番（フォームの並び）どおりに収集する。
 */
export function collectCareerTexts(form: CareerFormState): CareerTextItem[] {
  const items: CareerTextItem[] = [];

  // 並び順は PDF レイアウト（職務要約 → 職務経歴 → 資格 → 自己PR）に合わせ、
  // 左右ペイン・変更点リストと校正セクションの縦順を一致させる。
  pushText(items, "career_summary", [L.CAREER_SUMMARY], form.career_summary);

  form.experiences.forEach((exp, expIndex) => {
    if (!experienceIncluded(exp)) return;
    const expSeg = [`${L.EXPERIENCE}${expIndex + 1}`];
    const expPath = `experiences.${expIndex}`;

    pushText(items, `${expPath}.company`, [...expSeg, L.COMPANY], exp.company);
    pushText(
      items,
      `${expPath}.business_description`,
      [...expSeg, L.BUSINESS_DESCRIPTION],
      exp.business_description,
    );

    if (!exp.is_it_company) {
      pushText(items, `${expPath}.description`, [...expSeg, L.DESCRIPTION], exp.description);
      return;
    }

    exp.clients.forEach((client, clientIndex) => {
      if (!clientIncluded(client)) return;
      const clientSeg = [...expSeg, `${L.CLIENT}${clientIndex + 1}`];
      const clientPath = `${expPath}.clients.${clientIndex}`;

      if (client.is_vacation) {
        pushText(
          items,
          `${clientPath}.vacation_description`,
          [...clientSeg, L.VACATION_DESCRIPTION],
          client.vacation_description,
        );
        return;
      }

      if (client.has_client) {
        pushText(items, `${clientPath}.name`, [...clientSeg, L.CLIENT_NAME], client.name);
      }

      client.projects.forEach((proj, projIndex) => {
        if (!projectIncluded(proj)) return;
        const projSeg = [...clientSeg, `${L.PROJECT}${projIndex + 1}`];
        const projPath = `${clientPath}.projects.${projIndex}`;

        pushText(items, `${projPath}.name`, [...projSeg, L.PROJECT_NAME], proj.name);
        pushText(items, `${projPath}.role`, [...projSeg, L.ROLE], proj.role);
        pushText(items, `${projPath}.description`, [...projSeg, L.PROJECT_DESCRIPTION], proj.description);
      });
    });
  });

  form.qualifications.forEach((qual, index) => {
    const qualSeg = [`${L.QUALIFICATION}${index + 1}`];
    pushText(items, `qualifications.${index}.name`, [...qualSeg, L.QUALIFICATION_NAME], qual.name);
  });

  // 自己PR は PDF 上で最後に来るため末尾に収集する。
  pushText(items, "self_pr", [L.SELF_PR], form.self_pr);

  return items;
}
