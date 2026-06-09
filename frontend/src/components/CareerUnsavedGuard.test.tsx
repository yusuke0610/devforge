import { render } from "@testing-library/react";
import { Provider } from "react-redux";
import { configureStore } from "@reduxjs/toolkit";
import { describe, it, expect } from "vitest";

import { CareerUnsavedGuard } from "./CareerUnsavedGuard";
import formCacheReducer, { setBaseline, setCache } from "../store/formCacheSlice";
import { createInitialCareerForm } from "../formMappers";

/** formCache だけを持つ最小ストアを作る。 */
function makeStore() {
  return configureStore({ reducer: { formCache: formCacheReducer } });
}

/** career キャッシュへ baseline と（必要なら編集後の）form をセットする。 */
function seedCareer(store: ReturnType<typeof makeStore>, fullName: string) {
  const baseline = createInitialCareerForm();
  store.dispatch(setBaseline({ key: "career", baseline }));
  store.dispatch(
    setCache({
      key: "career",
      form: { ...createInitialCareerForm(), full_name: fullName },
      documentId: "resume-1",
    }),
  );
}

/** beforeunload を dispatch し、ハンドラが抑止したか（defaultPrevented）を返す。 */
function dispatchBeforeUnload(): boolean {
  const event = new Event("beforeunload", { cancelable: true });
  window.dispatchEvent(event);
  return event.defaultPrevented;
}

describe("CareerUnsavedGuard", () => {
  it("ログイン済みで未保存があると beforeunload を抑止する（別ページでも有効）", () => {
    const store = makeStore();
    seedCareer(store, "山田 太郎"); // baseline は空 → full_name 差分で dirty
    render(
      <Provider store={store}>
        <CareerUnsavedGuard isAuthenticated={true} />
      </Provider>,
    );
    expect(dispatchBeforeUnload()).toBe(true);
  });

  it("未ログインなら未保存があっても抑止しない", () => {
    const store = makeStore();
    seedCareer(store, "山田 太郎");
    render(
      <Provider store={store}>
        <CareerUnsavedGuard isAuthenticated={false} />
      </Provider>,
    );
    expect(dispatchBeforeUnload()).toBe(false);
  });

  it("ログイン済みでも未保存が無ければ抑止しない", () => {
    const store = makeStore();
    seedCareer(store, ""); // form === baseline（どちらも空） → dirty なし
    render(
      <Provider store={store}>
        <CareerUnsavedGuard isAuthenticated={true} />
      </Provider>,
    );
    expect(dispatchBeforeUnload()).toBe(false);
  });
});
