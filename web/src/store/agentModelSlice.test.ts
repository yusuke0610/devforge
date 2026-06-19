import { describe, expect, it } from "vitest";

import reducer, { setAgentModel } from "./agentModelSlice";

describe("agentModelSlice", () => {
  it("初期状態は無料の haiku（誤課金を防ぐ安全側の既定）", () => {
    const state = reducer(undefined, { type: "@@INIT" });
    expect(state.model).toBe("haiku");
  });

  it("setAgentModel で sonnet に切り替わる", () => {
    const state = reducer({ model: "haiku" }, setAgentModel("sonnet"));
    expect(state.model).toBe("sonnet");
  });

  it("setAgentModel で haiku に戻せる", () => {
    const state = reducer({ model: "sonnet" }, setAgentModel("haiku"));
    expect(state.model).toBe("haiku");
  });
});
