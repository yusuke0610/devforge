import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { ContributionHeatmap } from "./ContributionHeatmap";
import type { ContributionCalendar } from "../../api";

function makeCalendar(): ContributionCalendar {
  return {
    total_contributions: 15,
    weeks: [
      [
        { date: "2024-01-01", count: 0, level: 0 },
        { date: "2024-01-02", count: 4, level: 2 },
        { date: "2024-01-03", count: 9, level: 4 },
      ],
      [
        { date: "2024-02-05", count: 2, level: 1 },
        { date: "2024-02-06", count: 0, level: 0 },
      ],
    ],
  };
}

describe("ContributionHeatmap", () => {
  it("年間コントリビュート総数を表示する", () => {
    render(<ContributionHeatmap calendar={makeCalendar()} />);
    expect(screen.getByText("15")).toBeInTheDocument();
    expect(screen.getByText("年間コントリビュート")).toBeInTheDocument();
  });

  it("各日セルに日付とコントリビューション数の title を付ける", () => {
    render(<ContributionHeatmap calendar={makeCalendar()} />);
    expect(
      screen.getByTitle("2024-01-03: 9 contributions"),
    ).toBeInTheDocument();
    expect(
      screen.getByTitle("2024-02-05: 2 contributions"),
    ).toBeInTheDocument();
  });

  it("最大連続日数を算出する（count>0 の連続セル）", () => {
    // 実データは全日が連続して並ぶ。0 で途切れ、最大連続は 3。
    const calendar: ContributionCalendar = {
      total_contributions: 6,
      weeks: [
        [
          { date: "2024-03-01", count: 1, level: 1 },
          { date: "2024-03-02", count: 2, level: 1 },
          { date: "2024-03-03", count: 3, level: 2 },
          { date: "2024-03-04", count: 0, level: 0 },
          { date: "2024-03-05", count: 5, level: 3 },
        ],
      ],
    };
    render(<ContributionHeatmap calendar={calendar} />);
    expect(screen.getByText("最大連続日数")).toBeInTheDocument();
    expect(screen.getByText("3")).toBeInTheDocument();
  });

  it("月が変わる週に月ラベルを表示する", () => {
    render(<ContributionHeatmap calendar={makeCalendar()} />);
    expect(screen.getByText("Jan")).toBeInTheDocument();
    expect(screen.getByText("Feb")).toBeInTheDocument();
  });

  it("空の weeks でもクラッシュしない", () => {
    render(
      <ContributionHeatmap
        calendar={{ total_contributions: 0, weeks: [] }}
      />,
    );
    // total=0 / streak=0 の 2 枚のカードが描画される
    expect(screen.getAllByText("0")).toHaveLength(2);
    expect(screen.getByText("最大連続日数")).toBeInTheDocument();
  });
});
