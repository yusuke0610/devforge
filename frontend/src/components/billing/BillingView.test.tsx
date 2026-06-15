import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { BILLING_PAGE_MESSAGES } from "../../constants/messages";

const createCheckoutSessionMock = vi.fn();
const refreshMock = vi.fn();
const showSuccessMock = vi.fn();
const showErrorMock = vi.fn();

vi.mock("../../api/billing", () => ({
  createCheckoutSession: (...args: unknown[]) => createCheckoutSessionMock(...args),
}));

vi.mock("../../hooks/useBillingPage", () => ({
  useBillingPage: () => ({
    balance: 12000,
    packs: [{ id: "starter", name: "スターター", price_jpy: 500, credits: 500 }],
    transactions: [],
    paidRate: 12,
    loading: false,
    error: null,
    refresh: refreshMock,
  }),
}));

vi.mock("../ui/toast", () => ({
  useToast: () => ({ showSuccess: showSuccessMock, showError: showErrorMock }),
}));

import { BillingView } from "./BillingView";

const originalLocation = window.location;

/**
 * window.location をテスト用のプレーンオブジェクトに差し替える。
 * jsdom の location.assign は spyOn で再定義できないため、location ごと置き換える。
 * history.replaceState はクエリ除去を再現するようモックする。
 */
function stubLocation(search: string) {
  const locationObj = {
    href: `http://localhost/billing${search}`,
    pathname: "/billing",
    search,
    assign: vi.fn(),
  };
  Object.defineProperty(window, "location", { configurable: true, value: locationObj });
  vi.spyOn(window.history, "replaceState").mockImplementation(((_s, _t, url) => {
    locationObj.search = "";
    if (url) locationObj.pathname = String(url);
  }) as typeof window.history.replaceState);
  return locationObj;
}

beforeEach(() => {
  createCheckoutSessionMock.mockReset();
  refreshMock.mockReset();
  showSuccessMock.mockReset();
  showErrorMock.mockReset();
});

afterEach(() => {
  Object.defineProperty(window, "location", { configurable: true, value: originalLocation });
  vi.restoreAllMocks();
});

describe("BillingView 決済導線（ADR-0012 Phase 2）", () => {
  it("購入ボタンで Checkout セッションを作成し、返却 URL へリダイレクトする", async () => {
    const location = stubLocation("");
    createCheckoutSessionMock.mockResolvedValue({
      checkout_url: "https://checkout.stripe.com/c/pay/cs_test_1",
    });

    render(<BillingView />);
    fireEvent.change(screen.getByLabelText(BILLING_PAGE_MESSAGES.INPUT_LABEL), {
      target: { value: "1000" },
    });
    fireEvent.click(screen.getByRole("button", { name: BILLING_PAGE_MESSAGES.PURCHASE_BUTTON }));

    await waitFor(() => {
      expect(createCheckoutSessionMock).toHaveBeenCalledWith(1000);
    });
    expect(location.assign).toHaveBeenCalledWith("https://checkout.stripe.com/c/pay/cs_test_1");
  });

  it("Checkout 作成に失敗したらエラートーストを出す（リダイレクトしない）", async () => {
    const location = stubLocation("");
    createCheckoutSessionMock.mockRejectedValue(new Error("失敗"));

    render(<BillingView />);
    fireEvent.change(screen.getByLabelText(BILLING_PAGE_MESSAGES.INPUT_LABEL), {
      target: { value: "1000" },
    });
    fireEvent.click(screen.getByRole("button", { name: BILLING_PAGE_MESSAGES.PURCHASE_BUTTON }));

    await waitFor(() => {
      expect(showErrorMock).toHaveBeenCalled();
    });
    expect(location.assign).not.toHaveBeenCalled();
  });

  it("?checkout=success で戻ると成功トーストを出し残高を再取得する", async () => {
    const location = stubLocation("?checkout=success");

    render(<BillingView />);

    await waitFor(() => {
      expect(showSuccessMock).toHaveBeenCalledWith(BILLING_PAGE_MESSAGES.CHECKOUT_SUCCESS);
    });
    expect(refreshMock).toHaveBeenCalled();
    // クエリは除去され、リロード時の再通知を防ぐ
    expect(location.search).toBe("");
  });

  it("?checkout=cancel で戻るとキャンセル通知のみ（再取得しない）", async () => {
    const location = stubLocation("?checkout=cancel");

    render(<BillingView />);

    await waitFor(() => {
      expect(showSuccessMock).toHaveBeenCalledWith(BILLING_PAGE_MESSAGES.CHECKOUT_CANCELED);
    });
    expect(refreshMock).not.toHaveBeenCalled();
    expect(location.search).toBe("");
  });
});
