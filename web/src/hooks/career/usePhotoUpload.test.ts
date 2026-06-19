import { renderHook } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { usePhotoUpload } from "./usePhotoUpload";

describe("usePhotoUpload", () => {
  /** canvas モックのセットアップ（jsdom では canvas が使えないため） */
  beforeEach(() => {
    HTMLCanvasElement.prototype.getContext = vi.fn().mockReturnValue({
      drawImage: vi.fn(),
    });
    HTMLCanvasElement.prototype.toDataURL = vi
      .fn()
      .mockReturnValue("data:image/jpeg;base64,mock");
  });

  /**
   * handleFileChange に File を渡すと onPhotoChange が base64 文字列で呼ばれること。
   * canvas の toDataURL が呼ばれていること。
   */
  it("handleFileChange に File を渡すと onPhotoChange が base64 文字列で呼ばれる", async () => {
    const onPhotoChange = vi.fn();
    const { result } = renderHook(() => usePhotoUpload(onPhotoChange));

    const file = new File(["dummy"], "photo.jpg", { type: "image/jpeg" });

    // FileReader と Image の非同期処理を制御するために Promise でラップ
    await new Promise<void>((resolve) => {
      // FileReader.prototype.readAsDataURL の完了後に onload が呼ばれる流れを模倣
      const originalReadAsDataURL = FileReader.prototype.readAsDataURL;
      FileReader.prototype.readAsDataURL = vi.fn().mockImplementation(function (
        this: FileReader,
      ) {
        // すぐに onload を発火させる
        setTimeout(() => {
          Object.defineProperty(this, "result", {
            value: "data:image/jpeg;base64,original",
            writable: true,
          });

          // Image.onload をシミュレート
          const originalImage = globalThis.Image;
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          (globalThis as any).Image = class MockImage {
            onload: (() => void) | null = null;
            set src(_value: string) {
              // src がセットされたら onload を非同期で呼ぶ
              setTimeout(() => {
                if (this.onload) this.onload();
                // Image コンストラクタを元に戻す
                // eslint-disable-next-line @typescript-eslint/no-explicit-any
                (globalThis as any).Image = originalImage;
                FileReader.prototype.readAsDataURL = originalReadAsDataURL;
                resolve();
              }, 0);
            }
          };

          if (this.onload) {
            this.onload(new ProgressEvent("load") as ProgressEvent<FileReader>);
          }
        }, 0);
      });

      const event = {
        target: { files: [file] },
      } as unknown as React.ChangeEvent<HTMLInputElement>;

      result.current.handleFileChange(event);
    });

    expect(HTMLCanvasElement.prototype.toDataURL).toHaveBeenCalled();
    expect(onPhotoChange).toHaveBeenCalledWith("data:image/jpeg;base64,mock");
  });

  /** File が存在しない場合は onPhotoChange が呼ばれないこと */
  it("files が空の場合は onPhotoChange が呼ばれない", () => {
    const onPhotoChange = vi.fn();
    const { result } = renderHook(() => usePhotoUpload(onPhotoChange));

    const event = {
      target: { files: [] },
    } as unknown as React.ChangeEvent<HTMLInputElement>;

    result.current.handleFileChange(event);

    expect(onPhotoChange).not.toHaveBeenCalled();
  });
});
