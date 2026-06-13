/**
 * OpenAPI 生成型（`generated.ts`）を backend のクラス名のまま 1:1 で再エクスポートする薄い層。
 *
 * 呼び出し側は `components["schemas"][...]` を直書きせず、ここで定義した再エクスポート名を import する。
 * これは FE 独自名ではなく生成物の機械的ミラーであり、二重管理にはならない（ADR-0007）。
 * backend の Pydantic schema が DTO の Single Source of Truth。型を増やす場合はここに 1 行追加する。
 */
import type { components } from "./generated";

type Schemas = components["schemas"];

// ── 非同期タスク（shared.py）──────────────────────────────────────────────

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

// ── GitHub 連携（github_link.py）─────────────────────────────────────────

/** コントリビューションカレンダーの 1 日分。backend `schemas/github_link.py:ContributionDay`。 */
export type ContributionDay = Schemas["ContributionDay"];

/** 年ごとのコントリビューションカレンダー。backend `schemas/github_link.py:ContributionCalendar`。 */
export type ContributionCalendar = Schemas["ContributionCalendar"];

/** GitHub 連携の解析結果。backend `schemas/github_link.py:GitHubLinkResponse`。 */
export type GitHubLinkResponse = Schemas["GitHubLinkResponse"];

/** DB に保存された連携結果。backend `schemas/github_link.py:CachedGitHubLinkResponse`。 */
export type CachedGitHubLinkResponse = Schemas["CachedGitHubLinkResponse"];

// ── 認証（auth.py）────────────────────────────────────────────────────────

/** GitHub OAuth 認可 URL と CSRF 検証用 state。backend `schemas/auth.py:GitHubLoginUrlResponse`。 */
export type GitHubLoginUrlResponse = Schemas["GitHubLoginUrlResponse"];

/** 認証トークン応答（ログインユーザー情報）。backend `schemas/auth.py:TokenResponse`。 */
export type TokenResponse = Schemas["TokenResponse"];

// ── 職務経歴書（resume.py）────────────────────────────────────────────────
// 入出力兼用 schema のため openapi-typescript が -Input / -Output に分裂する（ADR-0007 論点A）。
// 両者は構造的に同一（差は nested の参照先のみ）なので、読み取り側の -Output を canonical とする。
// 送信ペイロードは ResumeCreate（== ResumeBase、Experience-Input ベース）を使う。

/** 職務経歴のレスポンス。backend `schemas/resume.py:ResumeResponse`。 */
export type ResumeResponse = Schemas["ResumeResponse"];

/** 職務経歴の作成/更新ペイロード。backend `schemas/resume.py:ResumeCreate`（ResumeBase 同形）。 */
export type ResumeCreate = Schemas["ResumeCreate"];

/** 保存前プレビュー（左右 diff 表示）のレスポンス。backend `schemas/resume.py:ResumePreviewResponse`。 */
export type ResumePreviewResponse = Schemas["ResumePreviewResponse"];

/** 職歴（1 社分）。backend `schemas/resume.py:Experience`。 */
export type Experience = Schemas["Experience-Output"];

/** 取引先/常駐先（休暇エントリ含む）。backend `schemas/resume.py:Client`。 */
export type Client = Schemas["Client-Output"];

/** プロジェクト（案件）。backend `schemas/resume.py:Project`。 */
export type Project = Schemas["Project-Output"];

/** プロジェクト体制。backend `schemas/resume.py:ProjectTeam`。 */
export type ProjectTeam = Schemas["ProjectTeam"];

/** プロジェクト在籍期間。backend `schemas/resume.py:ProjectPeriod`。 */
export type ProjectPeriod = Schemas["ProjectPeriod"];

/** 体制の役割ごとの人数。backend `schemas/resume.py:TeamMember`。 */
export type TeamMember = Schemas["TeamMember"];

/** 技術スタック項目。backend `schemas/resume.py:TechnologyStackItem`。 */
export type TechnologyStackItem = Schemas["TechnologyStackItem"];

/** 技術スタックのカテゴリ（Literal union）。backend `TechnologyStackItem.category` 由来。 */
export type TechnologyStackCategory = Schemas["TechnologyStackItem"]["category"];

