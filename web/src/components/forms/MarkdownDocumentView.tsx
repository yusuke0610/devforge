import { useEffect, useState } from "react";

import { IMPORT_ASSIST_MESSAGES } from "../../constants/messages";
import { renderMarkdown } from "../../utils/markdown";
import { useSelectionFill, type DocumentViewProps } from "./documentView";
import styles from "./ResumeSourceTracePanel.module.css";

/**
 * Markdown を整形描画し、テキスト選択を「流し込み」に変換する内側ビュー。
 *
 * {@link PdfDocumentView} と対になる Markdown 用レンダラー。
 * sanitize は {@link renderMarkdown}（DOMPurify 経由）に一元化しており、
 * `dangerouslySetInnerHTML` にはその出力のみを渡す。流し込み先の決定（最後に
 * フォーカスした入力欄）は useResumeImportAssist 側が担うため、ここは
 * 「選択文字列を onFill に渡す」ことだけに専念する。
 */
export default function MarkdownDocumentView({ file, zoom = 1, onFill, onError }: DocumentViewProps) {
  const [html, setHtml] = useState<string | null>(null);

  // ファイル本文をテキストとして読み込み、sanitize 済み HTML へ変換する。
  // 別ファイルへの切り替えは呼び出し側が key で再マウントするため、ここでの破棄は不要。
  useEffect(() => {
    let cancelled = false;
    file
      .text()
      .then((text) => {
        if (cancelled) return;
        onError(null);
        setHtml(renderMarkdown(text));
      })
      .catch(() => {
        if (cancelled) return;
        // 失敗時も loading（RENDERING）表示から抜けるよう html を確定させる。
        // 本文は空にし、失敗の通知は onError 経由でパネルのエラー欄に出す。
        setHtml("");
        onError(IMPORT_ASSIST_MESSAGES.RENDER_FAILED);
      });
    return () => {
      cancelled = true;
    };
  }, [file, onError]);

  const handleSelection = useSelectionFill(onFill);

  if (html === null) {
    return <p className={styles.empty}>{IMPORT_ASSIST_MESSAGES.RENDERING}</p>;
  }

  return (
    <div
      className={styles.markdownBody}
      style={{ fontSize: `${zoom}em` }}
      onMouseUp={handleSelection}
      dangerouslySetInnerHTML={{ __html: html }}
    />
  );
}
