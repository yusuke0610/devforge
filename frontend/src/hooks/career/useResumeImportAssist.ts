import { useCallback, useEffect, useRef, useState } from "react";

import {
  extractResumeBlocks,
  type ResumeImportBlock,
} from "../../api/resumeImports";
import { IMPORT_ASSIST_MESSAGES, NETWORK_MESSAGES } from "../../constants/messages";

/**
 * PDF 取り込み補助（クリック流し込み・LLM 不使用）の状態とハンドラを束ねるフック。
 *
 * バックエンドが PDF を「割り当て候補ブロック（本文行 / 表セル）」に分解して返す。
 * ユーザーはフォームの入力欄をクリックして流し込み先を選び、ブロックをクリックすると
 * その内容が選択中の入力欄へ流し込まれる（意味づけ・階層づけは人間が行う）。
 *
 * 流し込み先は document の focusin で「最後にフォーカスした input/textarea」を覚える。
 * React 管理下の controlled input にも、ネイティブ value セッター経由で input イベントを
 * 発火させて反映する（既存フォームの各入力に手を入れずに済む）。流し込み後は対象へ
 * フォーカスを戻し、選択状態（:focus の緑枠）が維持され連続流し込みできるようにする。
 */

/** controlled input/textarea に値を流し込み、React の onChange を発火させる。 */
function assignToElement(el: HTMLInputElement | HTMLTextAreaElement, text: string): void {
  const isTextarea = el.tagName === "TEXTAREA";
  const proto = isTextarea ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
  const setter = Object.getOwnPropertyDescriptor(proto, "value")?.set;
  if (!setter) return;
  // テキストエリアは追記（複数ブロックを続けて流し込めるように）、その他は置換
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
  blocks: ResumeImportBlock[];
  usedIds: Set<number>;
  loading: boolean;
  error: string | null;
  fileName: string | null;
  handleFileChange: (e: React.ChangeEvent<HTMLInputElement>) => Promise<void>;
  handleBlockClick: (block: ResumeImportBlock) => void;
};

export function useResumeImportAssist(): UseResumeImportAssistReturn {
  const [blocks, setBlocks] = useState<ResumeImportBlock[]>([]);
  const [usedIds, setUsedIds] = useState<Set<number>>(new Set());
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [fileName, setFileName] = useState<string | null>(null);

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

  const handleFileChange = useCallback(async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    e.target.value = ""; // 同じファイルを再選択できるようにリセット
    setError(null);
    setLoading(true);
    try {
      const res = await extractResumeBlocks(file);
      setBlocks(res.blocks);
      setUsedIds(new Set());
      setFileName(file.name);
    } catch (err) {
      setError(err instanceof Error ? err.message : NETWORK_MESSAGES.REQUEST_FAILED);
      setBlocks([]);
      setFileName(null);
    } finally {
      setLoading(false);
    }
  }, []);

  const handleBlockClick = useCallback((block: ResumeImportBlock) => {
    const el = lastFocusedRef.current;
    if (!el) {
      setError(IMPORT_ASSIST_MESSAGES.NO_TARGET);
      return;
    }
    setError(null);
    assignToElement(el, block.text);
    // 流し込み先にフォーカスを戻す（緑枠を維持し、続けてブロックを流し込めるようにする）
    el.focus();
    setUsedIds((prev) => {
      const next = new Set(prev);
      next.add(block.id);
      return next;
    });
  }, []);

  return {
    blocks,
    usedIds,
    loading,
    error,
    fileName,
    handleFileChange,
    handleBlockClick,
  };
}
