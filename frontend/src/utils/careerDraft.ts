import type { CareerFormState } from "../payloadBuilders";

/**
 * 未ログインで入力した職務経歴書ドラフトを OAuth 往復の間だけ退避するユーティリティ。
 *
 * ## なぜ sessionStorage か
 * GitHub OAuth は `window.location.assign` で全画面遷移するため、入力中フォームを保持する
 * Redux `formCache` は redux-persist の blacklist（PII 保護）対象で復元されない。
 * sessionStorage は OAuth 往復（同一タブ内の全画面ロード）を生き残ることが既存の CSRF state
 * 管理（GitHubCallbackPage）で実証済みのため、これに合わせてドラフトを橋渡しする。
 *
 * ## ライフサイクル
 * - 保存ボタン押下時（未ログイン）に `saveCareerDraft` で退避し、ログイン促進モーダルを開く。
 * - ログイン完了後に `loadCareerDraft` で読み出し、フォームへ復元したら `clearCareerDraft` で消す。
 * - タブを閉じれば自然に消える（PII をディスクへ残さない）。
 */
const CAREER_DRAFT_KEY = "career_draft";

/** ドラフトを sessionStorage へ退避する。直列化に失敗しても致命ではないのでログのみ。 */
export function saveCareerDraft(form: CareerFormState): void {
  try {
    sessionStorage.setItem(CAREER_DRAFT_KEY, JSON.stringify(form));
  } catch (error) {
    console.warn("職務経歴書ドラフトの退避に失敗しました", error);
  }
}

/** 退避済みドラフトを読み出す。存在しない / 壊れている場合は null。 */
export function loadCareerDraft(): CareerFormState | null {
  const raw = sessionStorage.getItem(CAREER_DRAFT_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as CareerFormState;
  } catch (error) {
    console.warn("職務経歴書ドラフトの読み出しに失敗しました", error);
    clearCareerDraft();
    return null;
  }
}

/** 退避済みドラフトを破棄する。 */
export function clearCareerDraft(): void {
  sessionStorage.removeItem(CAREER_DRAFT_KEY);
}
