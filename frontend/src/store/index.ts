import { combineReducers, configureStore } from "@reduxjs/toolkit";
import { persistReducer, persistStore } from "redux-persist";
import { useDispatch, useSelector, type TypedUseSelectorHook } from "react-redux";
import agentModelReducer from "./agentModelSlice";
import formCacheReducer from "./formCacheSlice";
import { persistConfig } from "./persistConfig";

const rootReducer = combineReducers({
  formCache: formCacheReducer,
  // 使用モデルのグローバル設定（永続化する。PII を含まない / ADR-0012）
  agentModel: agentModelReducer,
});

/** persistConfig の blacklist に基づき機密スライスを除外した永続化リデューサー */
const persistedReducer = persistReducer(persistConfig, rootReducer);

export const store = configureStore({
  reducer: persistedReducer,
  middleware: (getDefaultMiddleware) =>
    getDefaultMiddleware({
      serializableCheck: {
        // redux-persist の内部アクションは非シリアライズ可能なため除外
        ignoredActions: ["persist/PERSIST", "persist/REHYDRATE"],
      },
    }),
});

export const persistor = persistStore(store);

export type RootState = ReturnType<typeof rootReducer>;
export type AppDispatch = typeof store.dispatch;

export const useAppDispatch: () => AppDispatch = useDispatch;
export const useAppSelector: TypedUseSelectorHook<RootState> = useSelector;
