/**
 * テスト用レンダリングヘルパー。
 * Redux Provider・MemoryRouter・ToastProvider をラップして提供する。
 */
import { type ReactElement } from "react";
import { render, type RenderOptions } from "@testing-library/react";
import { Provider } from "react-redux";
import { MemoryRouter, type MemoryRouterProps } from "react-router-dom";
import { configureStore } from "@reduxjs/toolkit";
import agentModelReducer from "../store/agentModelSlice";
import formCacheReducer from "../store/formCacheSlice";
import { ToastProvider } from "../components/ui/toast";

interface Options extends Omit<RenderOptions, "wrapper"> {
  /** 文字列パス、または state を含む location オブジェクトを渡せる */
  initialEntries?: MemoryRouterProps["initialEntries"];
}

export function renderWithProviders(
  ui: ReactElement,
  { initialEntries = ["/"], ...options }: Options = {},
) {
  // 実 store（store/index.ts）と同じ slice 構成に揃える（agentModel は
  // GitHubLinkDashboard 等が useAppSelector で参照するため欠けると落ちる）
  const store = configureStore({
    reducer: { formCache: formCacheReducer, agentModel: agentModelReducer },
  });

  function Wrapper({ children }: { children: React.ReactNode }) {
    return (
      <Provider store={store}>
        <MemoryRouter initialEntries={initialEntries}>
          <ToastProvider>{children}</ToastProvider>
        </MemoryRouter>
      </Provider>
    );
  }

  return { store, ...render(ui, { wrapper: Wrapper, ...options }) };
}
