import { describe, expect, it } from "vitest";

import {
  blankCareerClient,
  blankCareerExperience,
  blankCareerProject,
} from "../constants";
import type { CareerExperienceForm, CareerFormState } from "../payloadBuilders";
import { collectCareerTexts } from "./collectCareerTexts";

/** 必要なフィールドだけ上書きした職歴を作る。 */
function makeExperience(overrides: Partial<CareerExperienceForm>): CareerExperienceForm {
  return { ...blankCareerExperience, ...overrides };
}

function makeForm(overrides: Partial<CareerFormState>): CareerFormState {
  return {
    full_name: "",
    career_summary: "",
    self_pr: "",
    experiences: [],
    qualifications: [],
    ...overrides,
  };
}

describe("collectCareerTexts", () => {
  it("トップレベルの職務要約・自己PRを収集する（氏名は対象外）", () => {
    const items = collectCareerTexts(
      makeForm({ full_name: "山田 太郎", career_summary: "要約です", self_pr: "PRです" }),
    );
    const ids = items.map((i) => i.id);
    expect(ids).toContain("career_summary");
    expect(ids).toContain("self_pr");
    expect(ids).not.toContain("full_name");
  });

  it("空白のみの値は除外する", () => {
    const items = collectCareerTexts(makeForm({ career_summary: "   ", self_pr: "" }));
    expect(items).toEqual([]);
  });

  it("非IT企業は description を収集し、clients は辿らない", () => {
    const exp = makeExperience({
      company: "非IT社",
      business_description: "事業",
      start_date: "2020-01",
      is_it_company: false,
      description: "詳細テキスト",
      clients: [{ ...blankCareerClient, has_client: true, name: "取引先A" }],
    });
    const items = collectCareerTexts(makeForm({ experiences: [exp] }));
    const ids = items.map((i) => i.id);
    expect(ids).toContain("experiences.0.company");
    expect(ids).toContain("experiences.0.business_description");
    expect(ids).toContain("experiences.0.description");
    // 非IT企業なので取引先配下は収集しない
    expect(ids.some((id) => id.includes("clients"))).toBe(false);
  });

  it("IT企業は取引先名・案件の自由記述を辿り、ラベルはパンくずになる", () => {
    const exp = makeExperience({
      company: "IT社",
      business_description: "事業",
      start_date: "2020-01",
      is_it_company: true,
      clients: [
        {
          ...blankCareerClient,
          has_client: true,
          name: "取引先A",
          projects: [
            {
              ...blankCareerProject,
              name: "案件X",
              role: "リーダー",
              description: "案件の説明",
            },
          ],
        },
      ],
    });
    const items = collectCareerTexts(makeForm({ experiences: [exp] }));
    const byId = new Map(items.map((i) => [i.id, i]));
    expect(byId.has("experiences.0.clients.0.name")).toBe(true);
    expect(byId.has("experiences.0.clients.0.projects.0.name")).toBe(true);
    expect(byId.has("experiences.0.clients.0.projects.0.role")).toBe(true);
    expect(byId.has("experiences.0.clients.0.projects.0.description")).toBe(true);
    // パンくず: 職歴1 ＞ 取引先1 ＞ プロジェクト1 ＞ 案件詳細
    expect(byId.get("experiences.0.clients.0.projects.0.description")?.label).toContain("職歴1");
    expect(byId.get("experiences.0.clients.0.projects.0.description")?.label).toContain(
      "プロジェクト1",
    );
  });

  it("休暇の取引先は休暇内容のみ収集する", () => {
    const exp = makeExperience({
      company: "IT社",
      business_description: "事業",
      start_date: "2020-01",
      is_it_company: true,
      clients: [
        {
          ...blankCareerClient,
          is_vacation: true,
          vacation_start_date: "2021-01",
          vacation_description: "育児休暇を取得",
        },
      ],
    });
    const items = collectCareerTexts(makeForm({ experiences: [exp] }));
    const ids = items.map((i) => i.id);
    expect(ids).toContain("experiences.0.clients.0.vacation_description");
    expect(ids.some((id) => id.includes("projects"))).toBe(false);
  });

  it("資格は名称を収集する", () => {
    const items = collectCareerTexts(
      makeForm({ qualifications: [{ acquired_date: "2020-01", name: "基本情報技術者" }] }),
    );
    expect(items.map((i) => i.id)).toContain("qualifications.0.name");
  });
});
