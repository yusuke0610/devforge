import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { ProjectModal } from "./ProjectModal";
import type { CareerProjectForm } from "../../payloadBuilders";
import type { UseResumeImportAssistReturn } from "../../hooks/career/useResumeImportAssist";

// 取り込みパネルは react-pdf / pdf.js を遅延ロードするため、ProjectModal の単体テストでは
// スタブに差し替える。ここでは「PDF がある時だけ右カラムに再掲されるか」だけを検証する。
const PANEL_MARKER = "PDF原本ビュー(stub)";
vi.mock("./ResumePdfTracePanel", () => ({
  ResumePdfTracePanel: () => <div>{PANEL_MARKER}</div>,
}));

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

/** PDF を選択済みの取り込み補助のモックを生成する */
const makeAssist = (
  overrides: Partial<UseResumeImportAssistReturn> = {},
): UseResumeImportAssistReturn => ({
  file: new File(["%PDF-1.4"], "resume.pdf", { type: "application/pdf" }),
  fileName: "resume.pdf",
  error: null,
  handleFileChange: vi.fn(),
  fillSelection: vi.fn(),
  setError: vi.fn(),
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

  /** PDF が選択済みの時、子モーダル内に原本ビューを再掲すること */
  it("PDFが選択済みだとモーダル内に原本ビューを表示する", () => {
    render(
      <ProjectModal
        project={emptyProject}
        onSave={vi.fn()}
        onClose={vi.fn()}
        techStackNamesByCategory={new Map()}
        assist={makeAssist()}
      />,
    );
    expect(screen.getByText(PANEL_MARKER)).toBeInTheDocument();
  });

  /** PDF 未選択の時は取り込みパネルを表示しないこと */
  it("PDF未選択の時はモーダル内に原本ビューを出さない", () => {
    render(
      <ProjectModal
        project={emptyProject}
        onSave={vi.fn()}
        onClose={vi.fn()}
        techStackNamesByCategory={new Map()}
        assist={makeAssist({ file: null, fileName: null })}
      />,
    );
    expect(screen.queryByText(PANEL_MARKER)).not.toBeInTheDocument();
  });
});
