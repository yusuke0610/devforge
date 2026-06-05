import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";

import { DeleteIconButton } from "./DeleteIconButton";

describe("DeleteIconButton", () => {
  /** label が aria-label として描画され、アクセシブルネームで参照できる */
  it("label が aria-label として描画される", () => {
    render(<DeleteIconButton label="職務経歴を削除" onClick={() => {}} />);
    expect(screen.getByRole("button", { name: "職務経歴を削除" })).toBeInTheDocument();
  });

  /** クリックで onClick が呼ばれる */
  it("クリックで onClick が呼ばれる", () => {
    const onClick = vi.fn();
    render(<DeleteIconButton label="取引先を削除" onClick={onClick} />);

    fireEvent.click(screen.getByRole("button", { name: "取引先を削除" }));
    expect(onClick).toHaveBeenCalledTimes(1);
  });

  /** クリックは親要素へ伝播しない（見出し内のトグルを誤発火させない） */
  it("クリックが親要素へ伝播しない", () => {
    const onParentClick = vi.fn();
    const onClick = vi.fn();
    render(
      <div onClick={onParentClick}>
        <DeleteIconButton label="資格を削除" onClick={onClick} />
      </div>,
    );

    fireEvent.click(screen.getByRole("button", { name: "資格を削除" }));
    expect(onClick).toHaveBeenCalledTimes(1);
    expect(onParentClick).not.toHaveBeenCalled();
  });
});
