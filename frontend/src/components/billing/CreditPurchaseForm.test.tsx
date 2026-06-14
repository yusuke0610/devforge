import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { CreditPackResponse } from "../../api/types";
import { getModelOption } from "../../constants/agentModels";
import {
  BILLING_PAGE_MESSAGES,
  formatCreditAmount,
  formatYen,
  modelChatsEstimateLabel,
  purchaseRangeHint,
} from "../../constants/messages";
import {
  MAX_PURCHASE_CREDITS,
  MIN_PURCHASE_CREDITS,
  PAID_REFERENCE_MODEL,
} from "../../utils/creditEstimate";
import { CreditPurchaseForm } from "./CreditPurchaseForm";

const PACKS: CreditPackResponse[] = [
  { id: "starter", name: "スターター", price_jpy: 500, credits: 500 },
  { id: "standard", name: "スタンダード", price_jpy: 1000, credits: 1100 },
];

// 表示文言は SSoT（messages / agentModels）から取得し、リテラルを直書きしない
const PAID_MODEL_NAME = getModelOption(PAID_REFERENCE_MODEL).name;
const INPUT_LABEL = BILLING_PAGE_MESSAGES.INPUT_LABEL;
const PURCHASE_BUTTON = BILLING_PAGE_MESSAGES.PURCHASE_BUTTON;
const RANGE_HINT = purchaseRangeHint(MIN_PURCHASE_CREDITS, MAX_PURCHASE_CREDITS);

function renderForm(paidRate: number | null = 12, onPurchase = vi.fn()) {
  render(<CreditPurchaseForm packs={PACKS} paidRate={paidRate} onPurchase={onPurchase} />);
  return { onPurchase };
}

describe("CreditPurchaseForm", () => {
  it("入力に応じてリアルタイムで円換算と回数目安を表示する", () => {
    renderForm(12);
    const input = screen.getByLabelText(INPUT_LABEL);

    fireEvent.change(input, { target: { value: "1000" } });

    // 1 クレジット = ¥1
    expect(screen.getByText(formatYen(1000))).toBeTruthy();
    // 1,000 / 12 = 83 回
    expect(screen.getByText(modelChatsEstimateLabel(PAID_MODEL_NAME, 83), { exact: false })).toBeTruthy();
  });

  it("値を変えると円換算もその場で更新される", () => {
    renderForm(12);
    const input = screen.getByLabelText(INPUT_LABEL);

    fireEvent.change(input, { target: { value: "1000" } });
    expect(screen.getByText(formatYen(1000))).toBeTruthy();
    fireEvent.change(input, { target: { value: "2500" } });
    expect(screen.getByText(formatYen(2500))).toBeTruthy();
    expect(screen.queryByText(formatYen(1000))).toBeNull();
  });

  it("未入力・範囲外は購入ボタンが無効で入力ヒントを表示する", () => {
    renderForm();
    // 未入力
    expect(screen.getByRole("button", { name: PURCHASE_BUTTON })).toHaveProperty("disabled", true);
    expect(screen.getByText(RANGE_HINT)).toBeTruthy();
    // 下限未満
    fireEvent.change(screen.getByLabelText(INPUT_LABEL), { target: { value: "10" } });
    expect(screen.getByRole("button", { name: PURCHASE_BUTTON })).toHaveProperty("disabled", true);
  });

  it("preset を押すと入力欄が埋まり購入ボタンが有効になる", () => {
    renderForm();
    fireEvent.click(screen.getByRole("button", { name: formatCreditAmount(1100) }));

    expect(screen.getByLabelText(INPUT_LABEL)).toHaveProperty("value", "1100");
    expect(screen.getByText(formatYen(1100))).toBeTruthy();
    expect(screen.getByRole("button", { name: PURCHASE_BUTTON })).toHaveProperty("disabled", false);
  });

  it("有効な値で購入ボタンを押すと入力クレジット数で onPurchase が呼ばれる", () => {
    const { onPurchase } = renderForm();
    fireEvent.change(screen.getByLabelText(INPUT_LABEL), { target: { value: "3000" } });
    fireEvent.click(screen.getByRole("button", { name: PURCHASE_BUTTON }));

    expect(onPurchase).toHaveBeenCalledWith(3000);
  });

  it("paidRate が null（回数算出不能）なら円換算のみ表示する", () => {
    renderForm(null);
    fireEvent.change(screen.getByLabelText(INPUT_LABEL), { target: { value: "1000" } });

    expect(screen.getByText(formatYen(1000))).toBeTruthy();
    // paidRate=null では回数目安が描画されない。SSoT ヘルパーが生成する文言（部分一致）が
    // 不在であることで「Sonnet 約N回」が出ていないことを検証する
    expect(
      screen.queryByText(modelChatsEstimateLabel(PAID_MODEL_NAME, 83), { exact: false }),
    ).toBeNull();
  });
});
