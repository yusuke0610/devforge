import { useCallback, useEffect, useRef, useState } from "react";

import { IMPORT_ASSIST_MESSAGES } from "../../constants/messages";

/**
 * ファイル取り込み補助（原本ビュー上の選択 → 入力欄へ流し込み）の状態とハンドラを束ねるフック。
 *
 * 選択したファイル（PDF / Markdown）は右カラム（{@link ResumeSourceTracePanel}）に原本のまま
 * 描画される。ユーザーはフォームの入力欄をクリックして流し込み先を選び、原本上でテキストを
 * ドラッグ選択すると、その文字列が選択中の入力欄へ流し込まれる（意味づけ・粒度は人間が決める）。
 *
 * 流し込み先は document の focusin で「最後にフォーカスした input/textarea」を覚える。
 * React 管理下の controlled input にも、ネイティブ value セッター経由で input イベントを
 * 発火させて反映する（既存フォームの各入力に手を入れずに済む）。流し込み後は対象へ
 * フォーカスを戻し、選択状態（:focus の緑枠）を維持して連続流し込みできるようにする。
 *
 * レンダラー（PDF / Markdown）は描画側で `kind` を見て切り替える。流し込み・フォーカス
 * 追跡のロジックは `window.getSelection()` ベースでレンダラー非依存。
 */

/** 取り込み対象のファイル種別。 */
export type ImportFileKind = "pdf" | "markdown";

/** file input の accept 属性（受け入れ可能な拡張子/MIME）。{@link detectKind} と対で更新する。 */
export const IMPORT_FILE_ACCEPT = "application/pdf,.md,.markdown,text/markdown";

/**
 * 種別ごとの最大バイト数。
 *
 * このガードは Cloud Run のコスト対策ではない（取り込みはブラウザ内描画のみで、
 * ファイルのバイト列はサーバーに送信されない）。目的は巨大ファイルの描画で
 * ブラウザがフリーズ/OOM するのを防ぐこと。
 * - PDF: pdf.js が全ページを一括レンダリングするため緩めの 20MB。
 * - Markdown: テキスト→DOM 展開のみで軽量だが、極端に巨大なものは弾く 2MB。
 */
const MAX_FILE_BYTES: Record<ImportFileKind, number> = {
  pdf: 20 * 1024 * 1024,
  markdown: 2 * 1024 * 1024,
};

/** ファイル名・MIME からファイル種別を判定する（未対応なら null）。 */
function detectKind(file: File): ImportFileKind | null {
  const name = file.name.toLowerCase();
  if (file.type === "application/pdf" || name.endsWith(".pdf")) return "pdf";
  if (
    file.type === "text/markdown" ||
    file.type === "text/x-markdown" ||
    name.endsWith(".md") ||
    name.endsWith(".markdown")
  ) {
    return "markdown";
  }
  return null;
}

/**
 * controlled input/textarea のカーソル位置に値を流し込み、React の onChange を発火させる。
 *
 * native value セッターで全置換 + 末尾改行追記していた旧実装は、(1) カーソル位置を無視して
 * 末尾に改行付きで追記される、(2) ブラウザの undo 履歴に乗らず Cmd+Z で戻せない、という
 * 2 つの不満があった。`document.execCommand("insertText")` はカーソル位置に挿入しつつ
 * ネイティブの undo 履歴に記録し、`input` イベントも自然発火して React の onChange に反映される。
 * execCommand は非推奨 API だが、プログラム挿入で undo を保つ代替手段が無いため採用する。
 */
function assignToElement(el: HTMLInputElement | HTMLTextAreaElement, text: string): void {
  el.focus();
  if (typeof document.execCommand === "function" && document.execCommand("insertText", false, text)) {
    return;
  }
  // フォールバック（execCommand 非対応環境: jsdom 等）。
  // selectionStart/End からカーソル位置に挿入し、native setter + input イベントで React に反映する。
  insertAtCaretFallback(el, text);
}

/** execCommand が使えない環境向けに、カーソル位置への挿入を手動で再現するフォールバック。 */
function insertAtCaretFallback(el: HTMLInputElement | HTMLTextAreaElement, text: string): void {
  const proto = el.tagName === "TEXTAREA" ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
  const setter = Object.getOwnPropertyDescriptor(proto, "value")?.set;
  if (!setter) return;
  const start = el.selectionStart ?? el.value.length;
  const end = el.selectionEnd ?? el.value.length;
  const next = `${el.value.slice(0, start)}${text}${el.value.slice(end)}`;
  setter.call(el, next);
  // caret を挿入したテキストの直後に移動し、続けて流し込めるようにする。
  const caret = start + text.length;
  el.setSelectionRange(caret, caret);
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
  /** 描画対象として選択中のファイル（未選択時は null） */
  file: File | null;
  fileName: string | null;
  /** 選択中ファイルの種別（描画側のレンダラー切替に使う）。未選択時は null。 */
  kind: ImportFileKind | null;
  error: string | null;
  handleFileChange: (e: React.ChangeEvent<HTMLInputElement>) => void;
  /** ドラッグ&ドロップ等で得た File を直接受け入れる（input 以外の導線用）。 */
  acceptFile: (file: File | null | undefined) => void;
  /** 原本上で選択された文字列を、選択中（最後にフォーカスした）入力欄へ流し込む。 */
  fillSelection: (text: string) => void;
  /** 原本描画/選択側で起きたエラーを表示するためのセッター。 */
  setError: (message: string | null) => void;
};

export function useResumeImportAssist(): UseResumeImportAssistReturn {
  const [file, setFile] = useState<File | null>(null);
  const [fileName, setFileName] = useState<string | null>(null);
  const [kind, setKind] = useState<ImportFileKind | null>(null);
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

  // 前回選択したファイルが残ったままだと、エラー表示の裏で古い原本が描画され続けるため、
  // エラー時はまず選択状態をクリアしてからエラーを出す。
  const clearSelection = useCallback(() => {
    setFile(null);
    setFileName(null);
    setKind(null);
  }, []);

  // ファイル選択（input）/ ドラッグ&ドロップ共通の受け入れ処理。種別・サイズを検証して採用する。
  const acceptFile = useCallback(
    (selected: File | null | undefined) => {
      if (!selected) return;
      const detected = detectKind(selected);
      if (!detected) {
        clearSelection();
        setError(IMPORT_ASSIST_MESSAGES.UNSUPPORTED_TYPE);
        return;
      }
      // 巨大ファイルは描画でブラウザがフリーズするため、描画前に弾く（上限は種別ごと）。
      const maxBytes = MAX_FILE_BYTES[detected];
      if (selected.size > maxBytes) {
        clearSelection();
        setError(IMPORT_ASSIST_MESSAGES.TOO_LARGE(maxBytes / (1024 * 1024)));
        return;
      }
      setError(null);
      setFile(selected);
      setFileName(selected.name);
      setKind(detected);
    },
    [clearSelection],
  );

  const handleFileChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const selected = e.target.files?.[0];
      e.target.value = ""; // 同じファイルを再選択できるようにリセット
      acceptFile(selected);
    },
    [acceptFile],
  );

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
    kind,
    error,
    handleFileChange,
    acceptFile,
    fillSelection,
    setError,
  };
}
