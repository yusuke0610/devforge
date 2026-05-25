import { useCallback, useEffect, useRef, useState } from "react";

import { IMPORT_ASSIST_MESSAGES } from "../../constants/messages";

/**
 * PDF 取り込み補助（PDF ビュー上の選択 → 入力欄へ流し込み）の状態とハンドラを束ねるフック。
 *
 * 選択した PDF は右カラム（{@link ResumePdfTracePanel}）に原本のまま描画される。
 * ユーザーはフォームの入力欄をクリックして流し込み先を選び、PDF 上でテキストをドラッグ
 * 選択すると、その文字列が選択中の入力欄へ流し込まれる（意味づけ・粒度は人間が決める）。
 *
 * 流し込み先は document の focusin で「最後にフォーカスした input/textarea」を覚える。
 * React 管理下の controlled input にも、ネイティブ value セッター経由で input イベントを
 * 発火させて反映する（既存フォームの各入力に手を入れずに済む）。流し込み後は対象へ
 * フォーカスを戻し、選択状態（:focus の緑枠）を維持して連続流し込みできるようにする。
 */

/** controlled input/textarea に値を流し込み、React の onChange を発火させる。 */
function assignToElement(el: HTMLInputElement | HTMLTextAreaElement, text: string): void {
  const isTextarea = el.tagName === "TEXTAREA";
  const proto = isTextarea ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
  const setter = Object.getOwnPropertyDescriptor(proto, "value")?.set;
  if (!setter) return;
  // テキストエリアは追記（複数箇所を続けて流し込めるように）、その他は置換
  const next = isTextarea && el.value.trim() ? `${el.value}\n${text}` : text;
  setter.call(el, next);
  el.dispatchEvent(new Event("input", { bubbles: true }));
}

/** 流し込み対象にできない input type（テキスト系のみ許可する）。 */
const NON_FILLABLE_INPUT_TYPES = new Set([
  "file",
  "checkbox",
  "radio",
  "range",
  "color",
  "submit",
  "button",
  "image",
]);

export type UseResumeImportAssistReturn = {
  /** 描画対象として選択中の PDF（未選択時は null） */
  file: File | null;
  fileName: string | null;
  error: string | null;
  handleFileChange: (e: React.ChangeEvent<HTMLInputElement>) => void;
  /** PDF 上で選択された文字列を、選択中（最後にフォーカスした）入力欄へ流し込む。 */
  fillSelection: (text: string) => void;
  /** PDF 描画/選択側で起きたエラーを表示するためのセッター。 */
  setError: (message: string | null) => void;
};

export function useResumeImportAssist(): UseResumeImportAssistReturn {
  const [file, setFile] = useState<File | null>(null);
  const [fileName, setFileName] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  // 最後にフォーカスした「流し込み先」入力欄
  const lastFocusedRef = useRef<HTMLInputElement | HTMLTextAreaElement | null>(null);

  useEffect(() => {
    const onFocusIn = (e: FocusEvent) => {
      const target = e.target as HTMLElement | null;
      if (!target) return;
      if (target.tagName === "TEXTAREA") {
        lastFocusedRef.current = target as HTMLTextAreaElement;
        return;
      }
      if (target.tagName === "INPUT") {
        const input = target as HTMLInputElement;
        if (NON_FILLABLE_INPUT_TYPES.has(input.type)) return;
        lastFocusedRef.current = input;
      }
    };
    document.addEventListener("focusin", onFocusIn);
    return () => document.removeEventListener("focusin", onFocusIn);
  }, []);

  const handleFileChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const selected = e.target.files?.[0];
    e.target.value = ""; // 同じファイルを再選択できるようにリセット
    if (!selected) return;
    setError(null);
    setFile(selected);
    setFileName(selected.name);
  }, []);

  const fillSelection = useCallback((text: string) => {
    const trimmed = text.trim();
    if (!trimmed) return;
    const el = lastFocusedRef.current;
    if (!el) {
      setError(IMPORT_ASSIST_MESSAGES.NO_TARGET);
      return;
    }
    setError(null);
    assignToElement(el, trimmed);
    // 流し込み先にフォーカスを戻す（緑枠を維持し、続けて流し込めるようにする）
    el.focus();
  }, []);

  return {
    file,
    fileName,
    error,
    handleFileChange,
    fillSelection,
    setError,
  };
}
