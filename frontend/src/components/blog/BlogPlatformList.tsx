import type { Dispatch, SetStateAction } from "react";

import type { BlogAccount } from "../../types";
import type { PlatformKey } from "../../hooks/blog/useBlogAccountManager";
import { ZennIcon } from "../icons/ZennIcon";
import { NoteIcon } from "../icons/NoteIcon";
import { QiitaIcon } from "../icons/QiitaIcon";
import styles from "./BlogPage.module.css";

/** 対応プラットフォーム定義 */
const PLATFORMS = [
  {
    key: "zenn" as const,
    label: "Zenn",
    urlPrefix: "https://zenn.dev/",
    icon: <ZennIcon size={22} />,
  },
  {
    key: "note" as const,
    label: "note",
    urlPrefix: "https://note.com/",
    icon: <NoteIcon size={22} />,
  },
  {
    key: "qiita" as const,
    label: "Qiita",
    urlPrefix: "https://qiita.com/",
    icon: <QiitaIcon size={22} />,
  },
] as const;

type BlogPlatformListProps = {
  accountMap: Map<string, BlogAccount>;
  draftUsernames: Record<string, string>;
  setDraftUsernames: Dispatch<SetStateAction<Record<string, string>>>;
  savingPlatform: string | null;
  syncingPlatform: string | null;
  onSave: (platform: PlatformKey) => Promise<void>;
  onSync: (platform: PlatformKey) => Promise<void>;
  onDelete: (platform: PlatformKey) => Promise<void>;
};

/** プラットフォーム連携行の一覧を描画するコンポーネント。 */
export function BlogPlatformList({
  accountMap,
  draftUsernames,
  setDraftUsernames,
  savingPlatform,
  syncingPlatform,
  onSave,
  onSync,
  onDelete,
}: BlogPlatformListProps) {
  return (
    <div className={styles.linkSection}>
      <h2>アウトプット連携</h2>
      <div className={styles.platformList}>
        {PLATFORMS.map((pf) => {
          const linked = accountMap.get(pf.key);
          return (
            <div key={pf.key} className={styles.platformRow}>
              <div className={styles.platformIcon}>{pf.icon}</div>
              <span className={styles.platformLabel}>{pf.label}</span>

              {linked ? (
                <>
                  <span className={styles.urlPrefix}>{pf.urlPrefix}</span>
                  <span className={styles.linkedUsername}>{linked.username}</span>
                  <span className={styles.linkedBadge}>連携済み</span>
                  <button
                    type="button"
                    className={styles.actionButton}
                    disabled={syncingPlatform === pf.key}
                    onClick={() => onSync(pf.key)}
                  >
                    {syncingPlatform === pf.key ? "同期中..." : "同期"}
                  </button>
                  <button
                    type="button"
                    className={styles.unlinkButton}
                    onClick={() => onDelete(pf.key)}
                  >
                    解除
                  </button>
                </>
              ) : (
                <>
                  <span className={styles.urlPrefix}>{pf.urlPrefix}</span>
                  <input
                    type="text"
                    className={styles.usernameInput}
                    placeholder="ユーザー名"
                    value={draftUsernames[pf.key]}
                    onChange={(e) =>
                      setDraftUsernames((prev) => ({ ...prev, [pf.key]: e.target.value }))
                    }
                    onKeyDown={(e) => {
                      if (
                        e.key === "Enter" &&
                        savingPlatform !== pf.key &&
                        draftUsernames[pf.key]?.trim()
                      )
                        onSave(pf.key);
                    }}
                  />
                  <button
                    type="button"
                    className={styles.saveButton}
                    disabled={savingPlatform === pf.key || !draftUsernames[pf.key]?.trim()}
                    onClick={() => onSave(pf.key)}
                  >
                    {savingPlatform === pf.key ? "保存中..." : "保存"}
                  </button>
                </>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
