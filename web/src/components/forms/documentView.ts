import { useCallback } from "react";

/**
 * 原本ビュー（{@link MarkdownDocumentView} / {@link PdfDocumentView}）共通の Props。
 *
 * レンダリング技術（DOMPurify HTML / react-pdf）は実装ごとに異なるが、
 * 「ファイルを受け取り、テキスト選択を onFill に流し、描画エラーを onError で伝える」
 * という入出力契約は共通なのでここに集約する。
 */
export type DocumentViewProps = {
  /** 描画対象のファイル */
  file: File;
  /** ズーム倍率（1 = 等倍 / カラム幅フィット） */
  zoom?: number;
  /** 原本上で選択された文字列を流し込むコールバック */
  onFill: (text: string) => void;
  /** 描画エラー・エラー解除を親へ伝えるコールバック */
  onError: (message: string | null) => void;
};

/**
 * テキスト選択を「流し込み」に変換する共通ハンドラを返す。
 *
 * 選択文字列があれば onFill に渡し、流し込み後は選択を解除して
 * 次にどこを掴んだか分かりやすくする。Markdown / PDF 両ビューで共用する。
 */
export function useSelectionFill(onFill: (text: string) => void) {
  return useCallback(() => {
    const text = window.getSelection()?.toString() ?? "";
    if (!text.trim()) return;
    onFill(text);
    window.getSelection()?.removeAllRanges();
  }, [onFill]);
}
