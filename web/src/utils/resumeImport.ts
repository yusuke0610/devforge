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
import type { ResumeDraftResultResponse, ResumeImportResponse } from "../api/types";
import {
  blankCareerClient,
  blankCareerExperience,
  blankCareerProject,
  blankCareerProjectPeriod,
  blankCareerTechnologyStack,
} from "../constants";
import { INTERNAL_MESSAGES } from "../constants/messages";
import type {
  CareerClientForm,
  CareerExperienceForm,
  CareerFormState,
  CareerProjectForm,
} from "../payloadBuilders";

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
 * ドラフト注入の追加先。ユーザーが明示的に選んだ職歴・取引先を指す（ADR-0026 決定 5）。
 * `null` は「職歴が 1 件も無いので新しく作る」ケースにだけ使う。機械は追加先を推測しない。
 */
export type DraftInjectionTarget = {
  experienceIndex: number;
  clientIndex: number;
};

/** 名前も説明も空のプレースホルダ案件か（フォーム初期状態の空欄）。 */
function isBlankProject(project: CareerProjectForm): boolean {
  return !project.name.trim() && !project.description.trim();
}

/** ドラフトのプロジェクト 1 件をフォームの案件へ写す（欠落は blank 既定を継承）。 */
function toProjectForm(
  project: NonNullable<ResumeDraftResultResponse["projects"]>[number],
): CareerProjectForm {
  const base = structuredClone(blankCareerProject);
  const periods = project.periods ?? [];
  const stacks = project.technology_stacks ?? [];
  return {
    ...base,
    name: project.name ?? "",
    description: project.description ?? "",
    // role / phases / team はドラフトが生成しない（人間が埋める / ADR-0026 決定 1）
    role: project.role ?? "",
    phases: project.phases ?? [],
    team: { total: "", members: [] },
    periods: periods.length > 0 ? periods.map((p) => ({ ...p })) : [{ ...blankCareerProjectPeriod }],
    technology_stacks:
      stacks.length > 0 ? stacks.map((s) => ({ ...s })) : [{ ...blankCareerTechnologyStack }],
  };
}

/**
 * 採用したプロジェクトを、ユーザーが指定した職歴・取引先の案件リストへ**追加**する
 * （ADR-0026 決定 5）。
 *
 * 不変条件:
 * - **既存の experience / client を書き換えない**。置換は行わず追加だけを行う。
 * - **冪等**。同一 client 内に同名の案件が既にあれば追加しない（判定キーは案件名 =
 *   リポジトリ名）。同じドラフトを 2 回適用しても案件が増殖しない。
 * - **職務要約・自己PR・氏名は上書きしない**。これらは候補として別経路でユーザーが適用する。
 * - **部分適用しない**。追加先が不正なら例外を投げ、入力の state は一切変更しない
 *   （`current` を破壊せず新しいオブジェクトを組み立てて返す）。
 *
 * 職歴が 1 件も無い場合のみ、空の experience と client を 1 件ずつ作ってそこへ追加する
 * （会社名・事業内容は空のまま。プレースホルダを入れない / ADR-0026 決定 1 と整合）。
 */
export function appendResumeDraftProjects(
  current: CareerFormState,
  payload: ResumeDraftResultResponse,
  target: DraftInjectionTarget | null,
): CareerFormState {
  const draftProjects = payload.projects ?? [];
  if (draftProjects.length === 0) return current;

  // 職歴が無ければ空の受け皿を 1 件ずつ作る。ある場合は追加先の明示指定を必須にする。
  if (current.experiences.length === 0) {
    const experience: CareerExperienceForm = {
      ...structuredClone(blankCareerExperience),
      clients: [{ ...structuredClone(blankCareerClient), projects: [] }],
    };
    return {
      ...current,
      experiences: [appendInto(experience, 0, draftProjects)],
    };
  }

  if (!target) throw new Error(INTERNAL_MESSAGES.DRAFT_TARGET_REQUIRED);
  const { experienceIndex, clientIndex } = target;
  const experience = current.experiences[experienceIndex];
  if (!experience || !experience.clients[clientIndex]) {
    throw new Error(INTERNAL_MESSAGES.DRAFT_TARGET_OUT_OF_RANGE);
  }

  return {
    ...current,
    experiences: current.experiences.map((exp, index) =>
      index === experienceIndex ? appendInto(exp, clientIndex, draftProjects) : exp,
    ),
  };
}

/** 指定 client の案件リストへ、同名を除いたドラフト案件を追加した experience を返す。 */
function appendInto(
  experience: CareerExperienceForm,
  clientIndex: number,
  draftProjects: NonNullable<ResumeDraftResultResponse["projects"]>,
): CareerExperienceForm {
  return {
    ...experience,
    clients: experience.clients.map((client, index) =>
      index === clientIndex ? appendProjects(client, draftProjects) : client,
    ),
  };
}

/** client の案件リストにドラフト案件を冪等に追加する（同名はスキップ・空枠は詰める）。 */
function appendProjects(
  client: CareerClientForm,
  draftProjects: NonNullable<ResumeDraftResultResponse["projects"]>,
): CareerClientForm {
  // フォーム初期状態の空欄が残らないよう、名前も説明も空の枠は追加時に取り除く
  const existing = client.projects.filter((project) => !isBlankProject(project));
  const existingNames = new Set(existing.map((project) => project.name));
  const added = draftProjects
    .filter((project) => !existingNames.has(project.name ?? ""))
    .map(toProjectForm);
  return { ...client, projects: [...existing, ...added] };
}
