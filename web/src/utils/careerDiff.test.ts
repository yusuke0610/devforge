import { describe, it, expect } from "vitest";

import {
  blankCareerClient,
  blankCareerExperience,
  blankCareerProject,
  blankCareerTechnologyStack,
  blankResumeQualification,
} from "../constants";
import type { CareerFormState } from "../payloadBuilders";
import { buildCareerChanges } from "./careerDiff";

/** ネストを含めて完全にコピーした form を作る（テスト間で参照を共有しないため）。 */
function buildForm(): CareerFormState {
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
  });
}

describe("buildCareerChanges", () => {
  it("変更が無ければ空配列を返す", () => {
    const form = buildForm();
    expect(buildCareerChanges(form, buildForm())).toEqual([]);
  });

  it("トップレベル文字列の修正を modified として検出する", () => {
    const baseline = buildForm();
    const form = buildForm();
    form.full_name = "佐藤 花子";

    const changes = buildCareerChanges(form, baseline);
    expect(changes).toHaveLength(1);
    expect(changes[0]).toMatchObject({
      kind: "modified",
      oldValue: "山田 太郎",
      newValue: "佐藤 花子",
    });
    expect(changes[0].label).toBe("氏名");
  });

  it("連絡先（email / github_url）の変更を検出し、ロールバックで復元できる", () => {
    const baseline = buildForm();
    const form = buildForm();
    form.email = "sato@example.com";
    form.github_url = "https://github.com/sato"; // baseline は ""（未設定）

    const changes = buildCareerChanges(form, baseline);

    // email: 既存値 → 新値の modified として検出される。
    const emailChange = changes.find((c) => c.path.join(".") === "email");
    expect(emailChange).toBeDefined();
    expect(emailChange).toMatchObject({
      kind: "modified",
      oldValue: "yamada@example.com",
      newValue: "sato@example.com",
    });

    // github_url: 空 → 新値の modified として検出される。
    const githubChange = changes.find((c) => c.path.join(".") === "github_url");
    expect(githubChange).toBeDefined();
    expect(githubChange?.kind).toBe("modified");
    expect(githubChange?.newValue).toBe("https://github.com/sato");

    // 項目別ロールバックで両フィールドが baseline 値へ戻る。
    expect(emailChange!.rollback(form).email).toBe("yamada@example.com");
    expect(githubChange!.rollback(form).github_url).toBe("");
  });

  it("職歴の追加を added として検出する", () => {
    const baseline = buildForm();
    const form = buildForm();
    form.experiences.push({ ...structuredClone(blankCareerExperience), company: "株式会社B" });

    const changes = buildCareerChanges(form, baseline);
    const added = changes.find((c) => c.kind === "added");
    expect(added).toBeDefined();
    expect(added?.label).toBe("職歴2");
    expect(added?.newValue).toBe("株式会社B");
  });

  it("職歴の削除を removed として検出し、ロールバックで復元できる", () => {
    const baseline = buildForm();
    baseline.experiences.push({ ...structuredClone(blankCareerExperience), company: "株式会社B" });
    const form = buildForm(); // 1 社だけ

    const changes = buildCareerChanges(form, baseline);
    const removed = changes.find((c) => c.kind === "removed");
    expect(removed).toBeDefined();
    expect(removed?.label).toBe("職歴2");
    expect(removed?.oldValue).toBe("株式会社B");

    const restored = removed!.rollback(form);
    expect(restored.experiences).toHaveLength(2);
    expect(restored.experiences[1].company).toBe("株式会社B");
  });

  it("ネストした技術スタックの変更を検出する", () => {
    const baseline = buildForm();
    const form = buildForm();
    form.experiences[0].clients[0].projects[0].technology_stacks[0].name = "Rust";

    const changes = buildCareerChanges(form, baseline);
    const techChange = changes.find((c) => c.newValue === "Rust");
    expect(techChange).toBeDefined();
    expect(techChange?.kind).toBe("modified");
    expect(techChange?.oldValue).toBe("TypeScript");
    expect(techChange?.label).toContain("技術名");
  });

  it("項目別ロールバックは当該フィールドのみ baseline に戻し、他の変更は保持する", () => {
    const baseline = buildForm();
    const form = buildForm();
    form.full_name = "佐藤 花子";
    form.career_summary = "新サマリー";

    const changes = buildCareerChanges(form, baseline);
    expect(changes).toHaveLength(2);

    // 氏名だけロールバック
    const nameChange = changes.find((c) => c.label === "氏名")!;
    const rolledBack = nameChange.rollback(form);

    expect(rolledBack.full_name).toBe("山田 太郎"); // baseline に戻る
    expect(rolledBack.career_summary).toBe("新サマリー"); // 他の変更は残る

    // 再計算すると氏名の行は消え、職務要約だけ残る
    const remaining = buildCareerChanges(rolledBack, baseline);
    expect(remaining).toHaveLength(1);
    expect(remaining[0].label).toBe("職務要約");
  });

  it("boolean フィールドは「あり / なし」で表示する", () => {
    const baseline = buildForm();
    const form = buildForm();
    form.experiences[0].is_current = !form.experiences[0].is_current;

    const changes = buildCareerChanges(form, baseline);
    const boolChange = changes.find((c) => c.label.includes("在職中"));
    expect(boolChange).toBeDefined();
    expect([boolChange?.oldValue, boolChange?.newValue].sort()).toEqual(["あり", "なし"]);
  });
});
