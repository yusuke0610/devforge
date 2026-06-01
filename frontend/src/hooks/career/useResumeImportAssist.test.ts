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

  it("handleFileChange で file と fileName を保持する（PDF は kind=pdf）", () => {
    const { result } = renderHook(() => useResumeImportAssist());
    const file = new File(["%PDF-1.4"], "resume.pdf", { type: "application/pdf" });

    act(() => result.current.handleFileChange(makeChangeEvent(file)));

    expect(result.current.file).toBe(file);
    expect(result.current.fileName).toBe("resume.pdf");
    expect(result.current.kind).toBe("pdf");
  });

  it(".md ファイルは kind=markdown として受け付ける", () => {
    const { result } = renderHook(() => useResumeImportAssist());
    const file = new File(["# 見出し"], "resume.md", { type: "text/markdown" });

    act(() => result.current.handleFileChange(makeChangeEvent(file)));

    expect(result.current.file).toBe(file);
    expect(result.current.fileName).toBe("resume.md");
    expect(result.current.kind).toBe("markdown");
  });

  it("MIME が空でも拡張子 .markdown で markdown と判定する", () => {
    const { result } = renderHook(() => useResumeImportAssist());
    const file = new File(["# 見出し"], "resume.markdown", { type: "" });

    act(() => result.current.handleFileChange(makeChangeEvent(file)));

    expect(result.current.kind).toBe("markdown");
  });

  it("未対応の拡張子は弾いてエラーを出す（file は保持しない）", () => {
    const { result } = renderHook(() => useResumeImportAssist());
    const file = new File(["hello"], "note.txt", { type: "text/plain" });

    act(() => result.current.handleFileChange(makeChangeEvent(file)));

    expect(result.current.file).toBeNull();
    expect(result.current.kind).toBeNull();
    expect(result.current.error).toBe(IMPORT_ASSIST_MESSAGES.UNSUPPORTED_TYPE);
  });

  it("2MB を超える Markdown は弾いてエラーを出す", () => {
    const { result } = renderHook(() => useResumeImportAssist());
    const huge = new File(["# 見出し"], "huge.md", { type: "text/markdown" });
    Object.defineProperty(huge, "size", { value: 3 * 1024 * 1024, configurable: true });

    act(() => result.current.handleFileChange(makeChangeEvent(huge)));

    expect(result.current.file).toBeNull();
    expect(result.current.kind).toBeNull();
    expect(result.current.error).toBe(IMPORT_ASSIST_MESSAGES.TOO_LARGE(2));
  });

  it("20MB を超える巨大ファイルは弾いてエラーを出す（file は保持しない）", () => {
    const { result } = renderHook(() => useResumeImportAssist());
    // 実バイト列を確保せず size だけ巨大に見せる（描画ガードの検証が目的）。
    const huge = new File(["%PDF-1.4"], "huge.pdf", { type: "application/pdf" });
    Object.defineProperty(huge, "size", { value: 21 * 1024 * 1024, configurable: true });

    act(() => result.current.handleFileChange(makeChangeEvent(huge)));

    expect(result.current.file).toBeNull();
    expect(result.current.fileName).toBeNull();
    expect(result.current.error).toBe(IMPORT_ASSIST_MESSAGES.TOO_LARGE(20));
  });

  it("有効な PDF 選択後に巨大ファイルを選ぶと、直前の選択をクリアする", () => {
    const { result } = renderHook(() => useResumeImportAssist());
    const valid = new File(["%PDF-1.4"], "resume.pdf", { type: "application/pdf" });

    act(() => result.current.handleFileChange(makeChangeEvent(valid)));
    expect(result.current.file).toBe(valid);
    expect(result.current.fileName).toBe("resume.pdf");

    // 実バイト列を確保せず size だけ巨大に見せる（描画ガードの検証が目的）。
    const huge = new File(["%PDF-1.4"], "huge.pdf", { type: "application/pdf" });
    Object.defineProperty(huge, "size", { value: 21 * 1024 * 1024, configurable: true });

    act(() => result.current.handleFileChange(makeChangeEvent(huge)));

    // 古い PDF が裏で描画され続けないよう、選択状態がクリアされていること。
    expect(result.current.file).toBeNull();
    expect(result.current.fileName).toBeNull();
    expect(result.current.error).toBe(IMPORT_ASSIST_MESSAGES.TOO_LARGE(20));
  });

  it("acceptFile（ドロップ等）は input を介さず File を直接受け入れる", () => {
    const { result } = renderHook(() => useResumeImportAssist());
    const file = new File(["# 見出し"], "dropped.md", { type: "text/markdown" });

    act(() => result.current.acceptFile(file));

    expect(result.current.file).toBe(file);
    expect(result.current.fileName).toBe("dropped.md");
    expect(result.current.kind).toBe("markdown");
  });

  it("acceptFile に未対応ファイルを渡すとエラーを出す", () => {
    const { result } = renderHook(() => useResumeImportAssist());
    const file = new File(["hello"], "note.txt", { type: "text/plain" });

    act(() => result.current.acceptFile(file));

    expect(result.current.file).toBeNull();
    expect(result.current.kind).toBeNull();
    expect(result.current.error).toBe(IMPORT_ASSIST_MESSAGES.UNSUPPORTED_TYPE);
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
