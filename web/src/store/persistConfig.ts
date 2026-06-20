import storageImport from "redux-persist/lib/storage";
import type { PersistConfig, WebStorage } from "redux-persist";
import type { RootState } from "./index";

/**
 * redux-persist/lib/storage は CJS（`exports.default`）。
 * vite 8 / @vitejs/plugin-react 6 の CJS→ESM interop 変更により、
 * default import が namespace オブジェクト（`{ __esModule, default }`）として
 * 解決され、`storage.getItem` が undefined になり起動時に
 * `TypeError: storage.getItem is not a function` でアプリが描画されなくなる。
 * interop が正しい環境（vitest / build）では unwrap 不要なので、
 * default プロパティがあればそれを採用するフォールバックで両対応する。
 */
const storage: WebStorage =
  (storageImport as { default?: WebStorage }).default ?? storageImport;

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
