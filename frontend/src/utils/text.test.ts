import { describe, it, expect } from "vitest";

import { countNonWhitespace } from "./text";

describe("countNonWhitespace", () => {
  it("通常の文字をそのまま数える", () => {
    expect(countNonWhitespace("abcde")).toBe(5);
  });

  it("半角スペース・タブ・改行を除外する", () => {
    expect(countNonWhitespace("a b\tc\nd")).toBe(4);
  });

  it("全角スペース（U+3000）も除外する", () => {
    expect(countNonWhitespace("あ　い　う")).toBe(3);
  });

  it("空文字は 0", () => {
    expect(countNonWhitespace("")).toBe(0);
  });

  it("空白のみは 0", () => {
    expect(countNonWhitespace("　 \n\t")).toBe(0);
  });
});
