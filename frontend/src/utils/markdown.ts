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
