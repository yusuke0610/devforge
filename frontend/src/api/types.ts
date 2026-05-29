/**
 * OpenAPI 生成型（`generated.ts`）を backend のクラス名のまま 1:1 で再エクスポートする薄い層。
 *
 * 呼び出し側は `components["schemas"][...]` を直書きせず、ここで定義した再エクスポート名を import する。
 * これは FE 独自名ではなく生成物の機械的ミラーであり、二重管理にはならない（ADR-0007）。
 * backend の Pydantic schema が DTO の Single Source of Truth。型を増やす場合はここに 1 行追加する。
 */
import type { components } from "./generated";

type Schemas = components["schemas"];

/**
 * 非同期タスクのステータスを返す軽量レスポンス。
 * backend `app/schemas/shared.py:TaskStatusResponse` のミラー。
 */
export type TaskStatusResponse = Schemas["TaskStatusResponse"];

/** 非同期タスクの受付応答（202 Accepted）。backend `schemas/shared.py:TaskAcceptedResponse`。 */
export type TaskAcceptedResponse = Schemas["TaskAcceptedResponse"];

/** GitHub 連携タスクの進捗。backend `schemas/shared.py:ProgressResponse`。 */
export type ProgressResponse = Schemas["ProgressResponse"];

/** 進捗の細粒度サブ進捗。backend `schemas/shared.py:SubProgress`。 */
export type SubProgress = Schemas["SubProgress"];

/** コントリビューションカレンダーの 1 日分。backend `schemas/github_link.py:ContributionDay`。 */
export type ContributionDay = Schemas["ContributionDay"];

/** 直近1年のコントリビューションカレンダー。backend `schemas/github_link.py:ContributionCalendar`。 */
export type ContributionCalendar = Schemas["ContributionCalendar"];

/** GitHub 連携の解析結果。backend `schemas/github_link.py:GitHubLinkResponse`。 */
export type GitHubLinkResponse = Schemas["GitHubLinkResponse"];

/** DB に保存された連携結果。backend `schemas/github_link.py:CachedGitHubLinkResponse`。 */
export type CachedGitHubLinkResponse = Schemas["CachedGitHubLinkResponse"];

/** GitHub OAuth 認可 URL と CSRF 検証用 state。backend `schemas/auth.py:GitHubLoginUrlResponse`。 */
export type GitHubLoginUrlResponse = Schemas["GitHubLoginUrlResponse"];

/** 認証トークン応答（ログインユーザー情報）。backend `schemas/auth.py:TokenResponse`。 */
export type TokenResponse = Schemas["TokenResponse"];
