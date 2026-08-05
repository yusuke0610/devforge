import { describe, expect, it } from "vitest";

import { blankCareerClient, blankCareerExperience, blankCareerProject } from "../constants";
import { createInitialCareerForm } from "../formMappers";
import type { CareerFormState } from "../payloadBuilders";
import type { ResumeDraftResultResponse, ResumeImportResponse } from "../api/types";
import {
  appendResumeDraftProjects,
  applyResumeImportToForm,
  hasCareerFormContent,
} from "./resumeImport";

/** 抽出 payload のひな型（テストで一部だけ差し替える）。 */
function importPayload(overrides: Partial<ResumeImportResponse> = {}): ResumeImportResponse {
  return {
    full_name: "",
    career_summary: "",
    self_pr: "",
    experiences: [],
    ...overrides,
  };
}

describe("hasCareerFormContent", () => {
  it("初期（空）フォームは false", () => {
    expect(hasCareerFormContent(createInitialCareerForm())).toBe(false);
  });

  it("email / github_url など任意の編集フィールドに入力があれば true", () => {
    expect(
      hasCareerFormContent({ ...createInitialCareerForm(), email: "a@example.com" }),
    ).toBe(true);
    expect(
      hasCareerFormContent({ ...createInitialCareerForm(), github_url: "https://github.com/x" }),
    ).toBe(true);
  });

  it("experiences / qualifications の中身があれば true（blank の配列長では判定しない）", () => {
    const withExp: CareerFormState = {
      ...createInitialCareerForm(),
      experiences: [{ ...blankCareerExperience, company: "会社" }],
    };
    expect(hasCareerFormContent(withExp)).toBe(true);
  });
});

describe("applyResumeImportToForm", () => {
  it("抽出された非空の見出しフィールドを現フォームに上書きする", () => {
    const current = createInitialCareerForm();
    const result = applyResumeImportToForm(
      current,
      importPayload({
        full_name: "山田 太郎",
        career_summary: "バックエンドエンジニアとして 5 年。",
        self_pr: "保守性を重視。",
      }),
    );
    expect(result.full_name).toBe("山田 太郎");
    expect(result.career_summary).toBe("バックエンドエンジニアとして 5 年。");
    expect(result.self_pr).toBe("保守性を重視。");
  });

  it("抽出が空のフィールドは現フォームの既存値を保持する", () => {
    const current: CareerFormState = {
      ...createInitialCareerForm(),
      full_name: "既存 名前",
      career_summary: "既存の要約",
    };
    const result = applyResumeImportToForm(
      current,
      importPayload({ full_name: "", career_summary: "   ", self_pr: "新しい自己PR" }),
    );
    // 空・空白のみは上書きしない
    expect(result.full_name).toBe("既存 名前");
    expect(result.career_summary).toBe("既存の要約");
    // 非空は上書きする
    expect(result.self_pr).toBe("新しい自己PR");
  });

  it("抽出で得られない email / github_url / qualifications は現フォームを保持する", () => {
    const current: CareerFormState = {
      ...createInitialCareerForm(),
      email: "keep@example.com",
      github_url: "https://github.com/keep",
    };
    const result = applyResumeImportToForm(current, importPayload({ full_name: "太郎" }));
    expect(result.email).toBe("keep@example.com");
    expect(result.github_url).toBe("https://github.com/keep");
    expect(result.qualifications).toEqual(current.qualifications);
  });

  it("抽出職歴があれば experiences をフラット値から構築して置き換える", () => {
    const current = createInitialCareerForm();
    const result = applyResumeImportToForm(
      current,
      importPayload({
        experiences: [
          {
            company: "株式会社サンプル",
            business_description: "受託開発",
            start_date: "2020-04",
            end_date: "2023-03",
            description: "API 開発を担当。",
          },
          {
            company: "在籍中カンパニー",
            business_description: "自社開発",
            start_date: "2023-04",
            end_date: "",
            description: "設計を担当。",
          },
        ],
      }),
    );
    expect(result.experiences).toHaveLength(2);
    const [first, second] = result.experiences;
    expect(first.company).toBe("株式会社サンプル");
    expect(first.business_description).toBe("受託開発");
    expect(first.start_date).toBe("2020-04");
    expect(first.end_date).toBe("2023-03");
    expect(first.description).toBe("API 開発を担当。");
    // end_date 空 = 在籍中フラグを立てる
    expect(first.is_current).toBe(false);
    expect(second.is_current).toBe(true);
    // 深いネストは blank の既定（clients が 1 件用意される）を継承する
    expect(first.clients.length).toBeGreaterThan(0);
  });

  it("抽出職歴が空なら現フォームの experiences を保持する", () => {
    const current: CareerFormState = {
      ...createInitialCareerForm(),
      experiences: [{ ...blankCareerExperience, company: "既存カンパニー" }],
    };
    const result = applyResumeImportToForm(current, importPayload({ full_name: "太郎" }));
    expect(result.experiences).toHaveLength(1);
    expect(result.experiences[0].company).toBe("既存カンパニー");
  });
});

