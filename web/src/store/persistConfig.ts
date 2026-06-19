import storage from "redux-persist/lib/storage";
import type { PersistConfig } from "redux-persist";
import type { RootState } from "./index";

/**
 * redux-persist 設定。
 * blacklist 方式を採用: 新スライス追加時は PII を含むか確認し、
 * 含む場合は必ず blacklist に追加すること。
 */
export const persistConfig: PersistConfig<RootState> = {
  key: "devforge",
  storage,
  // PII・機密情報を含むスライスは永続化禁止
  blacklist: ["formCache"],
};
