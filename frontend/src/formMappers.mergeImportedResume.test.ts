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
  it("初期フォームに対してインポートで完全に反映する", () => {
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

  it("既存フォームの文字列フィールドも imported の値で上書きされる", () => {
    const existing: CareerFormState = {
      ...createInitialCareerForm(),
      full_name: "既存の名前",
      career_summary: "既存サマリー",
      self_pr: "既存自己PR",
    };
    const result = mergeImportedResume(existing, sampleImported);

    expect(result.full_name).toBe("山田 太郎");
    expect(result.career_summary).toBe("バックエンドエンジニア");
    expect(result.self_pr).toBe("API 設計が得意");
  });

  it("既存に職務経歴があってもインポートで置換する（追記しない）", () => {
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

    expect(result.experiences).toHaveLength(1);
    expect(result.experiences[0].company).toBe("株式会社A");
  });

  it("既存に資格があってもインポートで置換する（追記しない）", () => {
    const existing: CareerFormState = {
      ...createInitialCareerForm(),
      qualifications: [{ acquired_date: "2019-04", name: "基本情報技術者" }],
    };
    const result = mergeImportedResume(existing, sampleImported);

    expect(result.qualifications).toHaveLength(1);
    expect(result.qualifications[0].name).toBe("AWS SAA");
  });

  it("インポートデータが空の場合は既存フォームを維持する（消さない）", () => {
    const existing: CareerFormState = {
      ...createInitialCareerForm(),
      full_name: "既存の名前",
      qualifications: [{ acquired_date: "2019-04", name: "基本情報技術者" }],
    };
    const result = mergeImportedResume(existing, blankImported);

    expect(result.full_name).toBe("既存の名前");
    expect(result.experiences).toEqual(existing.experiences);
    expect(result.qualifications).toEqual(existing.qualifications);
  });

  it("imported が空の文字列フィールドは既存の入力を維持する（部分フォールバック）", () => {
    const existing: CareerFormState = {
      ...createInitialCareerForm(),
      career_summary: "既存サマリー",
      self_pr: "既存自己PR",
    };
    const partialImported: CareerResumePayload = {
      ...blankImported,
      full_name: "新しい名前",
    };
    const result = mergeImportedResume(existing, partialImported);

    // imported に値がある full_name は上書き、空の項目は既存を維持
    expect(result.full_name).toBe("新しい名前");
    expect(result.career_summary).toBe("既存サマリー");
    expect(result.self_pr).toBe("既存自己PR");
  });
});
