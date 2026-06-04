import { describe, it, expect } from "vitest";

import { insertAtPath, removeAtPath, setAtPath } from "./setAtPath";

describe("setAtPath", () => {
  it("オブジェクトの 1 フィールドを更新し、元オブジェクトを破壊しない", () => {
    const original = { a: 1, b: { c: 2 } };
    const next = setAtPath(original, ["b", "c"], 99);
    expect(next).toEqual({ a: 1, b: { c: 99 } });
    expect(original.b.c).toBe(2); // 非破壊
    expect(next).not.toBe(original);
    expect(next.b).not.toBe(original.b);
  });

  it("配列の index を更新する", () => {
    const original = { items: [{ name: "x" }, { name: "y" }] };
    const next = setAtPath(original, ["items", 1, "name"], "z");
    expect(next.items[1].name).toBe("z");
    expect(original.items[1].name).toBe("y");
    expect(next.items[0]).toBe(original.items[0]); // 触らない要素は参照共有
  });

  it("空パスはルート置換になる", () => {
    expect(setAtPath({ a: 1 }, [], { b: 2 })).toEqual({ b: 2 });
  });
});

describe("removeAtPath", () => {
  it("配列要素を取り除く", () => {
    const original = { items: ["a", "b", "c"] };
    const next = removeAtPath(original, ["items", 1]);
    expect(next.items).toEqual(["a", "c"]);
    expect(original.items).toEqual(["a", "b", "c"]); // 非破壊
  });

  it("ネストした配列要素を取り除く", () => {
    const original = { groups: [{ items: ["a", "b"] }] };
    const next = removeAtPath(original, ["groups", 0, "items", 0]);
    expect(next.groups[0].items).toEqual(["b"]);
  });
});

describe("insertAtPath", () => {
  it("配列の指定位置に要素を挿入する", () => {
    const original = { items: ["a", "c"] };
    const next = insertAtPath(original, ["items", 1], "b");
    expect(next.items).toEqual(["a", "b", "c"]);
    expect(original.items).toEqual(["a", "c"]); // 非破壊
  });

  it("末尾を超える index への挿入は末尾に追加される", () => {
    const original = { items: ["a"] };
    const next = insertAtPath(original, ["items", 5], "b");
    expect(next.items).toEqual(["a", "b"]);
  });
});
