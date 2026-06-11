/**
 * 自動生成ファイル — 手編集禁止。
 *
 * backend の FastAPI OpenAPI スキーマから openapi-typescript で生成される。
 * 再生成: `make codegen-types`（ADR-0007 参照）。
 * backend の Pydantic schema が DTO の Single Source of Truth であり、
 * このファイルはその機械的ミラー。直接編集しても次回生成で上書きされる。
 */
export interface paths {
    "/api/agent/chat": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Agent Chat
         * @description 選択スコープの内容とプロンプトをもとに、職務経歴書への差分 operations を返す。
         *
         *     レスポンスはフロントの state にのみ適用され、DB は更新しない。
         *     ユーザーが確認して「適用」した時点で既存の保存 API が呼ばれる。
         */
        post: operations["agent_chat_api_agent_chat_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/blog/accounts": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * List Accounts
         * @description 連携アカウント一覧を取得する。
         */
        get: operations["list_accounts_api_blog_accounts_get"];
        put?: never;
        /**
         * Add Account
         * @description 連携アカウントを登録する。
         *     同じプラットフォームは1つまで。ユーザー存在チェックあり。
         */
        post: operations["add_account_api_blog_accounts_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/blog/accounts/{account_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        post?: never;
        /**
         * Delete Account
         * @description 連携アカウントを解除する。紐づく記事も削除される。
         */
        delete: operations["delete_account_api_blog_accounts__account_id__delete"];
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/blog/accounts/{account_id}/sync": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Sync Account
         * @description 外部 API からデータを取得して DB に保存する。
         */
        post: operations["sync_account_api_blog_accounts__account_id__sync_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/blog/accounts/{platform}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        /**
         * Update Account
         * @description 連携アカウントの username を更新し、同期状態を未同期に戻す。
         */
        patch: operations["update_account_api_blog_accounts__platform__patch"];
        trace?: never;
    };
    "/api/blog/articles": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * List Articles
         * @description DB に保存済みの記事一覧を取得する。
         */
        get: operations["list_articles_api_blog_articles_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/blog/score": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Get Blog Score
         * @description 保存済みの記事に対してスコアリングを実行する。
         */
        get: operations["get_blog_score_api_blog_score_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/github-link/cache": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Get Cache
         * @description 保存済みの連携結果を取得する。
         */
        get: operations["get_cache_api_github_link_cache_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/github-link/cache/status": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Get Cache Status
         * @description 連携ステータスを返す（軽量ポーリング用）。
         */
        get: operations["get_cache_status_api_github_link_cache_status_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/github-link/progress": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Get Link Progress
         * @description GitHub 連携タスクの進捗を取得する（ポーリング用）。
         *
         *     Redis にデータがない場合（タスク未開始・Redis 障害）は step_index=0 のデフォルトを返す。
         */
        get: operations["get_link_progress_api_github_link_progress_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/github-link/run": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Start Github Link
         * @description GitHub 連携パイプラインをバックグラウンドで開始する。
         */
        post: operations["start_github_link_api_github_link_run_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/github-link/run/retry": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Retry Github Link
         * @description 失敗した GitHub 連携タスクを手動で再実行する。
         *
         *     ``dead_letter`` 状態のキャッシュのみ再実行可能。
         *     ``retry_count`` を 0 にリセットし、ステータスを ``pending`` に戻して再ディスパッチする。
         */
        post: operations["retry_github_link_api_github_link_run_retry_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/master-data/qualification": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Items */
        get: operations["list_items_api_master_data_qualification_get"];
        put?: never;
        /** Create Item */
        post: operations["create_item_api_master_data_qualification_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/master-data/qualification/{item_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        /** Update Item */
        put: operations["update_item_api_master_data_qualification__item_id__put"];
        post?: never;
        /** Delete Item */
        delete: operations["delete_item_api_master_data_qualification__item_id__delete"];
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/master-data/technology-stack": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * List Technology Stacks
         * @description 技術スタックマスタ一覧を取得する（認証不要）。
         */
        get: operations["list_technology_stacks_api_master_data_technology_stack_get"];
        put?: never;
        /**
         * Create Technology Stack
         * @description 技術スタックマスタを新規作成する（admin認証必須）。
         */
        post: operations["create_technology_stack_api_master_data_technology_stack_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/master-data/technology-stack/{item_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        /**
         * Update Technology Stack
         * @description 技術スタックマスタを更新する（admin認証必須）。
         */
        put: operations["update_technology_stack_api_master_data_technology_stack__item_id__put"];
        post?: never;
        /**
         * Delete Technology Stack
         * @description 技術スタックマスタを削除する（admin認証必須）。
         */
        delete: operations["delete_technology_stack_api_master_data_technology_stack__item_id__delete"];
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/notifications": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * List Notifications
         * @description 最新30件の通知を取得する。
         */
        get: operations["list_notifications_api_notifications_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/notifications/read-all": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Mark All As Read
         * @description 全通知を既読にする。
         */
        post: operations["mark_all_as_read_api_notifications_read_all_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/notifications/unread-count": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Get Unread Count
         * @description 未読通知件数を返す。
         */
        get: operations["get_unread_count_api_notifications_unread_count_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/notifications/{notification_id}/read": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        /**
         * Mark As Read
         * @description 指定された通知を既読にする。
         */
        patch: operations["mark_as_read_api_notifications__notification_id__read_patch"];
        trace?: never;
    };
    "/api/resumes": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Create Resume */
        post: operations["create_resume_api_resumes_post"];
        /** Delete Resume */
        delete: operations["delete_resume_api_resumes_delete"];
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/resumes/latest": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Latest Resume */
        get: operations["get_latest_resume_api_resumes_latest_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/resumes/preview": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Preview Resume
         * @description 保存せずに、職務経歴書を PDF と同じレイアウトに整形した HTML と画面用 CSS を返す。
         *
         *     左右 diff プレビュー（左=保存済み / 右=編集中）の描画に使う。HTML 内の各値ノードには
         *     form パス（``data-fp``）が付与され、FE が変更箇所のハイライト・スクロール先特定に使う。
         *     DB は更新しない。WeasyPrint を通さず HTML 文字列生成のみのため軽量。
         */
        post: operations["preview_resume_api_resumes_preview_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/resumes/{resume_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Resume */
        get: operations["get_resume_api_resumes__resume_id__get"];
        /** Update Resume */
        put: operations["update_resume_api_resumes__resume_id__put"];
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/resumes/{resume_id}/markdown": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Download Resume Markdown */
        get: operations["download_resume_markdown_api_resumes__resume_id__markdown_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/resumes/{resume_id}/pdf": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Download Resume Pdf */
        get: operations["download_resume_pdf_api_resumes__resume_id__pdf_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/auth/github/callback": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Github Callback Redirect
         * @description GitHub OAuth コールバックを処理し、フロントエンドへリダイレクトする。
         *
         *     一部の CDN / リバースプロキシは 303 レスポンスの Set-Cookie を除去することがあるため、
         *     200 + HTML リダイレクトで Cookie を確実にセットする。
         *
         *     state は認可開始時に発行した HttpOnly Cookie とサーバー側で照合する（CSRF 対策）。
         *     照合失敗時はトークン交換に進まず、エラー付きでフロントへリダイレクトする。
         */
        get: operations["github_callback_redirect_auth_github_callback_get"];
        put?: never;
        /**
         * Github Callback
         * @description GitHub OAuth コードを受け取り、認証 Cookie を発行する。
         *
         *     state は認可開始時に発行した HttpOnly Cookie とサーバー側で照合する（CSRF 対策）。
         *     フロントの sessionStorage 照合に依存せず API 直叩きのログイン CSRF を防ぐ。
         *     redirect_uri は GitHub OAuth App の登録値 (`/github/callback`) と一致させる必要がある。
         */
        post: operations["github_callback_auth_github_callback_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/auth/github/login": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Github Login
         * @description GitHub OAuth 認可 URL へリダイレクトする。
         */
        get: operations["github_login_auth_github_login_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/auth/github/login-url": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Github Login Url
         * @description GitHub OAuth 認可 URL と state を返す。
         *
         *     state は HttpOnly Cookie に保存し、コールバックでサーバー側照合する（CSRF 対策の正本）。
         *     レスポンスの state はフロントの sessionStorage 照合（多層防御）にも併用する。
         */
        get: operations["github_login_url_auth_github_login_url_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/auth/logout": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Logout
         * @description ログアウト処理。DB の refresh_jti を無効化し Cookie を削除する。
         *     トークン解析が失敗した場合でも必ず Cookie を削除して 204 を返す。
         */
        post: operations["logout_auth_logout_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/auth/me": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Me
         * @description 現在のログインユーザー情報を返す。
         */
        get: operations["me_auth_me_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/auth/refresh": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Refresh
         * @description リフレッシュトークンで新しいアクセストークンを発行する。
         */
        post: operations["refresh_auth_refresh_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/health": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Healthcheck
         * @description ヘルスチェック。Uptime Check から呼ばれる。DB 接続も検証する。
         */
        get: operations["healthcheck_health_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/internal/tasks/{task_type}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Handle Task
         * @description Cloud Tasks コールバックまたはローカルテスト用エンドポイント。
         */
        post: operations["handle_task_internal_tasks__task_type__post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
}
export type webhooks = Record<string, never>;
export interface components {
    schemas: {
        /**
         * AgentChatRequest
         * @description Agent チャットのリクエスト。スコープ選択は必須。
         */
        AgentChatRequest: {
            /** History */
            history?: components["schemas"]["AgentHistoryEntry"][];
            /** Prompt */
            prompt: string;
            resume: components["schemas"]["AgentResumeContext"];
            /**
             * Scope
             * @enum {string}
             */
            scope: "project" | "career_summary" | "self_pr";
            target?: components["schemas"]["ProjectTarget"] | null;
        };
        /**
         * AgentChatResponse
         * @description Agent チャットのレスポンス（AI の説明文 + 差分 operations）。
         */
        AgentChatResponse: {
            /** Message */
            message: string;
            /** Operations */
            operations?: components["schemas"]["AgentOperation"][];
        };
        /**
         * AgentClientContext
         * @description LLM コンテキスト用の取引先情報。
         */
        AgentClientContext: {
            /**
             * Name
             * @default
             */
            name: string;
            /** Projects */
            projects?: components["schemas"]["AgentProjectContext"][];
        };
        /**
         * AgentExperienceContext
         * @description LLM コンテキスト用の在籍企業情報。
         */
        AgentExperienceContext: {
            /**
             * Business Description
             * @default
             */
            business_description: string;
            /** Clients */
            clients?: components["schemas"]["AgentClientContext"][];
            /**
             * Company
             * @default
             */
            company: string;
        };
        /**
         * AgentHistoryEntry
         * @description マルチターン用の会話履歴 1 件。
         *
         *     user はユーザーの依頼文のみ（レジュメコンテキストは含めない。コンテキストは
         *     最新ターンの prompt にのみ載せ、毎ターンの重複でトークンが膨れるのを防ぐ）。
         *     assistant は前回 LLM が返した JSON 文字列をそのまま入れる（出力形式の実例として
         *     few-shot 的に働き、小型モデルのフォーマット逸脱を抑える狙い）。
         */
        AgentHistoryEntry: {
            /**
             * Role
             * @enum {string}
             */
            role: "user" | "assistant";
            /** Text */
            text: string;
        };
        /**
         * AgentOperation
         * @description resume state へ適用する差分（テキストフィールドの置換）。
         *
         *     フロントは選択済みスコープ（と target）に対応するフィールドへ value を反映する。
         *     DB は更新せず、ユーザーが「適用」した時点で既存の保存 API を呼ぶ。
         *
         *     ``field`` は意図的に Literal ではなく str で受ける。小型 LLM が許可外の
         *     field 名を返すことがあり、Literal だと operation 1 件の逸脱でレスポンス全体が
         *     ValidationError になる。許可 field の検証・破棄は chat_service._parse_response が担う。
         */
        AgentOperation: {
            /** Field */
            field: string;
            /** Value */
            value: string;
        };
        /**
         * AgentProjectContext
         * @description LLM コンテキスト用のプロジェクト情報。
         */
        AgentProjectContext: {
            /**
             * Description
             * @default
             */
            description: string;
            /**
             * Name
             * @default
             */
            name: string;
            /** Phases */
            phases?: string[];
            /**
             * Role
             * @default
             */
            role: string;
            /** Technology Stacks */
            technology_stacks?: components["schemas"]["AgentTechnologyStack"][];
        };
        /**
         * AgentResumeContext
         * @description LLM に渡す編集中の職務経歴書コンテキスト。
         *
         *     保存契約（必須項目・日付検証）は適用しない。DB は参照せず、
         *     フロントが編集中のフォーム内容をそのまま送る設計（DB を更新しない原則）。
         */
        AgentResumeContext: {
            /**
             * Career Summary
             * @default
             */
            career_summary: string;
            /** Experiences */
            experiences?: components["schemas"]["AgentExperienceContext"][];
            /**
             * Self Pr
             * @default
             */
            self_pr: string;
        };
        /**
         * AgentTechnologyStack
         * @description LLM コンテキスト用の技術スタック（保存契約より緩い）。
         */
        AgentTechnologyStack: {
            /**
             * Category
             * @default
             */
            category: string;
            /**
             * Name
             * @default
             */
            name: string;
        };
        /**
         * BlogAccountCreate
         * @description ブログ連携アカウントの作成リクエスト。
         */
        BlogAccountCreate: {
            /**
             * Platform
             * @enum {string}
             */
            platform: "zenn" | "note" | "qiita";
            /** Username */
            username: string;
        };
        /**
         * BlogAccountResponse
         * @description ブログ連携アカウントのレスポンス。
         */
        BlogAccountResponse: {
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Last Synced At */
            last_synced_at?: string | null;
            /** Platform */
            platform: string;
            /** Username */
            username: string;
        };
        /**
         * BlogAccountUpdate
         * @description ブログ連携アカウントの更新リクエスト。
         */
        BlogAccountUpdate: {
            /** Username */
            username: string;
        };
        /**
         * BlogArticleResponse
         * @description ブログ記事のレスポンス。
         */
        BlogArticleResponse: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /**
             * Likes Count
             * @default 0
             */
            likes_count: number;
            /** Platform */
            platform: string;
            /** Published At */
            published_at?: string | null;
            /** Summary */
            summary?: string | null;
            /** Tags */
            tags?: string[];
            /** Title */
            title: string;
            /** Url */
            url: string;
        };
        /**
         * BlogScoreArticleResponse
         * @description 技術記事判定結果付きの記事情報。
         */
        BlogScoreArticleResponse: {
            /** Id */
            id: string;
            /**
             * Is Tech
             * @default false
             */
            is_tech: boolean;
            /**
             * Likes Count
             * @default 0
             */
            likes_count: number;
            /** Published At */
            published_at?: string | null;
            /** Tags */
            tags?: string[];
            /** Title */
            title: string;
            /** Url */
            url: string;
        };
        /**
         * BlogScoreResponse
         * @description ブログ統計サマリのレスポンス。
         */
        BlogScoreResponse: {
            /** Articles */
            articles?: components["schemas"]["BlogScoreArticleResponse"][];
            /**
             * Avg Likes
             * @default 0
             */
            avg_likes: number;
            /**
             * Avg Monthly Posts
             * @default 0
             */
            avg_monthly_posts: number;
            /**
             * Tech Article Count
             * @default 0
             */
            tech_article_count: number;
            /**
             * Total Article Count
             * @default 0
             */
            total_article_count: number;
        };
        /**
         * BlogSyncResponse
         * @description ブログ同期結果のレスポンス。
         */
        BlogSyncResponse: {
            /** Synced Count */
            synced_count: number;
            /** Total Count */
            total_count: number;
        };
        /**
         * CachedGitHubLinkResponse
         * @description DB に保存された連携結果を返す。
         */
        CachedGitHubLinkResponse: {
            /** Error Code */
            error_code?: string | null;
            /** Error Message */
            error_message?: string | null;
            result?: components["schemas"]["GitHubLinkResponse"] | null;
            /** Status */
            status?: string | null;
            /** Warning Message */
            warning_message?: string | null;
        };
        /**
         * Client
         * @description ユーザ（常駐先/クライアント企業）。
         *
         *     ``is_vacation=True`` の場合は取引先ではなく在籍中の休暇（育児/介護/留学等）を表し、
         *     name / projects の代わりに ``vacation_*`` 期間と詳細を保持する。
         */
        "Client-Input": {
            /**
             * Has Client
             * @default true
             */
            has_client: boolean;
            /**
             * Is Vacation
             * @default false
             */
            is_vacation: boolean;
            /**
             * Name
             * @default
             */
            name: string;
            /** Projects */
            projects?: components["schemas"]["Project-Input"][];
            /**
             * Vacation Description
             * @default
             */
            vacation_description: string;
            /**
             * Vacation End Date
             * @default
             */
            vacation_end_date: string;
            /**
             * Vacation Is Current
             * @default false
             */
            vacation_is_current: boolean;
            /**
             * Vacation Start Date
             * @default
             */
            vacation_start_date: string;
        };
        /**
         * Client
         * @description ユーザ（常駐先/クライアント企業）。
         *
         *     ``is_vacation=True`` の場合は取引先ではなく在籍中の休暇（育児/介護/留学等）を表し、
         *     name / projects の代わりに ``vacation_*`` 期間と詳細を保持する。
         */
        "Client-Output": {
            /**
             * Has Client
             * @default true
             */
            has_client: boolean;
            /**
             * Is Vacation
             * @default false
             */
            is_vacation: boolean;
            /**
             * Name
             * @default
             */
            name: string;
            /** Projects */
            projects?: components["schemas"]["Project-Output"][];
            /**
             * Vacation Description
             * @default
             */
            vacation_description: string;
            /**
             * Vacation End Date
             * @default
             */
            vacation_end_date: string;
            /**
             * Vacation Is Current
             * @default false
             */
            vacation_is_current: boolean;
            /**
             * Vacation Start Date
             * @default
             */
            vacation_start_date: string;
        };
        /**
         * ContributionCalendar
         * @description 1年分のコントリビューションカレンダー（GitHub の緑の四角）。
         */
        ContributionCalendar: {
            /**
             * Total Contributions
             * @description 期間内のコントリビューション総数
             */
            total_contributions: number;
            /**
             * Weeks
             * @description 週ごとの日配列（列=週、各週は最大7日）
             */
            weeks?: components["schemas"]["ContributionDay"][][];
            /**
             * Year
             * @description このカレンダーが対象とする西暦年
             */
            year: number;
        };
        /**
         * ContributionDay
         * @description コントリビューションカレンダーの 1 日分。
         */
        ContributionDay: {
            /**
             * Count
             * @description その日のコントリビューション数
             */
            count: number;
            /**
             * Date
             * @description ISO 8601 形式の日付 (YYYY-MM-DD)
             */
            date: string;
            /**
             * Level
             * @description GitHub の濃淡レベル (0–4)
             */
            level: number;
        };
        /** Experience */
        "Experience-Input": {
            /** Business Description */
            business_description: string;
            /**
             * Capital
             * @default
             */
            capital: string;
            /**
             * Capital Unit
             * @default 千万円
             * @enum {string}
             */
            capital_unit: "万円" | "百万円" | "千万円" | "億円";
            /** Clients */
            clients?: components["schemas"]["Client-Input"][];
            /** Company */
            company: string;
            /**
             * Description
             * @default
             */
            description: string;
            /**
             * Employee Count
             * @default
             */
            employee_count: string;
            /**
             * End Date
             * @default
             */
            end_date: string;
            /**
             * Is Current
             * @default false
             */
            is_current: boolean;
            /**
             * Is It Company
             * @default true
             */
            is_it_company: boolean;
            /**
             * Start Date
             * @default
             */
            start_date: string;
        };
        /** Experience */
        "Experience-Output": {
            /** Business Description */
            business_description: string;
            /**
             * Capital
             * @default
             */
            capital: string;
            /**
             * Capital Unit
             * @default 千万円
             * @enum {string}
             */
            capital_unit: "万円" | "百万円" | "千万円" | "億円";
            /** Clients */
            clients?: components["schemas"]["Client-Output"][];
            /** Company */
            company: string;
            /**
             * Description
             * @default
             */
            description: string;
            /**
             * Employee Count
             * @default
             */
            employee_count: string;
            /**
             * End Date
             * @default
             */
            end_date: string;
            /**
             * Is Current
             * @default false
             */
            is_current: boolean;
            /**
             * Is It Company
             * @default true
             */
            is_it_company: boolean;
            /**
             * Start Date
             * @default
             */
            start_date: string;
        };
        /** GitHubCallbackRequest */
        GitHubCallbackRequest: {
            /** Code */
            code: string;
            /** State */
            state: string;
        };
        /** GitHubLinkRequest */
        GitHubLinkRequest: {
            /**
             * Include Forks
             * @description 連携にフォークしたリポジトリを含めるかどうか
             * @default false
             */
            include_forks: boolean;
        };
        /** GitHubLinkResponse */
        GitHubLinkResponse: {
            /** Analyzed At */
            analyzed_at: string;
            /**
             * Contribution Calendars
             * @description 年ごとのコントリビューションカレンダー（新しい年順。取得失敗時は空配列）
             */
            contribution_calendars?: components["schemas"]["ContributionCalendar"][];
            /**
             * Languages
             * @description 言語ごとのバイト数（GitHub linguist ベース）
             */
            languages?: {
                [key: string]: number;
            };
            /** Repos Analyzed */
            repos_analyzed: number;
            /** Unique Skills */
            unique_skills: number;
            /** Username */
            username: string;
        };
        /**
         * GitHubLoginUrlResponse
         * @description GitHub OAuth 認可 URL と CSRF 検証用 state を返すレスポンス。
         *
         *     state はサーバー側で HttpOnly Cookie に保存され、コールバックで照合される（正本）。
         *     レスポンスの state はフロントの sessionStorage 照合（多層防御）にも併用する。
         */
        GitHubLoginUrlResponse: {
            /** Authorization Url */
            authorization_url: string;
            /** State */
            state: string;
        };
        /** HTTPValidationError */
        HTTPValidationError: {
            /** Detail */
            detail?: components["schemas"]["ValidationError"][];
        };
        /**
         * MarkAllReadResponse
         * @description 全件既読レスポンス。
         */
        MarkAllReadResponse: {
            /** Updated */
            updated: number;
        };
        /**
         * MasterItem
         * @description マスタデータ共通レスポンス（資格など）。
         */
        MasterItem: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Name */
            name: string;
            /** Sort Order */
            sort_order: number;
        };
        /**
         * MasterItemCreate
         * @description マスタデータ共通の作成リクエスト（資格など）。
         */
        MasterItemCreate: {
            /** Name */
            name: string;
            /**
             * Sort Order
             * @default 0
             */
            sort_order: number;
        };
        /**
         * MasterItemUpdate
         * @description マスタデータ共通の更新リクエスト（資格など）。
         */
        MasterItemUpdate: {
            /** Name */
            name: string;
            /**
             * Sort Order
             * @default 0
             */
            sort_order: number;
        };
        /**
         * NotificationResponse
         * @description 通知レスポンス。
         */
        NotificationResponse: {
            /** Created At */
            created_at: string;
            /** Id */
            id: string;
            /** Is Read */
            is_read: boolean;
            /** Message */
            message: string | null;
            /** Status */
            status: string;
            /** Task Type */
            task_type: string;
            /** Title */
            title: string;
        };
        /**
         * ProgressResponse
         * @description 非同期タスクの進捗情報。
         *
         *     GitHub 連携 / resume_import など、複数ステップを持つタスクで共通利用される。
         */
        ProgressResponse: {
            /**
             * Step Index
             * @description 現在のステップ番号（0 は未開始）
             * @default 0
             */
            step_index: number;
            /**
             * Step Label
             * @description 現在のステップラベル
             */
            step_label?: string | null;
            /** @description ステップ内の細粒度進捗（任意） */
            sub_progress?: components["schemas"]["SubProgress"] | null;
            /** Task Id */
            task_id: string;
            /**
             * Total Steps
             * @description 全ステップ数
             * @default 5
             */
            total_steps: number;
        };
        /** Project */
        "Project-Input": {
            /**
             * Description
             * @default
             */
            description: string;
            /**
             * Name
             * @default
             */
            name: string;
            /** Periods */
            periods?: components["schemas"]["ProjectPeriod"][];
            /** Phases */
            phases?: string[];
            /**
             * Role
             * @default
             */
            role: string;
            team?: components["schemas"]["ProjectTeam"];
            /** Technology Stacks */
            technology_stacks?: components["schemas"]["TechnologyStackItem"][];
        };
        /** Project */
        "Project-Output": {
            /**
             * Description
             * @default
             */
            description: string;
            /**
             * Name
             * @default
             */
            name: string;
            /** Periods */
            periods?: components["schemas"]["ProjectPeriod"][];
            /** Phases */
            phases?: string[];
            /**
             * Role
             * @default
             */
            role: string;
            team?: components["schemas"]["ProjectTeam"];
            /** Technology Stacks */
            technology_stacks?: components["schemas"]["TechnologyStackItem"][];
        };
        /**
         * ProjectPeriod
         * @description プロジェクトの在籍期間（1 案件に複数持てる）。
         */
        ProjectPeriod: {
            /**
             * End Date
             * @default
             */
            end_date: string;
            /**
             * Is Current
             * @default false
             */
            is_current: boolean;
            /**
             * Start Date
             * @default
             */
            start_date: string;
        };
        /**
         * ProjectTarget
         * @description scope=project のとき対象プロジェクトを特定するインデックス。
         */
        ProjectTarget: {
            /** Client Index */
            client_index: number;
            /** Experience Index */
            experience_index: number;
            /** Project Index */
            project_index: number;
        };
        /**
         * ProjectTeam
         * @description プロジェクト体制（全体人数 + 役割別内訳）。
         */
        ProjectTeam: {
            /** Members */
            members?: components["schemas"]["TeamMember"][];
            /**
             * Total
             * @default
             */
            total: string;
        };
        /** ResumeCreate */
        ResumeCreate: {
            /** Career Summary */
            career_summary: string;
            /** Email */
            email: string;
            /** Experiences */
            experiences?: components["schemas"]["Experience-Input"][];
            /** Full Name */
            full_name: string;
            /**
             * Github Url
             * @default
             */
            github_url: string;
            /** Qualifications */
            qualifications?: components["schemas"]["ResumeQualificationItem"][];
            /** Self Pr */
            self_pr: string;
        };
        /**
         * ResumePreviewResponse
         * @description 保存前プレビュー（左右 diff 表示）用の整形済み HTML と画面用 CSS。
         *
         *     DB を更新せず、編集中 payload を PDF と同じレイアウトに整形した HTML を返す。
         *     HTML 内の各値ノードには form パス（``data-fp``）が付与され、FE が変更箇所の
         *     ハイライト・スクロール先特定に使う。
         */
        ResumePreviewResponse: {
            /** Css */
            css: string;
            /** Html */
            html: string;
        };
        /** ResumeQualificationItem */
        ResumeQualificationItem: {
            /** Acquired Date */
            acquired_date: string;
            /** Name */
            name: string;
        };
        /** ResumeResponse */
        ResumeResponse: {
            /** Career Summary */
            career_summary: string;
            /** Created At */
            created_at: string;
            /** Email */
            email: string;
            /** Experiences */
            experiences?: components["schemas"]["Experience-Output"][];
            /** Full Name */
            full_name: string;
            /**
             * Github Url
             * @default
             */
            github_url: string;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Qualifications */
            qualifications?: components["schemas"]["ResumeQualificationItem"][];
            /** Self Pr */
            self_pr: string;
            /** Updated At */
            updated_at: string;
        };
        /** ResumeUpdate */
        ResumeUpdate: {
            /** Career Summary */
            career_summary: string;
            /** Email */
            email: string;
            /** Experiences */
            experiences?: components["schemas"]["Experience-Input"][];
            /** Full Name */
            full_name: string;
            /**
             * Github Url
             * @default
             */
            github_url: string;
            /** Qualifications */
            qualifications?: components["schemas"]["ResumeQualificationItem"][];
            /** Self Pr */
            self_pr: string;
        };
        /**
         * SubProgress
         * @description ステップ内の細粒度な進捗（例: リポジトリ詳細取得ステップ）。
         */
        SubProgress: {
            /** Done */
            done: number;
            /** Total */
            total: number;
        };
        /**
         * TaskAcceptedResponse
         * @description 非同期タスクの受付応答（202 Accepted）。
         *
         *     ``POST /github/run`` / ``POST /github/run/retry`` など、
         *     バックグラウンドタスクを開始するエンドポイントで共通利用される受付レスポンス。
         *     現在のタスクステータス（``pending`` 等）のみを返す。
         */
        TaskAcceptedResponse: {
            /** Status */
            status: string;
        };
        /**
         * TaskStatusResponse
         * @description 非同期タスクのステータスを返す軽量レスポンス。
         *
         *     blog / intelligence など複数の router で共通利用される。
         */
        TaskStatusResponse: {
            /** Error Code */
            error_code?: string | null;
            /** Error Message */
            error_message?: string | null;
            /** Status */
            status: string;
        };
        /**
         * TeamMember
         * @description 体制の役割ごとの人数。
         */
        TeamMember: {
            /** Count */
            count: number;
            /** Role */
            role: string;
        };
        /**
         * TechStackMasterCreate
         * @description 技術スタックマスタの作成リクエスト。
         */
        TechStackMasterCreate: {
            /** Category */
            category: string;
            /** Name */
            name: string;
            /**
             * Sort Order
             * @default 0
             */
            sort_order: number;
        };
        /**
         * TechStackMasterItem
         * @description 技術スタックマスタのレスポンス。
         */
        TechStackMasterItem: {
            /** Category */
            category: string;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Name */
            name: string;
            /** Sort Order */
            sort_order: number;
        };
        /**
         * TechStackMasterUpdate
         * @description 技術スタックマスタの更新リクエスト。
         */
        TechStackMasterUpdate: {
            /** Category */
            category: string;
            /** Name */
            name: string;
            /**
             * Sort Order
             * @default 0
             */
            sort_order: number;
        };
        /** TechnologyStackItem */
        TechnologyStackItem: {
            /**
             * Category
             * @enum {string}
             */
            category: "language" | "framework" | "os" | "db" | "cloud_provider" | "container" | "iac" | "vcs" | "ci_cd" | "project_tool" | "monitoring" | "middleware" | "ai_agent";
            /** Name */
            name: string;
        };
        /** TokenResponse */
        TokenResponse: {
            /**
             * Is Github User
             * @default false
             */
            is_github_user: boolean;
            /** Username */
            username: string;
        };
        /**
         * UnreadCountResponse
         * @description 未読件数レスポンス。
         */
        UnreadCountResponse: {
            /** Count */
            count: number;
        };
        /** ValidationError */
        ValidationError: {
            /** Context */
            ctx?: Record<string, never>;
            /** Input */
            input?: unknown;
            /** Location */
            loc: (string | number)[];
            /** Message */
            msg: string;
            /** Error Type */
            type: string;
        };
    };
    responses: never;
    parameters: never;
    requestBodies: never;
    headers: never;
    pathItems: never;
}
export type $defs = Record<string, never>;
export interface operations {
    agent_chat_api_agent_chat_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["AgentChatRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AgentChatResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_accounts_api_blog_accounts_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BlogAccountResponse"][];
                };
            };
        };
    };
    add_account_api_blog_accounts_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["BlogAccountCreate"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BlogAccountResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    delete_account_api_blog_accounts__account_id__delete: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                account_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    sync_account_api_blog_accounts__account_id__sync_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                account_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BlogSyncResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    update_account_api_blog_accounts__platform__patch: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                platform: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["BlogAccountUpdate"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BlogAccountResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_articles_api_blog_articles_get: {
        parameters: {
            query?: {
                platform?: string | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BlogArticleResponse"][];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_blog_score_api_blog_score_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BlogScoreResponse"];
                };
            };
        };
    };
    get_cache_api_github_link_cache_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CachedGitHubLinkResponse"];
                };
            };
        };
    };
    get_cache_status_api_github_link_cache_status_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["TaskStatusResponse"];
                };
            };
        };
    };
    get_link_progress_api_github_link_progress_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ProgressResponse"];
                };
            };
        };
    };
    start_github_link_api_github_link_run_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["GitHubLinkRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            202: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["TaskAcceptedResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    retry_github_link_api_github_link_run_retry_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: {
            content: {
                "application/json": components["schemas"]["GitHubLinkRequest"] | null;
            };
        };
        responses: {
            /** @description Successful Response */
            202: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["TaskAcceptedResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_items_api_master_data_qualification_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["MasterItem"][];
                };
            };
        };
    };
    create_item_api_master_data_qualification_post: {
        parameters: {
            query?: never;
            header?: {
                authorization?: string | null;
            };
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["MasterItemCreate"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["MasterItem"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    update_item_api_master_data_qualification__item_id__put: {
        parameters: {
            query?: never;
            header?: {
                authorization?: string | null;
            };
            path: {
                item_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["MasterItemUpdate"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["MasterItem"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    delete_item_api_master_data_qualification__item_id__delete: {
        parameters: {
            query?: never;
            header?: {
                authorization?: string | null;
            };
            path: {
                item_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_technology_stacks_api_master_data_technology_stack_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["TechStackMasterItem"][];
                };
            };
        };
    };
    create_technology_stack_api_master_data_technology_stack_post: {
        parameters: {
            query?: never;
            header?: {
                authorization?: string | null;
            };
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["TechStackMasterCreate"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["TechStackMasterItem"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    update_technology_stack_api_master_data_technology_stack__item_id__put: {
        parameters: {
            query?: never;
            header?: {
                authorization?: string | null;
            };
            path: {
                item_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["TechStackMasterUpdate"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["TechStackMasterItem"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    delete_technology_stack_api_master_data_technology_stack__item_id__delete: {
        parameters: {
            query?: never;
            header?: {
                authorization?: string | null;
            };
            path: {
                item_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_notifications_api_notifications_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["NotificationResponse"][];
                };
            };
        };
    };
    mark_all_as_read_api_notifications_read_all_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["MarkAllReadResponse"];
                };
            };
        };
    };
    get_unread_count_api_notifications_unread_count_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["UnreadCountResponse"];
                };
            };
        };
    };
    mark_as_read_api_notifications__notification_id__read_patch: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                notification_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["NotificationResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    create_resume_api_resumes_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ResumeCreate"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ResumeResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    delete_resume_api_resumes_delete: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": Record<string, never>;
                };
            };
        };
    };
    get_latest_resume_api_resumes_latest_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ResumeResponse"];
                };
            };
        };
    };
    preview_resume_api_resumes_preview_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ResumeCreate"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ResumePreviewResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_resume_api_resumes__resume_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                resume_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ResumeResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    update_resume_api_resumes__resume_id__put: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                resume_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ResumeUpdate"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ResumeResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    download_resume_markdown_api_resumes__resume_id__markdown_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                resume_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    download_resume_pdf_api_resumes__resume_id__pdf_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                resume_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    github_callback_redirect_auth_github_callback_get: {
        parameters: {
            query?: {
                code?: string | null;
                state?: string | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    github_callback_auth_github_callback_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["GitHubCallbackRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["TokenResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    github_login_auth_github_login_get: {
        parameters: {
            query?: {
                return_to?: string | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    github_login_url_auth_github_login_url_get: {
        parameters: {
            query?: {
                return_to?: string | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["GitHubLoginUrlResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    logout_auth_logout_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
        };
    };
    me_auth_me_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["TokenResponse"];
                };
            };
        };
    };
    refresh_auth_refresh_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["TokenResponse"];
                };
            };
        };
    };
    healthcheck_health_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: string;
                    };
                };
            };
        };
    };
    handle_task_internal_tasks__task_type__post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                task_type: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
}
