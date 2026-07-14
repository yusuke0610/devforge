import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { useGitHubSkills } from "./useGitHubSkills";
import type { GitHubSkillItem } from "../api/types";

const getGitHubSkillsMock = vi.fn();
const proposeSkillDisplayNamesMock = vi.fn();
const confirmSkillDisplayDecisionsMock = vi.fn();

vi.mock("../api/githubLink", () => ({
  getGitHubSkills: (...args: unknown[]) => getGitHubSkillsMock(...args),
  proposeSkillDisplayNames: (...args: unknown[]) => proposeSkillDisplayNamesMock(...args),
  confirmSkillDisplayDecisions: (...args: unknown[]) =>
    confirmSkillDisplayDecisionsMock(...args),
}));

function skill(overrides: Partial<GitHubSkillItem>): GitHubSkillItem {
  return {
    kind: "package",
    canonical_name: "react",
    ecosystem: "npm",
    parent: null,
    display_name: null,
    confirmed_display_name: null,
    group_id: null,
    decision_source: null,
    decision_reviewed: false,
    evidence: [],
    proficiency: null,
    ...overrides,
  } as GitHubSkillItem;
}

beforeEach(() => {
  getGitHubSkillsMock.mockReset();
  proposeSkillDisplayNamesMock.mockReset();
  confirmSkillDisplayDecisionsMock.mockReset();
});

describe("useGitHubSkills", () => {
  it("マウント時にスキルを取得しグループ化する（success）", async () => {
    getGitHubSkillsMock.mockResolvedValue({ skills: [skill({ canonical_name: "react" })] });

    const { result } = renderHook(() => useGitHubSkills("haiku"));

    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.skills).toHaveLength(1);
    expect(result.current.groups).toHaveLength(1);
    expect(result.current.error).toBeNull();
  });

  it("取得失敗時は error にメッセージが入る（error）", async () => {
    getGitHubSkillsMock.mockRejectedValue("network down");

    const { result } = renderHook(() => useGitHubSkills("haiku"));

    await waitFor(() => expect(result.current.error).not.toBeNull());
    expect(result.current.skills).toHaveLength(0);
  });

  it("propose で提案を編集可能な状態として保持する", async () => {
    getGitHubSkillsMock.mockResolvedValue({ skills: [skill({})] });
    proposeSkillDisplayNamesMock.mockResolvedValue({
      groups: [
        {
          display_name: "React",
          members: [{ kind: "package", ecosystem: "npm", canonical_name: "react" }],
        },
      ],
    });

    const { result } = renderHook(() => useGitHubSkills("haiku"));
    await waitFor(() => expect(result.current.loading).toBe(false));

    await act(async () => {
      await result.current.propose();
    });

    expect(result.current.proposal).toHaveLength(1);
    expect(result.current.proposal?.[0].displayName).toBe("React");
    expect(result.current.proposal?.[0].originalDisplayName).toBe("React");
  });

  it("confirm で確定 API を呼び、返却された最新一覧で置き換え提案をクリアする", async () => {
    getGitHubSkillsMock.mockResolvedValue({ skills: [skill({})] });
    proposeSkillDisplayNamesMock.mockResolvedValue({
      groups: [
        {
          display_name: "React",
          members: [{ kind: "package", ecosystem: "npm", canonical_name: "react" }],
        },
      ],
    });
    confirmSkillDisplayDecisionsMock.mockResolvedValue({
      skills: [skill({ confirmed_display_name: "React" })],
    });

    const { result } = renderHook(() => useGitHubSkills("haiku"));
    await waitFor(() => expect(result.current.loading).toBe(false));
    await act(async () => {
      await result.current.propose();
    });
    await act(async () => {
      await result.current.confirm();
    });

    expect(confirmSkillDisplayDecisionsMock).toHaveBeenCalledTimes(1);
    const payload = confirmSkillDisplayDecisionsMock.mock.calls[0][0];
    expect(payload.decisions[0].canonical_name).toBe("react");
    expect(payload.decisions[0].display_name).toBe("React");
    expect(result.current.proposal).toBeNull();
    expect(result.current.skills[0].confirmed_display_name).toBe("React");
  });

  it("提案の表示名を編集でき、破棄でクリアできる", async () => {
    getGitHubSkillsMock.mockResolvedValue({ skills: [skill({})] });
    proposeSkillDisplayNamesMock.mockResolvedValue({
      groups: [
        {
          display_name: "react",
          members: [{ kind: "package", ecosystem: "npm", canonical_name: "react" }],
        },
      ],
    });

    const { result } = renderHook(() => useGitHubSkills("haiku"));
    await waitFor(() => expect(result.current.loading).toBe(false));
    await act(async () => {
      await result.current.propose();
    });

    act(() => result.current.updateProposalName(0, "React"));
    expect(result.current.proposal?.[0].displayName).toBe("React");

    act(() => result.current.discardProposal());
    expect(result.current.proposal).toBeNull();
  });
});
