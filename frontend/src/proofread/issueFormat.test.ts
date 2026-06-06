import { describe, expect, it } from "vitest";

import { buildExcerpt, groupIssuesByField, mapSeverity } from "./issueFormat";
import type { ProofreadIssue } from "./types";

describe("mapSeverity", () => {
  it("0=info / 1=warning / 2 以上=error に写像する", () => {
    expect(mapSeverity(0)).toBe("info");
    expect(mapSeverity(1)).toBe("warning");
    expect(mapSeverity(2)).toBe("error");
    expect(mapSeverity(3)).toBe("error");
  });
});

describe("buildExcerpt", () => {
  it("指摘箇所の前後を切り出す（両端が途切れると省略記号を付ける）", () => {
    // 40 文字。半径 12 なので index=20 だと前後とも途切れる。
    const text = "あいうえおかきくけこさしすせそたちつてとアイウエオカキクケコサシスセソタチツテト";
    const excerpt = buildExcerpt(text, 20, 1);
    expect(excerpt).toContain("カ");
    expect(excerpt.startsWith("…")).toBe(true);
    expect(excerpt.endsWith("…")).toBe(true);
  });

  it("先頭付近は前側の省略記号を付けない", () => {
    const excerpt = buildExcerpt("短いテキスト", 0, 1);
    expect(excerpt.startsWith("…")).toBe(false);
    expect(excerpt).toContain("短い");
  });

  it("改行・連続空白は 1 つの空白に潰す", () => {
    const excerpt = buildExcerpt("行1\n\n  行2", 0, 1);
    expect(excerpt).not.toContain("\n");
    expect(excerpt).toBe("行1 行2");
  });

  it("空文字なら空を返す", () => {
    expect(buildExcerpt("", 0, 1)).toBe("");
  });
});

describe("groupIssuesByField", () => {
  const makeIssue = (fieldId: string, fieldLabel: string, message: string): ProofreadIssue => ({
    fieldId,
    fieldLabel,
    ruleId: "prh",
    message,
    severity: "warning",
    line: 1,
    column: 1,
    index: 0,
    excerpt: "",
  });

  it("フィールド単位でグルーピングし、入力順を保つ", () => {
    const issues = [
      makeIssue("self_pr", "自己PR", "A"),
      makeIssue("career_summary", "職務要約", "B"),
      makeIssue("self_pr", "自己PR", "C"),
    ];
    const groups = groupIssuesByField(issues);
    expect(groups.map((g) => g.fieldId)).toEqual(["self_pr", "career_summary"]);
    expect(groups[0].issues.map((i) => i.message)).toEqual(["A", "C"]);
    expect(groups[1].issues.map((i) => i.message)).toEqual(["B"]);
  });

  it("空配列なら空グループ", () => {
    expect(groupIssuesByField([])).toEqual([]);
  });
});
