import { createSlice, type PayloadAction } from "@reduxjs/toolkit";

import type { AgentModelAlias } from "../api/types";

/**
 * 使用する AI モデル（ADR-0012）のグローバル設定。
 *
 * モデル選択は「Agent ウィジェットのローカル状態」ではなく「アカウント横断の UI 設定」。
 * サイドバーに常時表示し、UserMenu のモデル選択モーダルから切り替える。
 * redux-persist で端末に永続化する（ドメインの事実ではないため DB には持たない）。
 */
interface AgentModelState {
  model: AgentModelAlias;
}

// 既定は無料の haiku（誤課金を防ぐ安全側の初期値）
const initialState: AgentModelState = { model: "haiku" };

const agentModelSlice = createSlice({
  name: "agentModel",
  initialState,
  reducers: {
    setAgentModel(state, action: PayloadAction<AgentModelAlias>) {
      state.model = action.payload;
    },
  },
});

export const { setAgentModel } = agentModelSlice.actions;
export default agentModelSlice.reducer;
