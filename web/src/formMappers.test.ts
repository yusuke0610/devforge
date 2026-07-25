import { describe, expect, it } from "vitest";

import type { ResumeDraftResultResponse, ResumeResponse } from "./api/types";
import { createInitialCareerForm, mapCareerResumeToForm } from "./formMappers";

describe("createInitialCareerForm", () => {
  it("空フォームは各配列に blank 要素を 1 件持つ", () => {
    const form = createInitialCareerForm();
    expect(form.full_name).toBe("");
    expect(form.experiences).toHaveLength(1);
    expect(form.qualifications).toHaveLength(1);
  });
});

describe("mapCareerResumeToForm", () => {
  it("保存済み経歴書（ResumeResponse）をフォーム state に写す", () => {
    const response = {
      full_name: "山田 太郎",
      email: "yamada@example.com",
      github_url: "https://github.com/yamada",
      career_summary: "要約",
      self_pr: "PR",
      experiences: [],
      qualifications: [],
      created_at: "2026-01-01T00:00:00Z",
      updated_at: "2026-01-02T00:00:00Z",
    } as unknown as ResumeResponse;
    const form = mapCareerResumeToForm(response);
    expect(form.full_name).toBe("山田 太郎");
    expect(form.email).toBe("yamada@example.com");
    // 空 experiences は blank 1 件へフォールバックする
    expect(form.experiences).toHaveLength(1);
  });

  it("ドラフト payload（timestamps 無し・email 空・深い職歴）を注入できる（#525 / ADR-0025）", () => {
    // ResumeDraftResultResponse は created_at/updated_at を持たない。#524 汎用化で
    // mapCareerResumeToForm が両方を受けられることの回帰テスト。
    const draft: ResumeDraftResultResponse = {
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
    };
    const form = mapCareerResumeToForm(draft);
    expect(form.full_name).toBe("ドラフト 太郎");
    expect(form.email).toBe("");
    expect(form.career_summary).toBe("生成した要約");
    expect(form.experiences).toHaveLength(1);
    expect(form.experiences[0].company).toBe("株式会社ドラフト");
    // 空 clients は blank 1 件へフォールバックする（深い構造の既定補完）
    expect(form.experiences[0].clients.length).toBeGreaterThan(0);
  });
});
