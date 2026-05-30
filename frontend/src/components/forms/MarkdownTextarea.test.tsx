import { render } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { MarkdownTextarea } from "./MarkdownTextarea";

function getPreview(container: HTMLElement): HTMLElement {
  const preview = container.querySelector("textarea + div");
  expect(preview).not.toBeNull();
  return preview as HTMLElement;
}

/**
 * XSS 回帰テスト。
 * MarkdownTextarea は marked の出力を dangerouslySetInnerHTML で描画するため、
 * DOMPurify を通して危険な要素・属性が除去されることを保証する。
 * （security.md §Frontend: Markdown レンダラーは sanitize を有効化）
 */
describe("MarkdownTextarea XSS サニタイズ", () => {
  it("script タグとその中身を除去する", () => {
    const { container } = render(
      <MarkdownTextarea
        label="自己PR"
        value={"<script>window.__xss = 1</script>通常テキスト"}
        onChange={() => {}}
      />,
    );
    const preview = getPreview(container);
    expect(preview.querySelector("script")).toBeNull();
    expect(preview.innerHTML).not.toContain("window.__xss");
  });

  it("img の onerror 属性を除去する", () => {
    const { container } = render(
      <MarkdownTextarea
        label="自己PR"
        value={'<img src="x" onerror="window.__xss = 1">'}
        onChange={() => {}}
      />,
    );
    const preview = getPreview(container);
    expect(preview.innerHTML.toLowerCase()).not.toContain("onerror");
  });

  it("javascript: スキームのリンクを無害化する", () => {
    const { container } = render(
      <MarkdownTextarea
        label="自己PR"
        value={'<a href="javascript:window.__xss=1">click</a>'}
        onChange={() => {}}
      />,
    );
    const anchor = getPreview(container).querySelector("a");
    expect(anchor?.getAttribute("href") ?? "").not.toContain("javascript:");
  });

  it("通常の Markdown は引き続き描画される", () => {
    const { container } = render(
      <MarkdownTextarea label="自己PR" value={"# 見出し"} onChange={() => {}} />,
    );
    expect(getPreview(container).querySelector("h1")?.textContent).toBe("見出し");
  });
});
