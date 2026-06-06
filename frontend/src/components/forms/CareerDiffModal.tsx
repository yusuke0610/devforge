import { useMemo, useRef } from "react";

import { DIFF_DIALOG_MESSAGES as D, PROOFREAD_MESSAGES as P } from "../../constants/messages";
import type { ProofreadIssue } from "../../proofread/types";
import { buildReviewEntries } from "../../utils/careerReview";
import type { CareerChange, ChangeKind } from "../../utils/careerDiff";
import {
  annotateHtml,
  buildPathKindMap,
  foldUnchanged,
  injectRemovedPlaceholders,
} from "../../utils/diffHighlight";
import styles from "./CareerDiffModal.module.css";

/** 種別ごとのバッジ文言。 */
const KIND_LABEL: Record<ChangeKind, string> = {
  modified: D.MODIFIED_LABEL,
  added: D.ADDED_LABEL,
  removed: D.REMOVED_LABEL,
};

/**
 * iframe 内に注入する diff 着色 CSS。backend の resume.css に追記する形で srcDoc に埋め込む。
 * 緑=追加 / 赤=削除 / 黄=修正。VSCode 系 diff の配色に寄せる。
 * 校正指摘は青の波線（diff の背景色と重ねても潰れないよう下線で表現）。
 */
const DIFF_CSS = `
  body { margin: 0; padding: 12px 16px; background: #fff; }
  .diff-mark { border-radius: 2px; padding: 0 1px; }
  .diff-added { background: rgba(22,163,74,0.18); box-shadow: 0 0 0 1px rgba(22,163,74,0.45); }
  .diff-removed { background: rgba(220,38,38,0.16); box-shadow: 0 0 0 1px rgba(220,38,38,0.40); }
  .diff-modified { background: rgba(234,179,8,0.25); box-shadow: 0 0 0 1px rgba(234,179,8,0.50); }
  .diff-proofread {
    text-decoration: underline wavy #2563eb;
    text-decoration-skip-ink: none;
    text-underline-offset: 2px;
  }
  details.fold { margin: 3px 0; }
  summary.fold-summary {
    cursor: pointer; list-style: none; font-size: 8pt; color: #6b7280;
    background: #f3f4f6; border: 1px dashed #cbd5e1; border-radius: 4px; padding: 2px 8px;
  }
  summary.fold-summary::-webkit-details-marker { display: none; }
  summary.fold-summary::before { content: "▸ "; }
  details[open] > summary.fold-summary::before { content: "▾ "; }
  .diff-removed-stub {
    font-size: 8pt; color: #b91c1c; background: rgba(220,38,38,0.08);
    border: 1px dashed rgba(220,38,38,0.5); border-radius: 4px; padding: 2px 6px; margin: 2px 0;
  }
  .diff-removed-stub td { border: none; color: #b91c1c; }
`;

function buildSrcDoc(css: string, bodyHtml: string): string {
  return (
    "<!DOCTYPE html><html lang=\"ja\"><head><meta charset=\"utf-8\">" +
    `<style>${css}\n${DIFF_CSS}</style></head><body>${bodyHtml}</body></html>`
  );
}

/**
 * 経歴書 保存時の左右 diff モーダル（VSCode フォーク風）。
 *
 * 左=保存済み(baseline) / 右=編集中(form) を PDF と同じ整形レイアウト（iframe srcdoc）で並べ、
 * 変更箇所を緑/赤/黄でハイライト。右サイドバーに変更点リストを出し、各行で項目別ロールバック。
 */
