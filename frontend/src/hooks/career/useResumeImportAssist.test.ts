import type { ChangeEvent } from "react";

import { act, renderHook } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { IMPORT_ASSIST_MESSAGES } from "../../constants/messages";
import { useResumeImportAssist } from "./useResumeImportAssist";

/** file input の change イベントを最小限スタブする（files は readonly のため defineProperty で設定）。 */
function makeChangeEvent(file: File | null): ChangeEvent<HTMLInputElement> {
  const input = document.createElement("input");
  input.type = "file";
  Object.defineProperty(input, "files", {
    value: file ? [file] : [],
    configurable: true,
  });
  return { target: input } as unknown as ChangeEvent<HTMLInputElement>;
}

/** 要素をフォーカスし、focusin を document まで伝播させて lastFocusedRef に記録させる。 */
function focusAndRegister(el: HTMLElement): void {
  el.focus();
  el.dispatchEvent(new FocusEvent("focusin", { bubbles: true }));
}

describe("useResumeImportAssist", () => {
  afterEach(() => {
    document.body.innerHTML = "";
  });

  it("handleFileChange で file と fileName を保持する", () => {
    const { result } = renderHook(() => useResumeImportAssist());
    const file = new File(["%PDF-1.4"], "resume.pdf", { type: "application/pdf" });

    act(() => result.current.handleFileChange(makeChangeEvent(file)));

    expect(result.current.file).toBe(file);
    expect(result.current.fileName).toBe("resume.pdf");
  });

  it("fillSelection はフォーカス中の入力欄へ流し込む", () => {
    const { result } = renderHook(() => useResumeImportAssist());
    const input = document.createElement("input");
    input.type = "text";
    document.body.appendChild(input);
    act(() => focusAndRegister(input));

    act(() => result.current.fillSelection("株式会社ABC"));

    expect(input.value).toBe("株式会社ABC");
    expect(result.current.error).toBeNull();
  });

  it("textarea には改行で追記する", () => {
    const { result } = renderHook(() => useResumeImportAssist());
    const textarea = document.createElement("textarea");
    textarea.value = "既存テキスト";
    document.body.appendChild(textarea);
    act(() => focusAndRegister(textarea));

    act(() => result.current.fillSelection("追記分"));

    expect(textarea.value).toBe("既存テキスト\n追記分");
  });

  it("流し込み先が未選択ならエラーを出す", () => {
    const { result } = renderHook(() => useResumeImportAssist());

    act(() => result.current.fillSelection("テキスト"));

    expect(result.current.error).toBe(IMPORT_ASSIST_MESSAGES.NO_TARGET);
  });

  it("空白だけの選択は流し込まずエラーも出さない", () => {
    const { result } = renderHook(() => useResumeImportAssist());

    act(() => result.current.fillSelection("   "));

    expect(result.current.error).toBeNull();
  });
});
