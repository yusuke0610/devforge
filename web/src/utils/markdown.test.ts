import { describe, expect, it } from "vitest";

import { renderMarkdown, markdownToPlainText } from "./markdown";

describe("renderMarkdown", () => {
  it("空文字は空文字を返す", () => {
    expect(renderMarkdown("")).toBe("");
  });

  it("Markdown を HTML へ整形する", () => {
    const html = renderMarkdown("# 見出し\n\n- 項目1\n- 項目2");
    expect(html).toContain("<h1");
    expect(html).toContain("見出し");
    expect(html).toContain("<li>項目1</li>");
  });

  it("script タグを除去する（XSS 防止）", () => {
    const html = renderMarkdown("通常テキスト\n\n<script>alert('xss')</script>");
    expect(html).not.toContain("<script>");
    expect(html).not.toContain("alert('xss')");
    expect(html).toContain("通常テキスト");
  });

  it("onerror 属性付きの img を無害化する（XSS 防止）", () => {
    const html = renderMarkdown('<img src="x" onerror="alert(1)">');
    expect(html).not.toContain("onerror");
  });
});

describe("markdownToPlainText", () => {
  it("空文字は空文字を返す", () => {
    expect(markdownToPlainText("")).toBe("");
  });

  it("太字記法 ** を除いた表示テキストを返す", () => {
    expect(markdownToPlainText("**太字**").trim()).toBe("太字");
  });

  it("見出し # やリスト記号 - は除外される", () => {
    const text = markdownToPlainText("# 見出し\n\n- 項目1\n- 項目2");
    expect(text).toContain("見出し");
    expect(text).toContain("項目1");
    expect(text).not.toContain("#");
    expect(text).not.toContain("- ");
  });

  it("リンク記法はテキストのみ残り URL は除外される", () => {
    const text = markdownToPlainText("[公式サイト](https://example.com)");
    expect(text).toContain("公式サイト");
    expect(text).not.toContain("example.com");
  });
});
