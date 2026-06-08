import { describe, it, expect, beforeEach, vi } from "vitest";

import { createInitialCareerForm } from "../formMappers";
import { clearCareerDraft, loadCareerDraft, saveCareerDraft } from "./careerDraft";

describe("careerDraft", () => {
  beforeEach(() => {
    sessionStorage.clear();
    vi.restoreAllMocks();
  });

  it("save → load で同じ内容を復元できる", () => {
    const form = { ...createInitialCareerForm(), full_name: "山田太郎" };
    saveCareerDraft(form);

    expect(loadCareerDraft()).toEqual(form);
  });

  it("ドラフト未保存なら load は null を返す", () => {
    expect(loadCareerDraft()).toBeNull();
  });

  it("clear すると load は null になる", () => {
    saveCareerDraft({ ...createInitialCareerForm(), full_name: "削除対象" });
    clearCareerDraft();

    expect(loadCareerDraft()).toBeNull();
  });

  it("壊れた JSON は null を返し、退避領域を掃除する", () => {
    sessionStorage.setItem("career_draft", "{壊れた");
    // 警告ログは抑止する（テスト出力を汚さない）
    vi.spyOn(console, "warn").mockImplementation(() => {});

    expect(loadCareerDraft()).toBeNull();
    expect(sessionStorage.getItem("career_draft")).toBeNull();
  });
});
