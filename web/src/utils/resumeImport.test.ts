import { describe, expect, it } from "vitest";

import { blankCareerExperience } from "../constants";
import { createInitialCareerForm } from "../formMappers";
import type { CareerFormState } from "../payloadBuilders";
import type { ResumeDraftResultResponse, ResumeImportResponse } from "../api/types";
import {
  applyResumeDraftToForm,
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

describe("applyResumeDraftToForm", () => {
  function draftPayload(overrides: Partial<ResumeDraftResultResponse> = {}): ResumeDraftResultResponse {
    return {
      full_name: "ドラフト 太郎",
      email: "",
      github_url: "https://github.com/draft",
      career_summary: "生成した要約",
      self_pr: "生成した自己PR",
      experiences: [
        {
          company: "株式会社ドラフト",
          business_description: "自社開発",
          start_date: "2020-04",
          end_date: "",
          is_current: true,
          clients: [],
        },
      ] as unknown as ResumeDraftResultResponse["experiences"],
      qualifications: [],
      ...overrides,
    };
  }

  it("生成が提供するフィールドは上書きする", () => {
    const current = createInitialCareerForm();
    const result = applyResumeDraftToForm(current, draftPayload());
    expect(result.full_name).toBe("ドラフト 太郎");
    expect(result.career_summary).toBe("生成した要約");
    expect(result.self_pr).toBe("生成した自己PR");
    expect(result.experiences[0].company).toBe("株式会社ドラフト");
    expect(result.github_url).toBe("https://github.com/draft");
  });

  it("生成が提供しない email は現フォーム値を保持する（#524 共通ルール）", () => {
    const current: CareerFormState = {
      ...createInitialCareerForm(),
      email: "keep@example.com",
    };
    const result = applyResumeDraftToForm(current, draftPayload({ email: "" }));
    expect(result.email).toBe("keep@example.com");
  });

  it("生成が資格を提供しない場合は現フォームの資格を保持する", () => {
    const current: CareerFormState = {
      ...createInitialCareerForm(),
      qualifications: [{ name: "基本情報技術者", acquired_date: "2019-04" }],
    };
    const result = applyResumeDraftToForm(current, draftPayload({ qualifications: [] }));
    expect(result.qualifications).toHaveLength(1);
    expect(result.qualifications[0].name).toBe("基本情報技術者");
  });
});
