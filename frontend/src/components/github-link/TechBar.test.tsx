import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { TechBar } from "./TechBar";

describe("TechBar", () => {
  it("techs が空オブジェクトの場合は何も描画しない", () => {
    const { container } = render(<TechBar techs={{}} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("渡された各ツール名を凡例として表示する", () => {
    render(<TechBar techs={{ React: 3, FastAPI: 2, Docker: 1 }} />);
    expect(screen.getByText("React")).toBeInTheDocument();
    expect(screen.getByText("FastAPI")).toBeInTheDocument();
    expect(screen.getByText("Docker")).toBeInTheDocument();
  });

  it("割合（%）が表示される", () => {
    render(<TechBar techs={{ React: 1 }} />);
    expect(screen.getByText("100.0%")).toBeInTheDocument();
  });

  it("リポジトリ数の多い順に並ぶ", () => {
    render(<TechBar techs={{ Vue: 1, React: 3, FastAPI: 2 }} />);
    const texts = screen
      .getAllByText(/^(React|FastAPI|Vue)$/)
      .map((el) => el.textContent);
    expect(texts.indexOf("React")).toBeLessThan(texts.indexOf("FastAPI"));
    expect(texts.indexOf("FastAPI")).toBeLessThan(texts.indexOf("Vue"));
  });
});