/** 資本金の単位（Literal union）。backend `Experience.capital_unit` 由来。 */
export type CapitalUnit = Schemas["Experience-Output"]["capital_unit"];

/** 資格項目。backend `schemas/resume.py:ResumeQualificationItem`。 */
export type ResumeQualificationItem = Schemas["ResumeQualificationItem"];

// ── マスタデータ（master_data.py）─────────────────────────────────────────

/** マスタ項目（資格など）。backend `schemas/master_data.py:MasterItem`。 */
export type MasterItem = Schemas["MasterItem"];

/** 技術スタックマスタ項目。backend `schemas/master_data.py:TechStackMasterItem`。 */
export type TechStackMasterItem = Schemas["TechStackMasterItem"];

// ── ブログ連携（blog.py）──────────────────────────────────────────────────

/** ブログ連携アカウント。backend `schemas/blog.py:BlogAccountResponse`。 */
export type BlogAccountResponse = Schemas["BlogAccountResponse"];

/** ブログ記事。backend `schemas/blog.py:BlogArticleResponse`。 */
export type BlogArticleResponse = Schemas["BlogArticleResponse"];

// ── 通知（routers/notifications.py）───────────────────────────────────────

/** 通知 1 件。backend `routers/notifications.py:NotificationResponse`。 */
export type NotificationResponse = Schemas["NotificationResponse"];

/** 未読件数レスポンス。backend `routers/notifications.py:UnreadCountResponse`。 */
export type UnreadCountResponse = Schemas["UnreadCountResponse"];

/** 全件既読レスポンス。backend `routers/notifications.py:MarkAllReadResponse`。 */
export type MarkAllReadResponse = Schemas["MarkAllReadResponse"];

// ── Agent（agent.py / ADR-0010）──────────────────────────────────────────

/** Agent チャットのリクエスト。backend `schemas/agent.py:AgentChatRequest`。 */
export type AgentChatRequest = Schemas["AgentChatRequest"];

/** Agent チャットのレスポンス。backend `schemas/agent.py:AgentChatResponse`。 */
export type AgentChatResponse = Schemas["AgentChatResponse"];

/** resume state へ適用する差分。backend `schemas/agent.py:AgentOperation`。 */
export type AgentOperation = Schemas["AgentOperation"];

/** マルチターン用の会話履歴 1 件。backend `schemas/agent.py:AgentHistoryEntry`。 */
export type AgentHistoryEntry = Schemas["AgentHistoryEntry"];

/** Agent に渡す編集中の職務経歴書コンテキスト。backend `schemas/agent.py:AgentResumeContext`。 */
export type AgentResumeContext = Schemas["AgentResumeContext"];

/** project スコープの対象指定。backend `schemas/agent.py:ProjectTarget`。 */
export type ProjectTarget = Schemas["ProjectTarget"];

/** experience スコープの対象指定。backend `schemas/agent.py:ExperienceTarget`。 */
export type ExperienceTarget = Schemas["ExperienceTarget"];

/** 選択可能な LLM モデルのエイリアス。backend `schemas/agent.py:AgentModelAlias`（ADR-0012）。 */
export type AgentModelAlias = NonNullable<AgentChatRequest["model"]>;

// ── 課金（billing.py / ADR-0012）─────────────────────────────────────────

/** クレジット残高。backend `schemas/billing.py:CreditBalanceResponse`。 */
export type CreditBalanceResponse = Schemas["CreditBalanceResponse"];

/** クレジット台帳エントリ。backend `schemas/billing.py:CreditTransactionResponse`。 */
export type CreditTransactionResponse = Schemas["CreditTransactionResponse"];

/** モデル別の使用量サマリ。backend `schemas/billing.py:AgentUsageSummaryEntry`。 */
export type AgentUsageSummaryEntry = Schemas["AgentUsageSummaryEntry"];

/** 購入可能なクレジットパック。backend `schemas/billing.py:CreditPackResponse`。 */
export type CreditPackResponse = Schemas["CreditPackResponse"];
