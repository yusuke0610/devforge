import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect } from "vitest";

import { Collapsible } from "./Collapsible";

describe("Collapsible", () => {
  /** 既定では開いた状態で中身が見える */
  it("defaultOpen 既定では中身が表示される", () => {
    render(
      <Collapsible title="資格">
        <p>中身テキスト</p>
      </Collapsible>,
    );
    expect(screen.getByText("中身テキスト")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "資格" })).toHaveAttribute("aria-expanded", "true");
  });

  /** ヘッダークリックで開閉がトグルする */
  it("ヘッダークリックで中身の表示/非表示が切り替わる", () => {
    render(
      <Collapsible title="資格">
        <p>中身テキスト</p>
      </Collapsible>,
    );
    const toggle = screen.getByRole("button", { name: "資格" });

    fireEvent.click(toggle);
    expect(screen.queryByText("中身テキスト")).not.toBeInTheDocument();
    expect(toggle).toHaveAttribute("aria-expanded", "false");

    fireEvent.click(toggle);
    expect(screen.getByText("中身テキスト")).toBeInTheDocument();
    expect(toggle).toHaveAttribute("aria-expanded", "true");
  });

  /** defaultOpen=false なら初期状態で畳まれている */
  it("defaultOpen=false なら初期状態で中身が非表示", () => {
    render(
      <Collapsible title="会社A" defaultOpen={false}>
        <p>会社の詳細</p>
      </Collapsible>,
    );
    expect(screen.queryByText("会社の詳細")).not.toBeInTheDocument();
  });

  /** headerActions はトグルの外側に描画される（畳んでいても見える） */
  it("headerActions は折りたたみ状態に関係なく表示される", () => {
    render(
      <Collapsible
        title="会社A"
        defaultOpen={false}
        headerActions={<button type="button">削除</button>}
      >
        <p>会社の詳細</p>
      </Collapsible>,
    );
    expect(screen.getByRole("button", { name: "削除" })).toBeInTheDocument();
    expect(screen.queryByText("会社の詳細")).not.toBeInTheDocument();
  });
});
