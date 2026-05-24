import { describe, expect, it } from "vitest";

import reducer, {
  beginPolling,
  beginUpload,
  clearImport,
  markReady,
  setError,
  setProgress,
  type ResumeImportState,
} from "./resumeImportSlice";

const initial: ResumeImportState = {
  importId: null,
  phase: "idle",
  error: null,
  progress: null,
};

const sampleError: ResumeImportState["error"] = {
  code: "RESUME_IMPORT_INVALID",
  message: "PDF をアップロードしてください。",
  action: null,
  retryAfter: null,
  errorId: "err-1",
};

describe("resumeImportSlice", () => {
  it("初期状態は idle / importId=null / error=null", () => {
    const state = reducer(undefined, { type: "@@INIT" });
    expect(state).toEqual(initial);
  });

  it("beginUpload で uploading フェーズに遷移し importId / error / progress がクリアされる", () => {
    const start: ResumeImportState = {
      importId: "previous-id",
      phase: "error",
      error: sampleError,
      progress: {
        task_id: "previous-id",
        step_index: 2,
        total_steps: 3,
        step_label: "前回のステップ",
        sub_progress: null,
      },
    };
    const state = reducer(start, beginUpload());
    expect(state.phase).toBe("uploading");
    expect(state.importId).toBeNull();
    expect(state.error).toBeNull();
    expect(state.progress).toBeNull();
  });

  it("beginPolling で importId をセットして polling フェーズに遷移する", () => {
    const state = reducer(
      { ...initial, phase: "uploading" },
      beginPolling({ importId: "abc-123" }),
    );
    expect(state.phase).toBe("polling");
    expect(state.importId).toBe("abc-123");
    expect(state.error).toBeNull();
  });

  it("setProgress で進捗が上書きされる", () => {
    const next = {
      task_id: "abc-123",
      step_index: 2,
      total_steps: 3,
      step_label: "職務経歴書か判定中...",
      sub_progress: null,
    } as const;
    const state = reducer(
      { ...initial, importId: "abc-123", phase: "polling" },
      setProgress(next),
    );
    expect(state.progress).toEqual(next);
    // 他のフィールドは影響を受けない
    expect(state.phase).toBe("polling");
    expect(state.importId).toBe("abc-123");
  });

  it("setProgress(null) で進捗を消せる", () => {
    const start: ResumeImportState = {
      importId: "abc-123",
      phase: "polling",
      error: null,
      progress: {
        task_id: "abc-123",
        step_index: 1,
        total_steps: 3,
        step_label: "PDFテキスト抽出中...",
        sub_progress: null,
      },
    };
    const state = reducer(start, setProgress(null));
    expect(state.progress).toBeNull();
  });

  it("markReady で ready フェーズに遷移する（importId は維持）", () => {
    const start: ResumeImportState = {
      importId: "abc-123",
      phase: "polling",
      error: null,
      progress: null,
    };
    const state = reducer(start, markReady());
    expect(state.phase).toBe("ready");
    expect(state.importId).toBe("abc-123");
    expect(state.error).toBeNull();
  });

  it("setError で error フェーズに遷移しエラー情報が格納される", () => {
    const state = reducer(initial, setError(sampleError));
    expect(state.phase).toBe("error");
    expect(state.error).toEqual(sampleError);
  });

  it("clearImport で初期状態に戻る（progress も null になる）", () => {
    const start: ResumeImportState = {
      importId: "abc-123",
      phase: "ready",
      error: sampleError,
      progress: {
        task_id: "abc-123",
        step_index: 3,
        total_steps: 3,
        step_label: "完了",
        sub_progress: null,
      },
    };
    const state = reducer(start, clearImport());
    expect(state).toEqual(initial);
  });
});
