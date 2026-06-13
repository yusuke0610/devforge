import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { CreditPackResponse } from "../../api/types";
import { CreditPurchaseForm } from "./CreditPurchaseForm";

const PACKS: CreditPackResponse[] = [
  { id: "starter", name: "スターター", price_jpy: 500, credits: 500 },
  { id: "standard", name: "スタンダード", price_jpy: 1000, credits: 1100 },
];

function renderForm(paidRate: number | null = 12, onPurchase = vi.fn()) {
  render(<CreditPurchaseForm packs={PACKS} paidRate={paidRate} onPurchase={onPurchase} />);
  return { onPurchase };
}

describe("CreditPurchaseForm", () => {
  it("入力に応じてリアルタイムで円換算と回数目安を表示する", () => {
    renderForm(12);
    const input = screen.getByLabelText("購入するクレジット数");

    fireEvent.change(input, { target: { value: "1000" } });

    // 1 クレジット = ¥1
    expect(screen.getByText("¥1,000")).toBeTruthy();
    // 1,000 / 12 = 83 回
    expect(screen.getByText(/Sonnet 約83回/)).toBeTruthy();
  });

  it("値を変えると円換算もその場で更新される", () => {
    renderForm(12);
    const input = screen.getByLabelText("購入するクレジット数");

    fireEvent.change(input, { target: { value: "1000" } });
    expect(screen.getByText("¥1,000")).toBeTruthy();
    fireEvent.change(input, { target: { value: "2500" } });
    expect(screen.getByText("¥2,500")).toBeTruthy();
    expect(screen.queryByText("¥1,000")).toBeNull();
  });

  it("未入力・範囲外は購入ボタンが無効で入力ヒントを表示する", () => {
    renderForm();
    // 未入力
    expect(screen.getByRole("button", { name: "購入する" })).toHaveProperty("disabled", true);
    expect(screen.getByText(/クレジットで入力してください/)).toBeTruthy();
    // 下限未満
    fireEvent.change(screen.getByLabelText("購入するクレジット数"), { target: { value: "10" } });
    expect(screen.getByRole("button", { name: "購入する" })).toHaveProperty("disabled", true);
  });

  it("preset を押すと入力欄が埋まり購入ボタンが有効になる", () => {
    renderForm();
    fireEvent.click(screen.getByRole("button", { name: "1,100" }));

    expect(screen.getByLabelText("購入するクレジット数")).toHaveProperty("value", "1100");
    expect(screen.getByText("¥1,100")).toBeTruthy();
    expect(screen.getByRole("button", { name: "購入する" })).toHaveProperty("disabled", false);
  });

  it("有効な値で購入ボタンを押すと入力クレジット数で onPurchase が呼ばれる", () => {
    const { onPurchase } = renderForm();
    fireEvent.change(screen.getByLabelText("購入するクレジット数"), { target: { value: "3000" } });
    fireEvent.click(screen.getByRole("button", { name: "購入する" }));

    expect(onPurchase).toHaveBeenCalledWith(3000);
  });

  it("paidRate が null（回数算出不能）なら円換算のみ表示する", () => {
    renderForm(null);
    fireEvent.change(screen.getByLabelText("購入するクレジット数"), { target: { value: "1000" } });

    expect(screen.getByText("¥1,000")).toBeTruthy();
    expect(screen.queryByText(/Sonnet 約/)).toBeNull();
  });
});
