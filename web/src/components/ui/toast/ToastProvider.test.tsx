import { render, screen, fireEvent, act } from "@testing-library/react";
import type { ReactElement } from "react";
import { describe, it, expect, vi } from "vitest";

import { UI_MESSAGES } from "../../../constants/messages";
import type { AppErrorState } from "../../../utils/appError";
import { ToastProvider } from "./ToastProvider";
import { SUCCESS_TOAST_DURATION_MS, useToast } from "./toastContext";
import { useAppErrorToast, useMessageToast } from "./useToastBridge";

/** showSuccess / showError を任意のラベルから発火させるトリガーボタン。 */
function Trigger({ onClick, label }: { onClick: () => void; label: string }) {
  return (
    <button type="button" onClick={onClick}>
      {label}
    </button>
  );
}

/** useToast を呼び出してトリガーを描画するハーネス。 */
function ToastHarness({ render: renderTrigger }: { render: (api: ReturnType<typeof useToast>) => ReactElement }) {
  const api = useToast();
  return renderTrigger(api);
}

describe("ToastProvider / useToast", () => {
  it("showSuccess は成功トーストを表示し、一定時間で自動消去される", () => {
    vi.useFakeTimers();
    try {
      render(
        <ToastProvider>
          <ToastHarness
            render={({ showSuccess }) => (
              <Trigger label="出す" onClick={() => showSuccess("保存しました")} />
            )}
          />
        </ToastProvider>,
      );

      fireEvent.click(screen.getByText("出す"));
      expect(screen.getByText("保存しました")).toBeInTheDocument();

      act(() => {
        vi.advanceTimersByTime(SUCCESS_TOAST_DURATION_MS);
      });
      expect(screen.queryByText("保存しました")).not.toBeInTheDocument();
    } finally {
      vi.useRealTimers();
    }
  });

  it("showError(文字列) はエラートーストを表示し、自動消去されず手動で閉じられる", () => {
    vi.useFakeTimers();
    try {
      render(
        <ToastProvider>
          <ToastHarness
            render={({ showError }) => (
              <Trigger label="出す" onClick={() => showError("保存に失敗しました")} />
            )}
          />
        </ToastProvider>,
      );

      fireEvent.click(screen.getByText("出す"));
      expect(screen.getByText("保存に失敗しました")).toBeInTheDocument();

      // 自動消去時間を大きく超えても残り続ける（エラーは手動クローズ）。
      act(() => {
        vi.advanceTimersByTime(SUCCESS_TOAST_DURATION_MS * 3);
      });
      expect(screen.getByText("保存に失敗しました")).toBeInTheDocument();

      fireEvent.click(screen.getByRole("button", { name: UI_MESSAGES.TOAST_DISMISS }));
      expect(screen.queryByText("保存に失敗しました")).not.toBeInTheDocument();
    } finally {
      vi.useRealTimers();
    }
  });

  it("showError(AppErrorState) はメッセージと回復アクションボタンを表示する", () => {
    const appError: AppErrorState = {
      code: "AUTH_EXPIRED",
      message: "セッションが切れました",
      action: "再度ログインしてください",
      retryAfter: null,
      errorId: "err-auth-1",
    };
    render(
      <ToastProvider>
        <ToastHarness
          render={({ showError }) => (
            <Trigger label="出す" onClick={() => showError(appError)} />
          )}
        />
      </ToastProvider>,
    );

    fireEvent.click(screen.getByText("出す"));
    expect(screen.getByText("セッションが切れました")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "ログインし直す" })).toBeInTheDocument();
    expect(screen.getByText(/err-auth-1/)).toBeInTheDocument();
  });
});

/** message を prop で受け取り useMessageToast に橋渡しするハーネス。 */
function MessageBridgeHarness({ message }: { message: string | null }) {
  useMessageToast(message, "error");
  return null;
}

describe("useMessageToast", () => {
  it("message が非 null になった時だけ表示し、同一文言の重複表示を防ぐ", () => {
    const { rerender } = render(
      <ToastProvider>
        <MessageBridgeHarness message={null} />
      </ToastProvider>,
    );
    expect(screen.queryByText("失敗しました")).not.toBeInTheDocument();

    rerender(
      <ToastProvider>
        <MessageBridgeHarness message="失敗しました" />
      </ToastProvider>,
    );
    expect(screen.getAllByText("失敗しました")).toHaveLength(1);

    // 同じ message のまま再レンダリングしても増えない。
    rerender(
      <ToastProvider>
        <MessageBridgeHarness message="失敗しました" />
      </ToastProvider>,
    );
    expect(screen.getAllByText("失敗しました")).toHaveLength(1);
  });

  it("message が null に戻った後に同じ文言が再出現したら再表示する", () => {
    const { rerender } = render(
      <ToastProvider>
        <MessageBridgeHarness message="失敗しました" />
      </ToastProvider>,
    );
    expect(screen.getAllByText("失敗しました")).toHaveLength(1);

    rerender(
      <ToastProvider>
        <MessageBridgeHarness message={null} />
      </ToastProvider>,
    );
    rerender(
      <ToastProvider>
        <MessageBridgeHarness message="失敗しました" />
      </ToastProvider>,
    );
    // 先のトーストは手動クローズしていないため、再表示で 2 件になる。
    expect(screen.getAllByText("失敗しました")).toHaveLength(2);
  });
});

/** error を prop で受け取り useAppErrorToast に橋渡しするハーネス。 */
function AppErrorBridgeHarness({ error }: { error: AppErrorState | null }) {
  useAppErrorToast(error);
  return null;
}

describe("useAppErrorToast", () => {
  const makeError = (errorId: string): AppErrorState => ({
    code: "INTERNAL_ERROR",
    message: "連携に失敗しました",
    action: null,
    retryAfter: null,
    errorId,
  });

  it("errorId が変わった時だけ表示し、同一エラーの重複表示を防ぐ", () => {
    const { rerender } = render(
      <ToastProvider>
        <AppErrorBridgeHarness error={null} />
      </ToastProvider>,
    );
    expect(screen.queryByText("連携に失敗しました")).not.toBeInTheDocument();

    const first = makeError("e1");
    rerender(
      <ToastProvider>
        <AppErrorBridgeHarness error={first} />
      </ToastProvider>,
    );
    expect(screen.getAllByText("連携に失敗しました")).toHaveLength(1);

    // 同一 errorId の参照変更では増えない。
    rerender(
      <ToastProvider>
        <AppErrorBridgeHarness error={{ ...first }} />
      </ToastProvider>,
    );
    expect(screen.getAllByText("連携に失敗しました")).toHaveLength(1);

    // 新しい errorId では新規表示。
    rerender(
      <ToastProvider>
        <AppErrorBridgeHarness error={makeError("e2")} />
      </ToastProvider>,
    );
    expect(screen.getAllByText("連携に失敗しました")).toHaveLength(2);
  });

  it("errorId が空の場合は重複判定せず毎回表示する", () => {
    const { rerender } = render(
      <ToastProvider>
        <AppErrorBridgeHarness error={null} />
      </ToastProvider>,
    );

    // 空 errorId のエラーは重複判定の基準にできないため、別インスタンスごとに表示される。
    rerender(
      <ToastProvider>
        <AppErrorBridgeHarness error={makeError("")} />
      </ToastProvider>,
    );
    expect(screen.getAllByText("連携に失敗しました")).toHaveLength(1);

    rerender(
      <ToastProvider>
        <AppErrorBridgeHarness error={makeError("")} />
      </ToastProvider>,
    );
    expect(screen.getAllByText("連携に失敗しました")).toHaveLength(2);
  });
});
