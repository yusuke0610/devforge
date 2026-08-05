import { describe, expect, it } from "vitest";

import type { ResumeDraftCandidateResponse } from "../api/types";
import {
  buildDefaultSelection,
  isSelectionFull,
  toggleCandidate,
} from "./resumeDraftCandidates";

const LIMIT = 5;

function candidate(
  full_name: string,
  overrides: Partial<ResumeDraftCandidateResponse> = {},
): ResumeDraftCandidateResponse {
  return {
    full_name,
    description: "",
    duration_days: 400,
    implementation_volume: 10000,
    has_infra: false,
    technology_stacks: [],
    default_selected: true,
    reasons: [],
    ...overrides,
  };
}

describe("buildDefaultSelection", () => {
  it("default_selected の候補だけを初期選択にする", () => {
    const candidates = [
      candidate("o/real"),
      candidate("o/tutorial", { default_selected: false, reasons: ["learning_topic"] }),
      candidate("o/other"),
    ];
    expect(buildDefaultSelection(candidates, LIMIT)).toEqual(["o/real", "o/other"]);
  });

  it("上限を超える分は初期選択に含めない（提示順の上位を優先）", () => {
    const candidates = Array.from({ length: LIMIT + 3 }, (_, i) => candidate(`o/repo-${i}`));
    expect(buildDefaultSelection(candidates, LIMIT)).toEqual([
      "o/repo-0",
      "o/repo-1",
      "o/repo-2",
      "o/repo-3",
      "o/repo-4",
    ]);
  });

  it("全件が非選択なら空になる（機械が勝手に選ばない）", () => {
    const candidates = [candidate("o/a", { default_selected: false, reasons: ["short_duration"] })];
    expect(buildDefaultSelection(candidates, LIMIT)).toEqual([]);
  });
});

describe("toggleCandidate", () => {
  it("未選択なら追加する", () => {
    expect(toggleCandidate(["o/a"], "o/b", LIMIT)).toEqual(["o/a", "o/b"]);
  });

  it("選択済みなら外す（機械の判定を常に覆せる）", () => {
    expect(toggleCandidate(["o/a", "o/b"], "o/a", LIMIT)).toEqual(["o/b"]);
  });

  it("上限に達していると追加しない（既存の選択は壊さない）", () => {
    const full = ["o/1", "o/2", "o/3", "o/4", "o/5"];
    expect(toggleCandidate(full, "o/6", LIMIT)).toEqual(full);
  });

  it("上限に達していても選択解除はできる", () => {
    const full = ["o/1", "o/2", "o/3", "o/4", "o/5"];
    expect(toggleCandidate(full, "o/3", LIMIT)).toEqual(["o/1", "o/2", "o/4", "o/5"]);
  });
});

describe("isSelectionFull", () => {
  it("上限に達しているかを返す", () => {
    expect(isSelectionFull(["o/1", "o/2"], LIMIT)).toBe(false);
    expect(isSelectionFull(["o/1", "o/2", "o/3", "o/4", "o/5"], LIMIT)).toBe(true);
  });
});
