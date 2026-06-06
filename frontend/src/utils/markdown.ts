import { marked } from "marked";
import DOMPurify from "dompurify";

/**
 * Markdown 文字列を sanitize 済み HTML に変換する。
 *
 * marked は HTML をサニタイズしない（v5 以降 sanitize オプションは廃止）ため、
 * 生成した HTML は必ず DOMPurify に通して XSS（`<script>` / `onerror` 等）を除去する。
 * `dangerouslySetInnerHTML` に渡してよいのはこの関数の戻り値だけ、という制約を
 * 1 箇所に集約するための入口。
 */
export function renderMarkdown(md: string): string {
  if (!md) return "";
  const rawHtml = marked.parse(md, { async: false }) as string;
  return DOMPurify.sanitize(rawHtml);
}

/**
 * Markdown を描画後の表示テキスト（記法・タグを除いたプレーンテキスト）に変換する。
 *
 * 文字数カウントなど「見た目の本文量」を測る用途に使う。
 * `**太字**` の `*` やリンク記法 `[]()` の URL、見出しの `#` などはカウント対象から外れる。
 * sanitize 済み HTML を `DOMParser` で解釈し（live DOM へは挿入しない）textContent を取り出す。
 */
export function markdownToPlainText(md: string): string {
  const html = renderMarkdown(md);
  if (!html) return "";
  const doc = new DOMParser().parseFromString(html, "text/html");
  return doc.body.textContent ?? "";
}
