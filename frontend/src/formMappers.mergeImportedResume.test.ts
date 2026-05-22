import { describe, expect, it } from "vitest";

import { blankCareerExperience } from "./constants";
import { createInitialCareerForm, mergeImportedResume } from "./formMappers";
import type { CareerFormState } from "./payloadBuilders";
import type { CareerResumePayload } from "./types";

const blankImported: CareerResumePayload = {
  full_name: "",
  career_summary: "",
  self_pr: "",
  experiences: [],
  qualifications: [],
};

const sampleImported: CareerResumePayload = {
  full_name: "山田 太郎",
  career_summary: "バックエンドエンジニア",
  self_pr: "API 設計が得意",
  experiences: [
    {
      company: "株式会社A",
      business_description: "受託開発",
      start_date: "2020-04",
      end_date: "2023-03",
      is_current: false,
      employee_count: "50名",
      capital: "1000万円",
      clients: [],
    },
  ],
  qualifications: [
    { acquired_date: "2021-06", name: "AWS SAA" },
  ],
};

describe("mergeImportedResume", () => {
  it("初期フォームに対してインポートで完全に置換する", () => {
    const existing = createInitialCareerForm();
    const result = mergeImportedResume(existing, sampleImported);

    expect(result.full_name).toBe("山田 太郎");
    expect(result.career_summary).toBe("バックエンドエンジニア");
    expect(result.self_pr).toBe("API 設計が得意");
    expect(result.experiences).toHaveLength(1);
    expect(result.experiences[0].company).toBe("株式会社A");
    expect(result.qualifications).toHaveLength(1);
    expect(result.qualifications[0].name).toBe("AWS SAA");
  });

  it("既存フォームの文字列フィールドは上書きされない", () => {
    const existing: CareerFormState = {
      ...createInitialCareerForm(),
      full_name: "既存の名前",
      career_summary: "既存サマリー",
      self_pr: "既存自己PR",
    };
    const result = mergeImportedResume(existing, sampleImported);

    expect(result.full_name).toBe("既存の名前");
    expect(result.career_summary).toBe("既存サマリー");
    expect(result.self_pr).toBe("既存自己PR");
  });

  it("既存に職務経歴がある場合はインポートを追記する", () => {
    const existing: CareerFormState = {
      ...createInitialCareerForm(),
      experiences: [
        {
          ...blankCareerExperience,
          company: "株式会社既存",
          business_description: "既存事業",
          start_date: "2018-04",
        },
      ],
    };
    const result = mergeImportedResume(existing, sampleImported);

    expect(result.experiences).toHaveLength(2);
    expect(result.experiences[0].company).toBe("株式会社既存");
    expect(result.experiences[1].company).toBe("株式会社A");
  });

  it("既存に資格がある場合はインポートを追記する", () => {
    const existing: CareerFormState = {
      ...createInitialCareerForm(),
      qualifications: [{ acquired_date: "2019-04", name: "基本情報技術者" }],
    };
    const result = mergeImportedResume(existing, sampleImported);

    expect(result.qualifications).toHaveLength(2);
    expect(result.qualifications[0].name).toBe("基本情報技術者");
    expect(result.qualifications[1].name).toBe("AWS SAA");
  });

  it("インポートデータが空の場合は既存フォームを返す", () => {
    const existing: CareerFormState = {
      ...createInitialCareerForm(),
      full_name: "既存の名前",
    };
    const result = mergeImportedResume(existing, blankImported);

    expect(result.full_name).toBe("既存の名前");
    expect(result.experiences).toEqual(existing.experiences);
  });

  it("空フィールドはインポートで埋まる（非破壊）", () => {
    const existing: CareerFormState = {
      ...createInitialCareerForm(),
      full_name: "",
      career_summary: "",
    };
    const result = mergeImportedResume(existing, sampleImported);

    expect(result.full_name).toBe("山田 太郎");
    expect(result.career_summary).toBe("バックエンドエンジニア");
  });
});