export function CareerDiffModal({
  changes,
  baselineHtml,
  editedHtml,
  css,
  loading,
  error,
  saving,
  issues,
  proofreading,
  proofreadError,
  onConfirm,
  onCancel,
  onRollback,
}: {
  changes: CareerChange[];
  baselineHtml: string | null;
  editedHtml: string | null;
  css: string;
  loading: boolean;
  error: string | null;
  saving: boolean;
  /** 編集中フォームの校正指摘（フィールド横断）。 */
  issues: ProofreadIssue[];
  /** 校正処理中フラグ。 */
  proofreading: boolean;
  /** 校正失敗時のメッセージ（null なら正常）。 */
  proofreadError: string | null;
  onConfirm: () => void;
  onCancel: () => void;
  onRollback: (change: CareerChange) => void;
}) {
  const editedFrameRef = useRef<HTMLIFrameElement>(null);
  const hasChanges = changes.length > 0;

  const pathKindMap = useMemo(() => buildPathKindMap(changes), [changes]);

  /**
   * 変更点と校正指摘を 1 本のレビュー一覧へ統合し、PDF レイアウト順に並べる。
   * 左右ペイン（PDF）とサイドバーの縦順が一致し、上から順に突合できる。
   */
  const reviewEntries = useMemo(() => buildReviewEntries(changes, issues), [changes, issues]);

  /** 校正指摘のあるフィールド id 集合（編集中ペインの青マーク／折りたたみ除外に使う）。 */
  const proofreadFieldIds = useMemo(
    () => new Set(issues.map((issue) => issue.fieldId)),
    [issues],
  );

  // 着色（annotateHtml）→ 変更なし領域を畳む（foldUnchanged）の順で整形する。
  // baseline（保存済み）側は校正マークを付けない（指摘は編集中フォームに対するもの）。
  const baselineDoc = useMemo(() => {
    if (baselineHtml === null) return null;
    return buildSrcDoc(css, foldUnchanged(annotateHtml(baselineHtml, pathKindMap), pathKindMap));
  }, [baselineHtml, css, pathKindMap]);

  const editedDoc = useMemo(() => {
    if (editedHtml === null) return null;
    // 着色（差分＋校正青マーク）→ 削除跡のプレースホルダ挿入 → 変更なし領域の折りたたみ。
    // 校正指摘のある項目は畳まないよう foldUnchanged にも fieldId 集合を渡す。
    const annotated = annotateHtml(editedHtml, pathKindMap, proofreadFieldIds);
    const withStubs = injectRemovedPlaceholders(annotated, changes);
    return buildSrcDoc(css, foldUnchanged(withStubs, pathKindMap, proofreadFieldIds));
  }, [editedHtml, css, pathKindMap, changes, proofreadFieldIds]);

  /** レビュー項目クリックで、右ペイン（編集中）の該当ノードへスクロールする。 */
  const scrollToPath = (fp: string) => {
    const doc = editedFrameRef.current?.contentDocument;
    if (!doc) return;
    const escaped = CSS.escape(fp);
    const target =
      doc.querySelector(`[data-fp="${escaped}"]`) ??
      doc.querySelector(`[data-fp^="${escaped}."]`);
    target?.scrollIntoView({ block: "center", behavior: "smooth" });
  };

  return (
    <div
      className={styles.overlay}
      onClick={() => {
        // 保存処理中は背景クリックでの閉じ操作を無効化する（処理中状態を隠さない）。
        if (!saving) onCancel();
      }}
    >
      <div
        className={styles.modal}
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-label={D.TITLE}
      >
        <div className={styles.header}>
          <h2 className={styles.title}>{D.TITLE}</h2>
          <p className={styles.description}>{D.DESCRIPTION}</p>
        </div>

        <div className={styles.body}>
          {/* 左: 保存済み */}
          <section className={styles.pane}>
            <div className={styles.paneHead}>{D.PANE_BASELINE}</div>
            {baselineDoc ? (
              <iframe
                className={styles.frame}
                title={D.PANE_BASELINE}
                sandbox="allow-same-origin"
                srcDoc={baselineDoc}
              />
            ) : (
              <div className={styles.placeholder}>{D.BASELINE_EMPTY}</div>
            )}
          </section>

          {/* 右: 編集中 */}
          <section className={styles.pane}>
            <div className={styles.paneHead}>{D.PANE_EDITED}</div>
            {error ? (
              <div className={styles.placeholder}>{error}</div>
            ) : editedDoc ? (
              <iframe
                ref={editedFrameRef}
                className={styles.frame}
                title={D.PANE_EDITED}
                sandbox="allow-same-origin"
                srcDoc={editedDoc}
              />
            ) : (
              <div className={styles.placeholder}>{D.PREVIEW_LOADING}</div>
            )}
            {loading && editedDoc && <div className={styles.refetching}>{D.PREVIEW_LOADING}</div>}
          </section>

          {/* レビュー一覧: 変更点と校正を 1 本に統合し PDF レイアウト順に並べる。 */}
          <aside className={styles.sidebar}>
            <div className={styles.sidebarHead}>
              <span>{D.REVIEW_HEADING}</span>
              {proofreading && <span className={styles.proofreadLoading}>{P.LOADING}</span>}
            </div>
            {proofreadError && <p className={styles.proofreadEmpty}>{proofreadError}</p>}
            {reviewEntries.length > 0 ? (
              <ul className={styles.list}>
                {reviewEntries.map((entry) => (
                  <li key={entry.path} className={styles.entry}>
                    <button
                      type="button"
                      className={styles.entryHead}
                      onClick={() => scrollToPath(entry.path)}
                    >
                      <span className={styles.label}>{entry.label}</span>
                    </button>

                    {/* 差分（変更点）。バッジ＋旧→新＋元に戻す。 */}
                    {entry.changes.map((change) => (
                      <div key={`${change.path.join("/")}:${change.kind}`} className={styles.entryDiff}>
                        <div className={styles.diffMain}>
                          <span className={`${styles.badge} ${styles[change.kind]}`}>
                            {KIND_LABEL[change.kind]}
                          </span>
                          <span className={styles.values}>
                            {change.kind !== "added" && (
                              <span className={styles.oldValue}>
                                {change.oldValue || D.EMPTY_VALUE}
                              </span>
                            )}
                            {change.kind === "modified" && <span className={styles.arrow}>→</span>}
                            {change.kind !== "removed" && (
                              <span className={styles.newValue}>
                                {change.newValue || D.EMPTY_VALUE}
                              </span>
                            )}
                          </span>
                        </div>
                        <button
                          type="button"
                          className={styles.rollback}
                          onClick={() => onRollback(change)}
                          disabled={saving}
                          aria-label={D.ROLLBACK}
                          title={D.ROLLBACK}
                        >
                          ↩
                        </button>
                      </div>
                    ))}

                    {/* 校正の指摘（青）。誤字脱字・表記ゆれ。保存はブロックしない。 */}
                    {entry.issues.length > 0 && (
                      <ul className={styles.entryIssues}>
                        {entry.issues.map((issue, i) => (
                          <li
                            key={`${issue.ruleId}:${issue.index}:${i}`}
                            className={styles.proofreadItem}
                          >
                            <p className={styles.proofreadMessage}>{issue.message}</p>
                            {issue.excerpt && (
                              <p className={styles.proofreadExcerpt}>{issue.excerpt}</p>
                            )}
                          </li>
                        ))}
                      </ul>
                    )}
                  </li>
                ))}
              </ul>
            ) : (
              !proofreading && !proofreadError && <p className={styles.empty}>{D.NO_CHANGES}</p>
            )}
            <p className={styles.proofreadHint}>{P.HINT}</p>
          </aside>
        </div>

        <div className={styles.actions}>
          <button
            type="button"
            className="primary"
            onClick={onConfirm}
            disabled={saving || !hasChanges}
          >
            {D.CONFIRM}
          </button>
          <button type="button" onClick={onCancel} disabled={saving}>
            {D.CANCEL}
          </button>
        </div>
      </div>
    </div>
  );
}
