import { useCallback, useEffect, useRef, useState } from "react";
import { Document, Page } from "react-pdf";

import { IMPORT_ASSIST_MESSAGES } from "../../constants/messages";
import { useSelectionFill, type DocumentViewProps } from "./documentView";
import styles from "./ResumeSourceTracePanel.module.css";
// worker 設定（副作用 import）。このモジュールごと React.lazy で遅延ロードされる。
import "../../utils/pdfjs";

/** ドキュメント全体の最小テキスト量。これ未満ならスキャン PDF とみなして警告する。 */
const MIN_TEXT_CHARS = 20;

/**
 * react-pdf で PDF を描画し、テキスト選択を「流し込み」に変換する内側ビュー。
 *
 * 重い react-pdf / pdf.js / テキストレイヤー CSS をこのモジュールに閉じ込め、
 * {@link ResumeSourceTracePanel} から React.lazy で遅延ロードして初期バンドルから切り離す。
 * 流し込み先の決定（最後にフォーカスした入力欄）は useResumeImportAssist 側が担うため、
 * ここは「選択文字列を onFill に渡す」ことだけに専念する。
 */
export default function PdfDocumentView({ file, zoom = 1, onFill, onError }: DocumentViewProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(0);
  const [numPages, setNumPages] = useState(0);
  const [scanned, setScanned] = useState(false);

  // テキスト量の集計（スキャン PDF 判定用）。ページのテキスト取得ごとに加算する。
  const textCharsRef = useRef(0);
  const processedPagesRef = useRef(0);

  // パネル幅にページ幅を合わせる（カラム幅の変化に追従）。
  // スプリッターのドラッグ中は連続発火するため requestAnimationFrame で 1 フレーム 1 回に間引く。
  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    let raf = 0;
    const update = () => {
      cancelAnimationFrame(raf);
      raf = requestAnimationFrame(() => setWidth(el.clientWidth));
    };
    update();
    const observer = new ResizeObserver(update);
    observer.observe(el);
    return () => {
      cancelAnimationFrame(raf);
      observer.disconnect();
    };
  }, []);

  // 別の PDF への切り替えは呼び出し側が key で再マウントするため、ここでのリセットは不要。

  const handleSelection = useSelectionFill(onFill);

  const handleLoadSuccess = useCallback(
    (pdf: { numPages: number }) => {
      onError(null);
      setNumPages(pdf.numPages);
    },
    [onError],
  );

  const handleLoadError = useCallback(() => {
    onError(IMPORT_ASSIST_MESSAGES.RENDER_FAILED);
  }, [onError]);

  const handleGetTextSuccess = useCallback(
    (textContent: { items: ReadonlyArray<unknown> }) => {
      textCharsRef.current += textContent.items.reduce<number>((sum, item) => {
        const str = (item as { str?: string }).str;
        return sum + (typeof str === "string" ? str.length : 0);
      }, 0);
      processedPagesRef.current += 1;
      // 全ページ分のテキストを取り終えても文字が極端に少なければスキャン PDF とみなす。
      if (processedPagesRef.current >= numPages && textCharsRef.current < MIN_TEXT_CHARS) {
        setScanned(true);
      }
    },
    [numPages],
  );

  return (
    <div ref={containerRef} className={styles.pages} onMouseUp={handleSelection}>
      {scanned && <p className={styles.warning}>{IMPORT_ASSIST_MESSAGES.NO_TEXT}</p>}
      <Document
        file={file}
        onLoadSuccess={handleLoadSuccess}
        onLoadError={handleLoadError}
        loading={IMPORT_ASSIST_MESSAGES.RENDERING}
      >
        {width > 0 &&
          Array.from({ length: numPages }, (_, index) => (
            <Page
              key={index}
              pageNumber={index + 1}
              width={Math.max(1, Math.round(width * zoom))}
              renderAnnotationLayer={false}
              renderTextLayer
              onGetTextSuccess={handleGetTextSuccess}
              className={styles.page}
              loading={null}
            />
          ))}
      </Document>
    </div>
  );
}
