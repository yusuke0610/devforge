import { useCallback, useEffect, useState } from "react";

import { IMPORT_ASSIST_MESSAGES } from "../../constants/messages";
import { renderMarkdown } from "../../utils/markdown";
import styles from "./ResumeSourceTracePanel.module.css";

type Props = {
  /** 描画対象の Markdown ファイル */
  file: File;
  /** ズーム倍率（1 = 等倍）。フォントサイズの em 倍率として適用する。 */
  zoom?: number;
  /** 原本上で選択された文字列を流し込むコールバック */
  onFill: (text: string) => void;
  /** 描画エラー・エラー解除を親へ伝えるコールバック */
  onError: (message: string | null) => void;
};

/**
 * Markdown を整形描画し、テキスト選択を「流し込み」に変換する内側ビュー。
 *
 * {@link PdfDocumentView} と対になる Markdown 用レンダラー。
 * sanitize は {@link renderMarkdown}（DOMPurify 経由）に一元化しており、
 * `dangerouslySetInnerHTML` にはその出力のみを渡す。流し込み先の決定（最後に
 * フォーカスした入力欄）は useResumeImportAssist 側が担うため、ここは
 * 「選択文字列を onFill に渡す」ことだけに専念する。
 */
export default function MarkdownDocumentView({ file, zoom = 1, onFill, onError }: Props) {
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
        onError(IMPORT_ASSIST_MESSAGES.RENDER_FAILED);
      });
    return () => {
      cancelled = true;
    };
  }, [file, onError]);

  const handleSelection = useCallback(() => {
    const text = window.getSelection()?.toString() ?? "";
    if (!text.trim()) return;
    onFill(text);
    // 流し込み後は選択を解除し、次にどこを掴んだか分かりやすくする。
    window.getSelection()?.removeAllRanges();
  }, [onFill]);

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
