import { setupServer } from "msw/node";
import { handlers } from "./handlers";

/** Vitest 用の MSW サーバーインスタンス */
export const server = setupServer(...handlers);
