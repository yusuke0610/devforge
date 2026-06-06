import { describe, expect, it } from "vitest";

import { buildReviewEntries, comparePaths } from "./careerReview";
import type { CareerChange } from "./careerDiff";
import type { ProofreadIssue } from "../proofread/types";

function change(path: (string | number)[], label: string): CareerChange {
  return { path, label, kind: "modified", oldValue: "", newValue: "", rollback: (f) => f };
}
function issue(fieldId: string, fieldLabel: string, message: string): ProofreadIssue {
  return {
    fieldId,
    fieldLabel,
    ruleId: "prh",
    message,
    severity: "warning",
    line: 1,
    column: 1,
    index: 0,
    excerpt: "",
  };
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
  it("同一パスの差分と校正を 1 エントリに統合する", () => {
    const entries = buildReviewEntries(
      [change(["career_summary"], "職務要約")],
      [issue("career_summary", "職務要約", "javascript => JavaScript")],
    );
    expect(entries).toHaveLength(1);
    expect(entries[0].changes).toHaveLength(1);
    expect(entries[0].issues).toHaveLength(1);
  });

  it("PDF レイアウト順に並ぶ（自己PRが末尾、職歴は資格より前）", () => {
    const entries = buildReviewEntries(
      [change(["self_pr"], "自己PR"), change(["full_name"], "氏名")],
      [
        issue("self_pr", "自己PR", "x"),
        issue("qualifications.0.name", "資格1 ＞ 資格名", "y"),
        issue("experiences.0.company", "職歴1 ＞ 会社名", "z"),
      ],
    );
    const order = entries.map((e) => e.path);
    expect(order[0]).toBe("full_name");
    expect(order[order.length - 1]).toBe("self_pr");
    expect(order.indexOf("experiences.0.company")).toBeLessThan(order.indexOf("qualifications.0.name"));
  });

  it("差分のみ・校正のみの項目もそれぞれエントリになる", () => {
    const entries = buildReviewEntries(
      [change(["full_name"], "氏名")],
      [issue("experiences.0.description", "職歴1 ＞ 詳細", "冗長")],
    );
    expect(entries.map((e) => e.path)).toEqual(["full_name", "experiences.0.description"]);
    expect(entries[0].issues).toHaveLength(0);
    expect(entries[1].changes).toHaveLength(0);
  });
});
