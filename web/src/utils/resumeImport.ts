/**
 * PDF 経歴書の抽出結果（{@link ResumeImportResponse}）をキャリアフォーム state へ注入する
 * 決定論変換（ADR-0024 / #524・#528）。
 *
 * 方針（「欠落は既存値保持」/ #524）:
 * - 見出しフィールド（full_name / career_summary / self_pr）は**抽出値が非空のときだけ**
 *   上書きし、空・空白のみなら現フォームの値を保持する。
 * - email / github_url / qualifications は抽出対象外（v1）なので常に現フォームを保持する。
 * - experiences は**抽出に 1 件でもあれば**フラット値から構築して置き換え、無ければ現状維持。
 *   深いネスト（clients / projects / periods / technology_stacks）は blank の既定を継承し、
 *   ユーザーがフォームで追記する。
 *
 * 破壊は呼び出し側（アップロード UI）が「入力途中なら確認ダイアログ」で防ぐ。本関数は純変換。
 */
import type { ResumeImportResponse } from "../api/types";
import { blankCareerExperience } from "../constants";
import { mapCareerResumeToForm, type ResumeFormSource } from "../formMappers";
import type { CareerExperienceForm, CareerFormState } from "../payloadBuilders";

type ImportExperience = NonNullable<ResumeImportResponse["experiences"]>[number];

/**
 * キャリアフォームにユーザーの意味のある入力があるかを判定する（全編集フィールド横断）。
 *
 * PDF 自動入力パネルの表示可否（空フォームのみ）と、上書き確認の要否の両方で使う単一述語。
 * 空フォームは experiences / qualifications に blank 要素を 1 件持つため、配列長ではなく
 * 各フィールドの中身（trim 後の非空）で判定する。
 */
export function hasCareerFormContent(form: CareerFormState): boolean {
  return Boolean(
    form.full_name.trim() ||
      form.email.trim() ||
      form.github_url.trim() ||
      form.career_summary.trim() ||
      form.self_pr.trim() ||
      form.experiences.some(
        (e) =>
          e.company.trim() || e.business_description.trim() || e.description.trim(),
      ) ||
      form.qualifications.some((q) => q.name.trim() || q.acquired_date.trim()),
  );
}

/** 抽出値が非空（空白のみでない）ならそれを、そうでなければ現行値を返す。 */
function pick(extracted: string | undefined, current: string): string {
  return (extracted ?? "").trim() ? (extracted as string) : current;
}

/** フラットな抽出職歴 1 件を、深いネストは blank 既定のままにした experience へ写す。 */
function toExperienceForm(exp: ImportExperience): CareerExperienceForm {
  // 各 experience が blank のネスト構造を共有しないよう深いコピーを作る
  const base = structuredClone(blankCareerExperience);
  const endDate = exp.end_date ?? "";
  return {
    ...base,
    company: exp.company ?? "",
    business_description: exp.business_description ?? "",
    start_date: exp.start_date ?? "",
    end_date: endDate,
    // 終了日が空 = 在籍中とみなす
    is_current: endDate.trim() === "",
    description: exp.description ?? "",
  };
}

export function applyResumeImportToForm(
  current: CareerFormState,
  payload: ResumeImportResponse,
): CareerFormState {
  const extractedExperiences = payload.experiences ?? [];
  return {
    ...current,
    full_name: pick(payload.full_name, current.full_name),
    career_summary: pick(payload.career_summary, current.career_summary),
    self_pr: pick(payload.self_pr, current.self_pr),
    experiences:
      extractedExperiences.length > 0
        ? extractedExperiences.map(toExperienceForm)
        : current.experiences,
  };
}

/**
 * 経歴書ドラフト/保存済み経歴書の payload をキャリアフォームへ注入する（#524 共通ルール / ADR-0025）。
 *
 * `mapCareerResumeToForm` で全体を写した上で、**全フィールドに一様に preserve-if-empty を適用する**
 * （PDF インポートの {@link applyResumeImportToForm} と同じ「欠落/空は既存値保持」不変条件）。
 * スカラーは値が非空なら上書き・空なら現フォーム保持、配列は中身の有無で置換/維持する。特定
 * フィールドを無条件に上書きしないため、生成が想定外に空を返してもユーザーの入力を消さない。
 * 実際のドラフトは full_name / career_summary / self_pr / experiences / github_url を常に提供する
 * ため上書きされ、email と資格は提供しない（空）ため現フォーム値が残る（ADR-0025）。
 */
export function applyResumeDraftToForm(
  current: CareerFormState,
  payload: ResumeFormSource,
): CareerFormState {
  const mapped = mapCareerResumeToForm(payload);
  // 全フィールドに一様の preserve-if-empty を適用する（フィールド名で固定分岐しない）。
  // スカラーは値が非空なら上書き・空なら現フォーム保持。配列は中身の有無で置換/維持。
  const pick = (mappedValue: string, currentValue: string): string =>
    mappedValue.trim() ? mappedValue : currentValue;
  const mappedHasExperiences = mapped.experiences.some(
    (e) => e.company.trim() || e.business_description.trim() || e.description.trim(),
  );
  const mappedHasQualifications = mapped.qualifications.some(
    (q) => q.name.trim() || q.acquired_date.trim(),
  );
  return {
    full_name: pick(mapped.full_name, current.full_name),
    email: pick(mapped.email, current.email),
    github_url: pick(mapped.github_url, current.github_url),
    career_summary: pick(mapped.career_summary, current.career_summary),
    self_pr: pick(mapped.self_pr, current.self_pr),
    experiences: mappedHasExperiences ? mapped.experiences : current.experiences,
    qualifications: mappedHasQualifications ? mapped.qualifications : current.qualifications,
  };
}
