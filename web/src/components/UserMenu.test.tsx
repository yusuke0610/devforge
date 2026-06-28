import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect } from "vitest";

import { UserMenu } from "./UserMenu";
import { UI_MESSAGES } from "../constants/messages";
import { APP_VERSION } from "../utils/appVersion";

/** 認証済み状態の UserMenu を描画する最小ヘルパー。 */
function renderMenu() {
  return render(
    <UserMenu
      isAuthenticated={true}
      username="testuser"
      theme="light"
      onToggleTheme={() => {}}
      onLogout={() => {}}
      onLogin={() => {}}
    />,
  );
}

describe("UserMenu", () => {
  it("メニューを開くとフッターにコピーライトとアプリバージョンを併記する", () => {
    renderMenu();
    // メニューはトリガー押下で初めて開く（フッターはその中にある）。
    fireEvent.click(screen.getByRole("button", { name: /testuser/ }));
    // vitest 環境では VITE_APP_VERSION 未注入のため APP_VERSION は "dev" になる。
    expect(
      screen.getByText(`${UI_MESSAGES.COPYRIGHT} · ${APP_VERSION}`),
    ).toBeTruthy();
  });
});
