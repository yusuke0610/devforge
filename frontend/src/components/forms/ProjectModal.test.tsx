import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { ProjectModal } from "./ProjectModal";
import type { CareerProjectForm } from "../../payloadBuilders";
import type { UseResumeImportAssistReturn } from "../../hooks/career/useResumeImportAssist";

const invalidDateProject: CareerProjectForm = {
  name: "テスト",
  start_date: "2024-12",
  end_date: "2024-01",
  is_current: false,
  role: "エンジニア",
  challenge: "",
  action: "",
  result: "",
  team: { total: "", members: [] },
  technology_stacks: [],
  phases: [],
};

const emptyProject: CareerProjectForm = {
  name: "",
  start_date: "",
  end_date: "",
  is_current: false,
  role: "",
  challenge: "",
  action: "",
  result: "",
  team: { total: "", members: [] },
  technology_stacks: [],
  phases: [],
};

/** 抽出ブロックを持つ取り込み補助のモックを生成する */
const makeAssist = (
  overrides: Partial<UseResumeImportAssistReturn> = {},
): UseResumeImportAssistReturn => ({
  blocks: [{ id: 1, kind: "line", text: "抽出テキストA" }],
  usedIds: new Set(),
  loading: false,
  error: null,
  fileName: "resume.pdf",
  handleFileChange: vi.fn(),
  handleBlockClick: vi.fn(),
  ...overrides,
});

describe("ProjectModal", () => {
  /** 開始日 > 終了日 のとき保存ボタンが disabled になること */
  it("開始日が終了日より後の場合に保存ボタンが disabled になる", () => {
    render(
      <ProjectModal
        project={invalidDateProject}
        onSave={vi.fn()}
        onClose={vi.fn()}
        techStackNamesByCategory={new Map()}
      />,
    );
    expect(screen.getByRole("button", { name: "保存" })).toBeDisabled();
  });

  /** assist にブロックがある時、子モーダル内に取り込みパネルを表示すること */
  it("抽出ブロックがあるとモーダル内に取り込みパネルを表示する", () => {
    render(
      <ProjectModal
        project={emptyProject}
        onSave={vi.fn()}
        onClose={vi.fn()}
        techStackNamesByCategory={new Map()}
        assist={makeAssist()}
      />,
    );
    // ブロックがモーダル内（オーバーレイの上）に並び、クリックできる
    expect(screen.getByRole("button", { name: /抽出テキストA/ })).toBeInTheDocument();
  });

  /** モーダル内のブロックをクリックすると流し込みハンドラが呼ばれること */
  it("モーダル内ブロックのクリックで handleBlockClick が呼ばれる", () => {
    const handleBlockClick = vi.fn();
    render(
      <ProjectModal
        project={emptyProject}
        onSave={vi.fn()}
        onClose={vi.fn()}
        techStackNamesByCategory={new Map()}
        assist={makeAssist({ handleBlockClick })}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: /抽出テキストA/ }));
    expect(handleBlockClick).toHaveBeenCalledWith({ id: 1, kind: "line", text: "抽出テキストA" });
  });

  /** 抽出ブロックが無い時は取り込みパネルを表示しないこと */
  it("抽出ブロックが無い時はモーダル内に取り込みパネルを出さない", () => {
    render(
      <ProjectModal
        project={emptyProject}
        onSave={vi.fn()}
        onClose={vi.fn()}
        techStackNamesByCategory={new Map()}
        assist={makeAssist({ blocks: [], fileName: null })}
      />,
    );
    expect(screen.queryByText("抽出テキストA")).not.toBeInTheDocument();
  });
});
