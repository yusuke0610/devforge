import { describe, expect, it } from "vitest";

import { creditsToYen, estimateChats } from "./creditEstimate";

describe("estimateChats", () => {
  it("クレジット ÷ 1回あたり消費の floor を返す", () => {
    // 1000 / 12 = 83.3 → 83
    expect(estimateChats(1000, 12)).toBe(83);
  });

  it("残高 0 は 0 回（負ではないので算出する）", () => {
    expect(estimateChats(0, 12)).toBe(0);
  });

  it("負の残高では目安を出さない（『約 -N 回』を防ぐ）", () => {
    expect(estimateChats(-50, 12)).toBeNull();
  });

  it("1回あたり消費が 0 / null / undefined なら null", () => {
    expect(estimateChats(1000, 0)).toBeNull();
    expect(estimateChats(1000, null)).toBeNull();
    expect(estimateChats(1000, undefined)).toBeNull();
  });
});

describe("creditsToYen", () => {
  it("1 クレジット = ¥1 で換算する", () => {
    expect(creditsToYen(500)).toBe(500);
  });
});
