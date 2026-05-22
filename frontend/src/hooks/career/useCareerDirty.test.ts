import { renderHook } from "@testing-library/react";
import { describe, it, expect } from "vitest";

import {
  blankCareerClient,
  blankCareerExperience,
  blankCareerProject,
  blankCareerTechnologyStack,
  blankResumeQualification,
} from "../../constants";
import type { CareerFormState } from "../../payloadBuilders";
import { useCareerDirty } from "./useCareerDirty";

/** 標準的なフォーム初期状態を作るヘルパ */
function buildForm(overrides: Partial<CareerFormState> = {}): CareerFormState {
  return {
    full_name: "山田 太郎",
    career_summary: "サマリー",
    self_pr: "自己PR",
    experiences: [
      {
        ...blankCareerExperience,
        company: "株式会社A",
        business_description: "受託開発",
        start_date: "2020-04",
        clients: [
          {
            ...blankCareerClient,
            projects: [
              {
                ...blankCareerProject,
                name: "プロジェクトX",
                technology_stacks: [{ ...blankCareerTechnologyStack }],
              },
            ],
          },
        ],
      },
    ],
    qualifications: [
      { ...blankResumeQualification, name: "基本情報", acquired_date: "2021-04-01" },
    ],
    ...overrides,
  };
}

describe("useCareerDirty", () => {
  it("baseline が null の場合はすべて false を返す（未ロード）", () => {
    const form = buildForm();
    const { result } = renderHook(() => useCareerDirty(form, null));
    expect(result.current.any).toBe(false);
    expect(result.current.experiencesAny).toBe(false);
    expect(result.current.qualificationsAny).toBe(false);
    // 配下クライアントとプロジェクトも form と同じ shape を保ち、各 any は false
    expect(result.current.experiences[0].clients[0].projects).toHaveLength(
      form.experiences[0].clients[0].projects.length,
    );
    expect(result.current.experiences[0].clients[0].projects[0].any).toBe(false);
  });

  it("form と baseline が同一なら dirty なし", () => {
    const form = buildForm();
    const baseline = buildForm();
    const { result } = renderHook(() => useCareerDirty(form, baseline));
    expect(result.current.any).toBe(false);
    expect(result.current.full_name).toBe(false);
    expect(result.current.experiences[0].any).toBe(false);
    expect(result.current.qualifications[0].self).toBe(false);
  });

  it("単一フィールド（氏名）の変更で full_name と any が true になる", () => {
    const baseline = buildForm();
    const form = buildForm({ full_name: "佐藤 花子" });
    const { result } = renderHook(() => useCareerDirty(form, baseline));
    expect(result.current.full_name).toBe(true);
    expect(result.current.any).toBe(true);
    // 他は false のまま
    expect(result.current.career_summary).toBe(false);
    expect(result.current.experiencesAny).toBe(false);
  });

  it("経歴配下のプロジェクトを変更すると experience / experiencesAny / overall が伝播する", () => {
    const baseline = buildForm();
    const form = buildForm();
    form.experiences[0].clients[0].projects[0].name = "プロジェクトY";

    const { result } = renderHook(() => useCareerDirty(form, baseline));
    expect(result.current.any).toBe(true);
    expect(result.current.experiencesAny).toBe(true);
    expect(result.current.experiences[0].any).toBe(true);
    expect(result.current.experiences[0].clients[0].any).toBe(true);
    expect(result.current.experiences[0].clients[0].projects[0].any).toBe(true);
    // experience 直下フィールド自体は変えていないので self は false
    expect(result.current.experiences[0].self).toBe(false);
    expect(result.current.experiences[0].fields.company).toBe(false);
  });

  it("経歴を新規追加した場合、新規要素は dirty で集約も dirty", () => {
    const baseline = buildForm();
    const form = buildForm();
    form.experiences = [...form.experiences, { ...blankCareerExperience }];

    const { result } = renderHook(() => useCareerDirty(form, baseline));
    expect(result.current.any).toBe(true);
    expect(result.current.experiencesAny).toBe(true);
    expect(result.current.experiences[1].any).toBe(true);
    expect(result.current.experiences[1].self).toBe(true);
  });

  it("経歴を削除した場合、experiencesAny が true（要素数が baseline と異なる）", () => {
    const baseline = buildForm();
    baseline.experiences = [
      ...baseline.experiences,
      { ...blankCareerExperience, company: "株式会社B" },
    ];
    const form = buildForm();
    // form は経歴1件のみ、baseline は2件

    const { result } = renderHook(() => useCareerDirty(form, baseline));
    expect(result.current.any).toBe(true);
    expect(result.current.experiencesAny).toBe(true);
  });

  it("資格名を変更すると qualifications[i].self と qualificationsAny が true", () => {
    const baseline = buildForm();
    const form = buildForm();
    form.qualifications[0].name = "応用情報";

    const { result } = renderHook(() => useCareerDirty(form, baseline));
    expect(result.current.qualificationsAny).toBe(true);
    expect(result.current.qualifications[0].self).toBe(true);
    expect(result.current.qualifications[0].fields.name).toBe(true);
    expect(result.current.qualifications[0].fields.acquired_date).toBe(false);
    expect(result.current.any).toBe(true);
    // 経歴側は影響しない
    expect(result.current.experiencesAny).toBe(false);
  });

  it("経歴の company だけ変更すると、当該 experience の fields.company と self / any が立つ", () => {
    const baseline = buildForm();
    const form = buildForm();
    form.experiences[0].company = "株式会社Z";

    const { result } = renderHook(() => useCareerDirty(form, baseline));
    expect(result.current.experiences[0].fields.company).toBe(true);
    expect(result.current.experiences[0].self).toBe(true);
    expect(result.current.experiences[0].any).toBe(true);
    expect(result.current.experiencesAny).toBe(true);
    // 配下プロジェクトは触れていないので false のまま
    expect(result.current.experiences[0].clients[0].projects[0].any).toBe(false);
  });
});
