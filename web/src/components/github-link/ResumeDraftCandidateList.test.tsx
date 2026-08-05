import { render, screen, fireEvent } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { ResumeDraftCandidateResponse } from "../../api/types";
import { RESUME_DRAFT_CANDIDATE_MESSAGES } from "../../constants/messages";
import { ResumeDraftCandidateList } from "./ResumeDraftCandidateList";

function candidate(
  full_name: string,
  overrides: Partial<ResumeDraftCandidateResponse> = {},
): ResumeDraftCandidateResponse {
  return {
    full_name,
    description: "",
    duration_days: 400,
    implementation_volume: 12000,
    has_infra: false,
    technology_stacks: [],
    default_selected: true,
    reasons: [],
    ...overrides,
  };
}

describe("ResumeDraftCandidateList", () => {
  it("デフォルト非選択の候補も一覧に出し、理由バッジを表示する", () => {
    render(
      <ResumeDraftCandidateList
        candidates={[
          candidate("o/real"),
          candidate("o/tutorial", {
            default_selected: false,
            reasons: ["short_duration", "learning_topic"],
          }),
        ]}
        selected={["o/real"]}
        selectionLimit={5}
        loading={false}
        disabled={false}
        onToggle={vi.fn()}
      />,
    );

    // 機械は候補を落とさない（両方表示される）
    expect(screen.getByText("o/real")).toBeInTheDocument();
    expect(screen.getByText("o/tutorial")).toBeInTheDocument();
    expect(
      screen.getByText(RESUME_DRAFT_CANDIDATE_MESSAGES.REASON_LABELS.short_duration),
    ).toBeInTheDocument();
    expect(
      screen.getByText(RESUME_DRAFT_CANDIDATE_MESSAGES.REASON_LABELS.learning_topic),
    ).toBeInTheDocument();
  });

  it("非選択の候補もクリックで選び直せる（機械の判定を覆せる）", () => {
    const onToggle = vi.fn();
    render(
      <ResumeDraftCandidateList
        candidates={[candidate("o/tutorial", { default_selected: false, reasons: ["learning_topic"] })]}
        selected={[]}
        selectionLimit={5}
        loading={false}
        disabled={false}
        onToggle={onToggle}
      />,
    );

    fireEvent.click(screen.getByRole("checkbox"));
    expect(onToggle).toHaveBeenCalledWith("o/tutorial");
  });

  it("上限に達すると未選択だけ無効化し、選択済みは解除できる", () => {
    render(
      <ResumeDraftCandidateList
        candidates={[candidate("o/a"), candidate("o/b", { default_selected: false })]}
        selected={["o/a"]}
        selectionLimit={1}
        loading={false}
        disabled={false}
        onToggle={vi.fn()}
      />,
    );

    const [checkedBox, uncheckedBox] = screen.getAllByRole("checkbox");
    expect(checkedBox).toBeEnabled();
    expect(uncheckedBox).toBeDisabled();
    expect(screen.getByText(RESUME_DRAFT_CANDIDATE_MESSAGES.LIMIT_REACHED)).toBeInTheDocument();
  });

  it("候補が 0 件なら空表示にする", () => {
    render(
      <ResumeDraftCandidateList
        candidates={[]}
        selected={[]}
        selectionLimit={5}
        loading={false}
        disabled={false}
        onToggle={vi.fn()}
      />,
    );
    expect(screen.getByText(RESUME_DRAFT_CANDIDATE_MESSAGES.EMPTY)).toBeInTheDocument();
  });
});
