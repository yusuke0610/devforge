import { lazy, Suspense, useState } from "react";

import { IMPORT_ASSIST_MESSAGES } from "../../constants/messages";
import type { UseResumeImportAssistReturn } from "../../hooks/career/useResumeImportAssist";
import shared from "../../styles/shared.module.css";
import styles from "./ResumePdfTracePanel.module.css";

// react-pdf / pdf.js を含む内側ビューは遅延ロードし、初期バンドルから切り離す。
const PdfDocumentView = lazy(() => import("./PdfDocumentView"));

const ZOOM_MIN = 0.5;
const ZOOM_MAX = 3;
const ZOOM_STEP = 0.25;

type Props = {
  assist: UseResumeImportAssistReturn;
};

/**
 * PDF 取り込み補助の右カラム（PDF 原本ビュー）。
 *
 * 選択された PDF を原本のまま描画し、ユーザーが文字をドラッグ選択すると、選択中（緑枠）の
 * 入力欄へ流し込む。「どの項目をどの粒度で取り込むか」は人間が PDF 上の選択で決める。
 * 上部のタブ風ヘッダーでズーム（拡大/縮小）を操作する。
 */
export function ResumePdfTracePanel({ assist }: Props) {
  const { file, fileName, error, fillSelection, setError } = assist;
  const [zoom, setZoom] = useState(1);

  const zoomIn = () => setZoom((z) => Math.min(z + ZOOM_STEP, ZOOM_MAX));
  const zoomOut = () => setZoom((z) => Math.max(z - ZOOM_STEP, ZOOM_MIN));

  return (
    <div className={styles.panel}>
      {file && (
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

      {!file ? (
        <p className={styles.empty}>{IMPORT_ASSIST_MESSAGES.EMPTY}</p>
      ) : (
        <Suspense fallback={<p className={styles.empty}>{IMPORT_ASSIST_MESSAGES.RENDERING}</p>}>
          {/* 別ファイルに切り替わったら再マウントして描画・集計状態をリセットする */}
          <PdfDocumentView
            key={`${file.name}-${file.size}-${file.lastModified}`}
            file={file}
            zoom={zoom}
            onFill={fillSelection}
            onError={setError}
          />
        </Suspense>
      )}
    </div>
  );
}
