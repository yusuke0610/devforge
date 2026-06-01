import { lazy, Suspense, useRef, useState } from "react";
import type { DragEvent } from "react";

import { IMPORT_ASSIST_MESSAGES } from "../../constants/messages";
import {
  IMPORT_FILE_ACCEPT,
  type UseResumeImportAssistReturn,
} from "../../hooks/career/useResumeImportAssist";
import shared from "../../styles/shared.module.css";
import styles from "./ResumeSourceTracePanel.module.css";

// react-pdf / pdf.js を含む PDF ビューと Markdown ビューは遅延ロードし、初期バンドルから切り離す。
const PdfDocumentView = lazy(() => import("./PdfDocumentView"));
const MarkdownDocumentView = lazy(() => import("./MarkdownDocumentView"));

const ZOOM_MIN = 0.5;
const ZOOM_MAX = 3;
const ZOOM_STEP = 0.25;

type Props = {
  assist: UseResumeImportAssistReturn;
};

/**
 * 取り込み補助の右カラム（原本ビュー）。
 *
 * 選択されたファイル（PDF / Markdown）を原本のまま描画し、ユーザーが文字をドラッグ選択すると、
 * 選択中（緑枠）の入力欄へ流し込む。「どの項目をどの粒度で取り込むか」は人間が原本上の選択で
 * 決める。ファイルはこのパネルへのドラッグ&ドロップ、または空状態のドロップゾーンのクリックで
 * 選択できる（ヘッダーの取り込みボタンからも選択可）。上部のタブ風ヘッダーでズームを操作する。
 * レンダラーは `kind` で切り替える。
 */
export function ResumeSourceTracePanel({ assist }: Props) {
  const { file, fileName, kind, error, fillSelection, setError, handleFileChange, acceptFile } =
    assist;
  const [zoom, setZoom] = useState(1);
  // ドラッグ中のハイライト表示フラグ。
  const [dragActive, setDragActive] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const zoomIn = () => setZoom((z) => Math.min(z + ZOOM_STEP, ZOOM_MAX));
  const zoomOut = () => setZoom((z) => Math.max(z - ZOOM_STEP, ZOOM_MIN));

  const handleDragOver = (e: DragEvent<HTMLDivElement>) => {
    // dragover を preventDefault しないと drop イベントが発火しない。
    e.preventDefault();
    setDragActive(true);
  };

  const handleDragLeave = (e: DragEvent<HTMLDivElement>) => {
    // 子要素間の移動でも dragleave は発火するため、パネル外へ出た時だけ解除する。
    if (e.currentTarget.contains(e.relatedTarget as Node | null)) return;
    setDragActive(false);
  };

  const handleDrop = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setDragActive(false);
    acceptFile(e.dataTransfer.files?.[0]);
  };

  const hasDocument = !!file && !!kind;

  return (
    <div
      className={`${styles.panel} ${dragActive ? styles.dragActive : ""}`}
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
    >
      {/* パネル内のドロップゾーン/再選択から開くファイル選択。ヘッダーの input と同じハンドラを使う。 */}
      <input
        ref={inputRef}
        type="file"
        accept={IMPORT_FILE_ACCEPT}
        style={{ display: "none" }}
        onChange={handleFileChange}
        aria-label={IMPORT_ASSIST_MESSAGES.SELECT_FILE}
      />

      {hasDocument && (
        <div className={styles.tab}>
          <span className={styles.tabName} title={fileName ?? undefined}>
            {fileName ?? IMPORT_ASSIST_MESSAGES.TAB_FALLBACK}
          </span>
          <div className={styles.tabActions}>
            <button
              type="button"
              className={styles.iconButton}
              onClick={zoomOut}
              disabled={zoom <= ZOOM_MIN}
              aria-label={IMPORT_ASSIST_MESSAGES.ZOOM_OUT}
            >
              −
            </button>
            <span className={styles.zoomLabel}>{Math.round(zoom * 100)}%</span>
            <button
              type="button"
              className={styles.iconButton}
              onClick={zoomIn}
              disabled={zoom >= ZOOM_MAX}
              aria-label={IMPORT_ASSIST_MESSAGES.ZOOM_IN}
            >
              ＋
            </button>
          </div>
        </div>
      )}

      <p className={styles.hint}>{IMPORT_ASSIST_MESSAGES.HINT}</p>

      {error && <p className={`${shared.error} ${styles.error}`}>{error}</p>}

      {!hasDocument ? (
        <button
          type="button"
          className={styles.dropzone}
          onClick={() => inputRef.current?.click()}
        >
          {dragActive ? IMPORT_ASSIST_MESSAGES.DROP_ACTIVE : IMPORT_ASSIST_MESSAGES.DROPZONE}
        </button>
      ) : (
        <Suspense fallback={<p className={styles.empty}>{IMPORT_ASSIST_MESSAGES.RENDERING}</p>}>
          {/* 別ファイルに切り替わったら再マウントして描画・集計状態をリセットする */}
          {kind === "pdf" ? (
            <PdfDocumentView
              key={`${file.name}-${file.size}-${file.lastModified}`}
              file={file}
              zoom={zoom}
              onFill={fillSelection}
              onError={setError}
            />
          ) : (
            <MarkdownDocumentView
              key={`${file.name}-${file.size}-${file.lastModified}`}
              file={file}
              zoom={zoom}
              onFill={fillSelection}
              onError={setError}
            />
          )}
        </Suspense>
      )}
    </div>
  );
}
