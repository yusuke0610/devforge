import { describe, expect, it } from "vitest";

import type { CareerFormState } from "../payloadBuilders";
import { applyAgentOperations, buildAgentResumeContext } from "./agentOperations";

/** テスト用の最小フォーム state（project 1 件入り）。 */
function makeForm(): CareerFormState {
  return {
    full_name: "山田 太郎",
    email: "yamada@example.com",
    github_url: "",
    career_summary: "現在の職務要約",
    self_pr: "現在の自己PR",
    experiences: [
      {
        company: "株式会社A",
        business_description: "受託開発",
        start_date: "2020-04",
        end_date: "",
        is_current: true,
        employee_count: "",
        capital: "",
        capital_unit: "千万円",
        is_it_company: true,
        description: "",
        clients: [
          {
            name: "クライアントX",
            has_client: true,
            is_vacation: false,
            vacation_start_date: "",
            vacation_end_date: "",
            vacation_is_current: false,
            vacation_description: "",
            projects: [
              {
                name: "ECサイト構築",
                periods: [],
                role: "現在の役割",
                description: "現在の詳細",
                team: { total: "", members: [] },
                technology_stacks: [{ category: "language", name: "Python" }],
                phases: ["実装"],
              },
            ],
          },
        ],
      },
    ],
    qualifications: [],
  };
}

describe("buildAgentResumeContext", () => {
  it("フォーム state から LLM コンテキストに必要な項目だけを抽出する", () => {
    const context = buildAgentResumeContext(makeForm());
    expect(context.career_summary).toBe("現在の職務要約");
    expect(context.self_pr).toBe("現在の自己PR");
    const project = context.experiences?.[0]?.clients?.[0]?.projects?.[0];
    expect(project?.name).toBe("ECサイト構築");
    expect(project?.description).toBe("現在の詳細");
    // 個人情報（氏名・メール）はコンテキストに含めない
    expect(JSON.stringify(context)).not.toContain("yamada@example.com");
  });
});

describe("applyAgentOperations", () => {
  it("career_summary スコープの operation をトップレベルに適用する", () => {
    const next = applyAgentOperations(makeForm(), "career_summary", null, [
      { field: "career_summary", value: "改善された職務要約" },
    ]);
    expect(next.career_summary).toBe("改善された職務要約");
    expect(next.self_pr).toBe("現在の自己PR");
  });

  it("project スコープの description / role を target の project にだけ適用する", () => {
    const target = { experience_index: 0, client_index: 0, project_index: 0 };
    const next = applyAgentOperations(makeForm(), "project", target, [
      { field: "description", value: "改善された詳細" },
      { field: "role", value: "改善された役割" },
    ]);
    const project = next.experiences[0].clients[0].projects[0];
    expect(project.description).toBe("改善された詳細");
    expect(project.role).toBe("改善された役割");
    // 他フィールドは変更しない
    expect(project.name).toBe("ECサイト構築");
  });

  it("スコープと一致しない field の operation は無視する", () => {
    const form = makeForm();
    const next = applyAgentOperations(form, "self_pr", null, [
      { field: "career_summary", value: "適用されない" },
    ]);
    expect(next.career_summary).toBe("現在の職務要約");
  });

  it("target が範囲外なら何も変更しない", () => {
    const form = makeForm();
    const target = { experience_index: 0, client_index: 0, project_index: 9 };
    const next = applyAgentOperations(form, "project", target, [
      { field: "description", value: "適用されない" },
    ]);
    expect(next).toEqual(form);
  });

  it("元の state を破壊しない（イミュータブル）", () => {
    const form = makeForm();
    applyAgentOperations(form, "career_summary", null, [
      { field: "career_summary", value: "変更後" },
    ]);
    expect(form.career_summary).toBe("現在の職務要約");
  });
});
