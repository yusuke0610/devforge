/**
 * テスト用の標準的な職務経歴フォーム（CareerFormState）を生成するファクトリ。
 *
 * 以前は careerDiff.test / useCareerDirty.test がそれぞれ同型のサンプルを直書きしており、
 * 値が少しずつドリフトしていた（一方だけ role / technology_stacks.name を持つ等）。
 * 正本をここへ集約し、各テストは overrides で必要な差分だけ与える。
 *
 * 毎回 structuredClone するため、呼び出し側で baseline / form を直接ミューテートしても
 * テスト間で参照が共有されない。
 */

import {
  blankCareerClient,
  blankCareerExperience,
  blankCareerProject,
  blankCareerTechnologyStack,
  blankResumeQualification,
} from "../../constants";
import type { CareerFormState } from "../../payloadBuilders";

export function buildSampleCareerForm(
  overrides: Partial<CareerFormState> = {},
): CareerFormState {
  return structuredClone({
    full_name: "山田 太郎",
    email: "yamada@example.com",
    github_url: "",
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
                role: "SE",
                technology_stacks: [{ ...blankCareerTechnologyStack, name: "TypeScript" }],
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
  });
}
