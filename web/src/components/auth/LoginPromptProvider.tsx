import { useCallback, useState } from "react";
import type { ReactNode } from "react";

import { LoginPromptModal } from "./LoginPromptModal";
import { LoginPromptContext } from "./loginPromptContext";

/**
 * ログイン促進モーダルを 1 つだけ保持し、配下のどこからでも `useLoginPrompt()` で開けるようにする Provider。
 * サイドバー（SidebarLayout）とお試し入力フォーム（CareerResumeForm）の双方が同じモーダルを共有する。
 */
export function LoginPromptProvider({ children }: { children: ReactNode }) {
  const [open, setOpen] = useState(false);
  const requestLogin = useCallback(() => setOpen(true), []);

  return (
    <LoginPromptContext.Provider value={requestLogin}>
      {children}
      {open && <LoginPromptModal onClose={() => setOpen(false)} />}
    </LoginPromptContext.Provider>
  );
}
