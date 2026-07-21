import { configureStore } from "@reduxjs/toolkit";
import { fireEvent, render, screen, within } from "@testing-library/react";
import type { ReactNode } from "react";
import { Provider } from "react-redux";
import { describe, expect, it, vi } from "vitest";

import { AGENT_MODEL_OPTIONS } from "../../constants/agentModels";
import { AGENT_MODEL_MESSAGES } from "../../constants/messages";
import agentModelReducer from "../../store/agentModelSlice";
import { ModelSelectModal } from "./ModelSelectModal";

// 表示文言は SSoT（constants/agentModels）から引き、テストと正本の乖離を防ぐ。
const HAIKU_NAME = AGENT_MODEL_OPTIONS.find((option) => option.alias === "haiku")!.name;
const SONNET_NAME = AGENT_MODEL_OPTIONS.find((option) => option.alias === "sonnet")!.name;
const haikuNamePattern = new RegExp(`^${HAIKU_NAME}`);
const sonnetNamePattern = new RegExp(`^${SONNET_NAME}`);

type Store = ReturnType<typeof makeStore>;

function makeStore(model: "haiku" | "sonnet" = "haiku") {
  return configureStore({
    reducer: { agentModel: agentModelReducer },
    preloadedState: { agentModel: { model } },
  });
}

function renderModal(opts: { store?: Store; onClose?: () => void }) {
  const store = opts.store ?? makeStore();
  const wrapper = (ui: ReactNode) => <Provider store={store}>{ui}</Provider>;
  render(wrapper(<ModelSelectModal onClose={opts.onClose ?? vi.fn()} />));
  return store;
}

describe("ModelSelectModal", () => {
  it("Haiku / Sonnet のカードが表示される", () => {
    renderModal({});
    expect(screen.getByRole("button", { name: haikuNamePattern })).toBeTruthy();
    expect(screen.getByRole("button", { name: sonnetNamePattern })).toBeTruthy();
  });

  it("現在選択中のモデルカードに『選択中』が付く", () => {
    renderModal({ store: makeStore("sonnet") });
    const sonnetCard = screen.getByRole("button", { name: sonnetNamePattern });
    expect(within(sonnetCard).getByText(AGENT_MODEL_MESSAGES.CURRENT_BADGE)).toBeTruthy();
  });

  it("カードを押すとグローバル設定が切り替わり、モーダルが閉じる", () => {
    const onClose = vi.fn();
    const store = renderModal({ onClose });

    fireEvent.click(screen.getByRole("button", { name: sonnetNamePattern }));

    expect(store.getState().agentModel.model).toBe("sonnet");
    expect(onClose).toHaveBeenCalledTimes(1);
  });
});
