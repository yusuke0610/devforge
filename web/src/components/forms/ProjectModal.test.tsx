import { fireEvent, render, screen } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { ProjectModal } from "./ProjectModal";
import { VALIDATION_MESSAGES } from "../../constants/messages";
import type { CareerProjectForm } from "../../payloadBuilders";
import type { UseResumeImportAssistReturn } from "../../hooks/career/useResumeImportAssist";

// 取り込みパネルは react-pdf / pdf.js を遅延ロードするため、ProjectModal の単体テストでは
// スタブに差し替える。ここでは「ファイルがある時だけ右カラムに再掲されるか」だけを検証する。
const PANEL_MARKER = "原本ビュー(stub)";
vi.mock("./ResumeSourceTracePanel", () => ({
  ResumeSourceTracePanel: () => <div>{PANEL_MARKER}</div>,
}));

const invalidDateProject: CareerProjectForm = {
  name: "テスト",
  periods: [{ start_date: "2024-12", end_date: "2024-01", is_current: false }],
  role: "エンジニア",
  description: "",
  team: { total: "", members: [] },
  technology_stacks: [],
  phases: [],
};

const emptyProject: CareerProjectForm = {
  name: "",
  periods: [{ start_date: "", end_date: "", is_current: false }],
  role: "",
  description: "",
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
  kind: "pdf",
  error: null,
  handleFileChange: vi.fn(),
  acceptFile: vi.fn(),
  fillSelection: vi.fn(),
  setError: vi.fn(),
  ...overrides,
});

describe("ProjectModal", () => {
  /** 保存ボタンは廃止され、入力のたびに onSave が即時に呼ばれること */
  it("入力すると onSave が即時に呼ばれる（保存ボタンなし）", () => {
    const onSave = vi.fn();
    render(
      <ProjectModal
        project={emptyProject}
        onSave={onSave}
        onClose={vi.fn()}
        techStackNamesByCategory={new Map()}
      />,
    );
    // 保存ボタンは存在しない。
    expect(screen.queryByRole("button", { name: "保存" })).toBeNull();
    // プロジェクト名を入力すると即時に onSave が呼ばれる。
    const nameInput = screen.getByPlaceholderText(
      "例: エネルギー業界 IoT Web API アプリ新規開発",
    );
    fireEvent.change(nameInput, { target: { value: "新規PJ" } });
    expect(onSave).toHaveBeenCalled();
    const lastCall = onSave.mock.calls[onSave.mock.calls.length - 1];
    expect(lastCall?.[0]).toMatchObject({ name: "新規PJ" });
  });

  /** 開始日 > 終了日 のとき期間エラーをインライン表示すること */
  it("開始日が終了日より後の場合に期間エラーをインライン表示する", () => {
    render(
      <ProjectModal
        project={invalidDateProject}
        onSave={vi.fn()}
        onClose={vi.fn()}
        techStackNamesByCategory={new Map()}
      />,
    );
    expect(screen.getByText(VALIDATION_MESSAGES.DATE_RANGE_INVALID)).toBeInTheDocument();
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

  /** autoFocus 指定で該当期間の開始入力にフォーカス＆ aria-invalid が付くこと */
  it("autoFocus で指定された期間の開始入力にフォーカスし aria-invalid を付ける", () => {
    render(
      <ProjectModal
        project={emptyProject}
        onSave={vi.fn()}
        onClose={vi.fn()}
        techStackNamesByCategory={new Map()}
        autoFocus={{ periodIndex: 0, field: "start_date" }}
      />,
    );
    // 「開始」ラベルの month input が対象。
    const startInput = document.querySelector(
      'input[type="month"][aria-invalid="true"]',
    ) as HTMLInputElement | null;
    expect(startInput).not.toBeNull();
    expect(document.activeElement).toBe(startInput);
  });
});
