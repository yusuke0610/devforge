import { describe, expect, it } from "vitest";

import { buildReviewEntries, comparePaths } from "./careerReview";
import type { CareerChange } from "./careerDiff";

function change(path: (string | number)[], label: string): CareerChange {
  return { path, label, kind: "modified", oldValue: "", newValue: "", rollback: (f) => f };
}

describe("comparePaths", () => {
  it("トップレベルは PDF 順（自己PR が資格より後）", () => {
    expect(comparePaths("self_pr", "qualifications.0.name")).toBeGreaterThan(0);
    expect(comparePaths("career_summary", "experiences.0.company")).toBeLessThan(0);
  });

  it("親は子より前", () => {
    expect(comparePaths("experiences.0", "experiences.0.company")).toBeLessThan(0);
  });

  it("配列 index は数値順", () => {
    expect(comparePaths("experiences.0.company", "experiences.1.company")).toBeLessThan(0);
  });

  it("コンテナ内のフィールドは PDF 順（company が business_description より前）", () => {
    expect(comparePaths("experiences.0.company", "experiences.0.business_description")).toBeLessThan(0);
  });
});

describe("buildReviewEntries", () => {
  it("同一パスの差分を 1 エントリにまとめる", () => {
    const entries = buildReviewEntries([
      change(["career_summary"], "職務要約"),
      change(["career_summary"], "職務要約"),
    ]);
    expect(entries).toHaveLength(1);
    expect(entries[0].changes).toHaveLength(2);
  });

  it("PDF レイアウト順に並ぶ（自己PRが末尾、職歴は資格より前）", () => {
    const entries = buildReviewEntries([
      change(["self_pr"], "自己PR"),
      change(["full_name"], "氏名"),
      change(["qualifications", 0, "name"], "資格1 ＞ 資格名"),
      change(["experiences", 0, "company"], "職歴1 ＞ 会社名"),
    ]);
    const order = entries.map((e) => e.path);
    expect(order[0]).toBe("full_name");
    expect(order[order.length - 1]).toBe("self_pr");
    expect(order.indexOf("experiences.0.company")).toBeLessThan(order.indexOf("qualifications.0.name"));
  });

  it("複数フィールドの差分がそれぞれエントリになる", () => {
    const entries = buildReviewEntries([
      change(["full_name"], "氏名"),
      change(["experiences", 0, "description"], "職歴1 ＞ 詳細"),
    ]);
    expect(entries.map((e) => e.path)).toEqual(["full_name", "experiences.0.description"]);
  });
});
