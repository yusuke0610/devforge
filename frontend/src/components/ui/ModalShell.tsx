import { useRef, type CSSProperties, type ReactNode } from "react";

import type { UseResumeImportAssistReturn } from "../../hooks/career/useResumeImportAssist";
import { useImportPanelLayout } from "../../hooks/career/useImportPanelLayout";
import { UI_MESSAGES } from "../../constants/messages";
import { ResumeSourceTracePanel } from "../forms/ResumeSourceTracePanel";
import styles from "./ModalShell.module.css";

/** 取り込みパネル列のリサイズ初期値（ProjectModal の従来値を既定にする） */
type ImportPanelLayoutOptions = {
  initialWidth?: number;
  minWidth?: number;
  minFormWidth?: number;
  reservedGap?: number;
};

type Props = {
  /** ヘッダー左に表示するタイトル */
  title: ReactNode;
  /** モーダルを閉じるコールバック（× / オーバーレイクリック共通） */
  onClose: () => void;
  /**
   * 取り込み補助。ファイルが選択されている時はモーダル内の右カラムに原本ビューを再掲する。
   * モーダルのオーバーレイ（position:fixed）が画面右の本体パネルを覆ってクリックを奪うため、
   * 子モーダルを開いている間でも参照できるようモーダル内に再掲する。
   */
  assist?: UseResumeImportAssistReturn;
  /** 入力フォーム本体（左カラムに配置される） */
  children: ReactNode;
  /** 取り込みパネル列のリサイズ初期値の上書き */
  importPanelLayout?: ImportPanelLayoutOptions;
};

/**
 * 職務経歴書フォームのモーダル外枠を共通化したシェル。
 * オーバーレイ・ヘッダー（× 閉じる）・左右 2 カラム（入力フォーム / 取り込み原本ビュー）と
 * スプリッターによる左右リサイズを担う。ProjectModal / MarkdownFieldModal が共有する。
 */
export function ModalShell({ title, onClose, assist, children, importPanelLayout }: Props) {
  /** 取り込みファイルが選択されている時だけモーダル内に原本ビューを表示する */
  const showPdf = !!assist && !!assist.file;

  // 入力フォームと原本カラムの比率をスプリッターのドラッグで変える。
  const bodyWrapRef = useRef<HTMLDivElement>(null);
  const { width: pdfWidth, startResize } = useImportPanelLayout(bodyWrapRef, {
    initialWidth: 440,
    minWidth: 240,
    minFormWidth: 320,
    reservedGap: 6,
    ...importPanelLayout,
  });

  return (
    <div className={styles.overlay} onClick={onClose}>
      <div className={styles.modal} onClick={(e) => e.stopPropagation()}>
        <div className={styles.header}>
          <span>{title}</span>
          <button
            type="button"
            className={styles.closeButton}
            onClick={onClose}
            aria-label={UI_MESSAGES.MODAL_CLOSE}
          >
            &times;
          </button>
        </div>

        <div
          className={styles.bodyWrap}
          ref={bodyWrapRef}
          style={showPdf ? ({ "--pdf-col-width": `${pdfWidth}px` } as CSSProperties) : undefined}
        >
          <div className={styles.body}>{children}</div>
          {showPdf && assist && (
            <>
              {/* 入力フォームと原本カラムの境界。ドラッグで左右比率を変える（縦積み時は CSS で非表示）。 */}
              <div
                className={styles.splitter}
                role="separator"
                aria-orientation="vertical"
                onMouseDown={startResize}
              />
              <aside className={styles.blocksColumn}>
                <ResumeSourceTracePanel assist={assist} />
              </aside>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