describe("appendResumeDraftProjects", () => {
  function draftPayload(
    overrides: Partial<ResumeDraftResultResponse> = {},
  ): ResumeDraftResultResponse {
    return {
      full_name: "ドラフト 太郎",
      email: "",
      github_url: "https://github.com/draft",
      career_summary: "生成した要約",
      self_pr: "生成した自己PR",
      projects: [
        {
          name: "devforge",
          description: "経歴書作成ツール",
          role: "",
          phases: [],
          periods: [{ start_date: "2024-01", end_date: "", is_current: true }],
          team: { total: "", members: [] },
          technology_stacks: [{ category: "language", name: "Python" }],
        },
      ] as unknown as ResumeDraftResultResponse["projects"],
      ...overrides,
    };
  }

  /** 職歴 1 社（取引先 1 件・案件 1 件）を持つフォームを作る。 */
  function formWithExperience(company: string, projectNames: string[] = []): CareerFormState {
    return {
      ...createInitialCareerForm(),
      experiences: [
        {
          ...structuredClone(blankCareerExperience),
          company,
          clients: [
            {
              ...structuredClone(blankCareerClient),
              name: "取引先A",
              projects: projectNames.map((name) => ({
                ...structuredClone(blankCareerProject),
                name,
              })),
            },
          ],
        },
      ],
    };
  }

  it("既存の experiences を保持したまま、指定した client の projects へ追加する", () => {
    const current = formWithExperience("既存カンパニー", ["既存案件"]);
    const result = appendResumeDraftProjects(current, draftPayload(), {
      experienceIndex: 0,
      clientIndex: 0,
    });

    // 職歴は置換されない（ADR-0026 決定 5 の中心的な不変条件）
    expect(result.experiences).toHaveLength(1);
    expect(result.experiences[0].company).toBe("既存カンパニー");
    expect(result.experiences[0].clients[0].name).toBe("取引先A");
    expect(result.experiences[0].clients[0].projects.map((p) => p.name)).toEqual([
      "既存案件",
      "devforge",
    ]);
  });

  it("職務要約・自己PR・氏名は上書きしない（候補として別経路で適用する）", () => {
    const current: CareerFormState = {
      ...formWithExperience("既存カンパニー"),
      full_name: "既存 太郎",
      career_summary: "既存の要約",
      self_pr: "既存の自己PR",
    };
    const result = appendResumeDraftProjects(current, draftPayload(), {
      experienceIndex: 0,
      clientIndex: 0,
    });

    expect(result.full_name).toBe("既存 太郎");
    expect(result.career_summary).toBe("既存の要約");
    expect(result.self_pr).toBe("既存の自己PR");
  });

  it("同じ payload を 2 回適用しても project が重複しない（冪等）", () => {
    const current = formWithExperience("既存カンパニー");
    const target = { experienceIndex: 0, clientIndex: 0 };
    const once = appendResumeDraftProjects(current, draftPayload(), target);
    const twice = appendResumeDraftProjects(once, draftPayload(), target);

    expect(twice.experiences[0].clients[0].projects.map((p) => p.name)).toEqual(["devforge"]);
  });

  it("同名 project が既にあれば追加しない（判定キーは project 名）", () => {
    const current = formWithExperience("既存カンパニー", ["devforge"]);
    const result = appendResumeDraftProjects(current, draftPayload(), {
      experienceIndex: 0,
      clientIndex: 0,
    });
    expect(result.experiences[0].clients[0].projects).toHaveLength(1);
  });

  it("experience が 1 件も無ければ空の experience と client を作ってそこへ追加する", () => {
    const current: CareerFormState = { ...createInitialCareerForm(), experiences: [] };
    const result = appendResumeDraftProjects(current, draftPayload(), null);

    expect(result.experiences).toHaveLength(1);
    // 会社名・事業内容はプレースホルダを入れず空のまま（ADR-0026 決定 1 と整合）
    expect(result.experiences[0].company).toBe("");
    expect(result.experiences[0].business_description).toBe("");
    expect(result.experiences[0].clients).toHaveLength(1);
    expect(result.experiences[0].clients[0].projects.map((p) => p.name)).toEqual(["devforge"]);
  });

  it("追加先が空の案件枠だけなら、その空枠を使う（空欄が残らない）", () => {
    const current = createInitialCareerForm();
    const result = appendResumeDraftProjects(current, draftPayload(), {
      experienceIndex: 0,
      clientIndex: 0,
    });
    expect(result.experiences[0].clients[0].projects.map((p) => p.name)).toEqual(["devforge"]);
  });

  it("他の職歴・取引先は書き換えない", () => {
    const current: CareerFormState = {
      ...createInitialCareerForm(),
      experiences: [
        formWithExperience("A社").experiences[0],
        formWithExperience("B社", ["B案件"]).experiences[0],
      ],
    };
    const result = appendResumeDraftProjects(current, draftPayload(), {
      experienceIndex: 1,
      clientIndex: 0,
    });

    expect(result.experiences[0]).toEqual(current.experiences[0]);
    expect(result.experiences[1].clients[0].projects.map((p) => p.name)).toEqual([
      "B案件",
      "devforge",
    ]);
  });

  it("入力のフォーム state を破壊しない（部分適用を作らない）", () => {
    const current = formWithExperience("既存カンパニー", ["既存案件"]);
    const snapshot = structuredClone(current);
    appendResumeDraftProjects(current, draftPayload(), { experienceIndex: 0, clientIndex: 0 });
    expect(current).toEqual(snapshot);
  });

  it("追加先の指定が範囲外なら例外を投げ、フォーム state は変更しない", () => {
    const current = formWithExperience("既存カンパニー");
    const snapshot = structuredClone(current);
    expect(() =>
      appendResumeDraftProjects(current, draftPayload(), { experienceIndex: 9, clientIndex: 0 }),
    ).toThrow();
    expect(current).toEqual(snapshot);
  });

  it("projects が空なら何も追加しない", () => {
    const current = formWithExperience("既存カンパニー", ["既存案件"]);
    const result = appendResumeDraftProjects(current, draftPayload({ projects: [] }), {
      experienceIndex: 0,
      clientIndex: 0,
    });
    expect(result.experiences[0].clients[0].projects.map((p) => p.name)).toEqual(["既存案件"]);
  });
});
