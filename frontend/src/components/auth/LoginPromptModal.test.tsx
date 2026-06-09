import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";

import { AUTH_PROMPT_MESSAGES } from "../../constants/messages";
import { LoginPromptModal } from "./LoginPromptModal";

// initiateGitHubLogin は実際に window.location.assign する副作用があるためモックする。
const initiateGitHubLogin = vi.fn<() => Promise<void>>().mockResolvedValue(undefined);
vi.mock("../../api", () => ({
  initiateGitHubLogin: (...args: unknown[]) => initiateGitHubLogin(...(args as [])),
}));

describe("LoginPromptModal", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("タイトルと説明を表示する", () => {
    render(<LoginPromptModal onClose={() => {}} />);

    expect(screen.getByText(AUTH_PROMPT_MESSAGES.TITLE)).toBeInTheDocument();
    expect(screen.getByText(AUTH_PROMPT_MESSAGES.DESCRIPTION)).toBeInTheDocument();
  });

  it("GitHubログインボタンで initiateGitHubLogin を呼ぶ", async () => {
    render(<LoginPromptModal onClose={() => {}} />);

    fireEvent.click(
      screen.getByRole("button", { name: AUTH_PROMPT_MESSAGES.GITHUB_LOGIN }),
    );

    await waitFor(() => {
      expect(initiateGitHubLogin).toHaveBeenCalledWith(window.location.origin);
    });
  });

  it("「あとで」で onClose を呼ぶ", () => {
    const onClose = vi.fn();
    render(<LoginPromptModal onClose={onClose} />);

    fireEvent.click(screen.getByRole("button", { name: AUTH_PROMPT_MESSAGES.LATER }));
    expect(onClose).toHaveBeenCalledTimes(1);
  });
});
