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
         *     career_summary / self_pr スコープでは GitHub 分析サマリーを参照情報として付与する。
         *     レスポンスはフロントの state にのみ適用され、DB は更新しない
         *     （クレジット消費・使用ログの記録は除く / ADR-0012）。
         *     ユーザーが確認して「適用」した時点で既存の保存 API が呼ばれる。
         */
        post: operations["agent_chat_api_agent_chat_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/agent/resume-draft/pdf": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Download Resume Draft Pdf
         * @description 完了済みの経歴書ドラフトを PDF で返す（ADR-0018）。
         *
         *     生成タスクが保存した payload から PDF を再レンダリングする（決定論的・DB 非依存）。
         *     生成未完了・結果なしは 409 を返す。
         */
        get: operations["download_resume_draft_pdf_api_agent_resume_draft_pdf_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/agent/resume-draft/run": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Start Resume Draft
         * @description GitHub 連携データからの経歴書ドラフト生成をバックグラウンドで開始する（202 / ADR-0018）。
         *
         *     構造（プロジェクト・技術スタック・期間）は連携データからルールベースで写し、自然文
         *     （職務要約・自己PR・プロジェクト説明）だけを LLM で生成する。生成物（payload）は
         *     ``resume_draft_cache`` に保存され、``GET /resume-draft/pdf`` でダウンロードできる。
         *     確定した職務経歴書（``resumes``）とは別物で、そちらには書き込まない。
         *     課金は生成タスク側で確定する（残高の事前チェックのみ本エンドポイントで行う / ADR-0012）。
         */
        post: operations["start_resume_draft_api_agent_resume_draft_run_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/agent/resume-draft/status": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Get Resume Draft Status
         * @description 経歴書ドラフト生成タスクのステータスを返す（軽量ポーリング用 / ADR-0018）。
         */
        get: operations["get_resume_draft_status_api_agent_resume_draft_status_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/billing/admin/grant": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Admin Grant Credits
         * @description 管理者がユーザーへクレジットを付与する（Phase 1 の残高調整・テスト用）。
         *
         *     ADMIN_TOKEN（Bearer）認証。Stripe 導入後も返金・補填時の残高調整用に残す。
         */
        post: operations["admin_grant_credits_api_billing_admin_grant_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/billing/balance": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Get Credit Balance
         * @description ログインユーザーのクレジット残高を返す。
         */
        get: operations["get_credit_balance_api_billing_balance_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/billing/checkout": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Create Checkout
         * @description クレジット購入の Stripe Checkout セッションを作成し、決済ページ URL を返す（ADR-0012）。
         *
         *     外部 API（Stripe）を呼ぶ高コスト endpoint のため rate limit を付与する。
         *     入金確定は Webhook（checkout.session.completed）が正であり、本エンドポイントは
         *     決済ページへ誘導する URL を返すだけで残高は更新しない。
         */
        post: operations["create_checkout_api_billing_checkout_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/billing/model-rates": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * List Model Rates
         * @description モデル別の標準消費レート（回数目安の算出用 / ADR-0012）を返す。
         *
         *     フロントは残高・パック・モデルカードを「Sonnet 約N回」に換算するのに使う。
         *     利用実績のあるユーザーは usage-summary の実測平均を優先し、本値は新規ユーザーの
         *     フォールバックとして使う。
         */
        get: operations["list_model_rates_api_billing_model_rates_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/billing/packs": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * List Credit Packs
         * @description 購入可能なクレジットパック一覧を返す（トークン購入画面用 / ADR-0012）。
         *
         *     価格・付与クレジットの正本は services/billing/pricing.py。
         */
        get: operations["list_credit_packs_api_billing_packs_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/billing/transactions": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * List Credit Transactions
         * @description クレジット台帳履歴（付与・消費）を新しい順に返す。
         */
        get: operations["list_credit_transactions_api_billing_transactions_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/billing/usage-summary": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Get Usage Summary
         * @description モデル別の使用量サマリ（チャット回数・トークン・消費クレジット）を返す。
         *
         *     モデル選択モーダルで「あなたの利用実績」を表示するために使う。残りチャット回数の
         *     目安は残高と組み合わせてフロントで算出する。
         */
        get: operations["get_usage_summary_api_billing_usage_summary_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/billing/webhook": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Stripe Webhook
         * @description Stripe Webhook（checkout.session.completed）でクレジットを付与する（ADR-0012）。
         *
         *     署名検証必須。入金確定はこのエンドポイントが正で、付与の冪等性は
         *     credit_transactions.stripe_session_id の UNIQUE 制約で担保する。呼び出し元は Stripe の
         *     ため get_current_user は付けない（認証 Cookie は届かない）。Cloudflare を経由せず
         *     Cloud Run へ直接届くため InternalSecretMiddleware の対象外にしてある（main.py 参照）。
         */
        post: operations["stripe_webhook_api_billing_webhook_post"];
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
    "/api/github-link/skills": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Get Skills
         * @description GitHub 連携で推論した 3 層スキル（ADR-0016）を取得する。
         *
         *     表示名の human-in-the-loop 確定（D11）があれば ``confirmed_display_name`` / ``group_id``
         *     として載せる。連携がまだ実行されていない場合は空配列を返す。
         */
        get: operations["get_skills_api_github_link_skills_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/github-link/skills/display-decisions": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        /**
         * Confirm Skill Display Decisions
         * @description レビュー済みの表示名・畳み込みを確定・永続化する（ADR-0016 D11）。
         *
         *     確定対象の identity は当該ユーザーの検出済みスキルに属していなければならない
         *     （他者・非実在 identity の混入を拒否）。確定は独立 Layer 3 テーブルへ upsert され、
         *     連携の洗い替えに耐える。確定後の最新スキル一覧を返す。
         */
        put: operations["confirm_skill_display_decisions_api_github_link_skills_display_decisions_put"];
        post?: never;
        /**
         * Reset Skill Display Decisions
         * @description 確定済みの表示名・畳み込みを解除（リセット）する（ADR-0016 D11 / #496）。
         *
         *     指定 identity の Layer 3 確定行を削除し、機械デフォルト（機械 display_name > canonical）
         *     へ戻す。畳み込みグループの全メンバー identity を渡せば畳み込みも解ける。identity は当該
         *     ユーザーの検出済みスキルに属していなければならない（confirm と同じ authz）。存在しない
         *     確定行の指定は冪等に無視する。リセット後の最新スキル一覧を返す。
         */
        delete: operations["reset_skill_display_decisions_api_github_link_skills_display_decisions_delete"];
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/github-link/skills/display-names/propose": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Propose Skill Display Names Endpoint
         * @description 検出済みスキルの表示名・畳み込みグループを agent に提案させる（ADR-0016 D11）。
         *
         *     agent は提案するだけで確定・DB 更新はしない（D8 / P4）。提案結果はレスポンスとして返し、
         *     ユーザーがレビュー・編集して ``PUT /skills/display-decisions`` で確定する。
         *     外部 LLM を呼ぶ高コスト endpoint のため rate limit を付与し、課金はチャットと同一契約。
         */
        post: operations["propose_skill_display_names_endpoint_api_github_link_skills_display_names_propose_post"];
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
         * AdminCreditGrantRequest
         * @description 管理者によるクレジット付与（Phase 1 の残高調整・テスト用）。
         */
        AdminCreditGrantRequest: {
            /** Amount */
            amount: number;
            /** Description */
            description?: string | null;
            /** Username */
            username: string;
        };
        /**
         * AgentChatRequest
         * @description Agent チャットのリクエスト。スコープ選択は必須。
         */
        AgentChatRequest: {
            /** History */
            history?: components["schemas"]["AgentHistoryEntry"][];
            /**
             * Model
             * @default haiku
             * @enum {string}
             */
            model: "haiku" | "sonnet" | "gemini-flash" | "gemini-pro" | "gpt-mini" | "gpt";
            /** Prompt */
            prompt: string;
            resume: components["schemas"]["AgentResumeContext"];
            /**
             * Scope
             * @enum {string}
             */
            scope: "project" | "career_summary" | "self_pr" | "experience";
            /** Target */
            target?: components["schemas"]["ProjectTarget"] | components["schemas"]["ExperienceTarget"] | null;
        };
        /**
         * AgentChatResponse
         * @description Agent チャットのレスポンス（AI の説明文 + 差分 operations）。
         *
         *     ``suggestions`` は依頼が曖昧で operations を返せないときに LLM が生成する
         *     「次の依頼文の候補」。フロントはボタンとして表示し、押下されたテキストを
         *     そのまま次の ``prompt`` として再送信する。検証・件数制限は
         *     chat_service._parse_response が担う。
         */
        AgentChatResponse: {
            /** Message */
            message: string;
            /** Operations */
            operations?: components["schemas"]["AgentOperation"][];
            /** Suggestions */
            suggestions?: string[];
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
            /**
             * Description
             * @default
             */
            description: string;
            /**
             * Is It Company
             * @default true
             */
            is_it_company: boolean;
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
         * AgentUsageSummaryEntry
         * @description モデル別の使用量サマリ 1 件（モデル選択モーダルの利用実績表示用 / ADR-0012）。
         */
        AgentUsageSummaryEntry: {
            /** Chat Count */
            chat_count: number;
            /** Credit Cost */
            credit_cost: number;
            /** Input Tokens */
            input_tokens: number;
            /** Model */
            model: string;
            /** Output Tokens */
            output_tokens: number;
        };
        /**
         * AnalyzedRepoSummary
         * @description 連携で分析したリポジトリ 1 件分のサマリ（ADR-0018）。
         *
         *     経歴書ドラフト生成のルールベースマッピングが入力にする決定論データ。
         *     スキル証跡（github_skill_evidence）と同一連携実行時点のスナップショットになる。
         */
        AnalyzedRepoSummary: {
            /**
             * Created At
             * @description ISO 8601 形式の作成日時
             * @default
             */
            created_at: string;
            /**
             * Description
             * @description GitHub のリポジトリ説明（無ければ空文字）
             * @default
             */
            description: string;
            /**
             * Full Name
             * @description owner/name 形式のリポジトリ名
             */
            full_name: string;
            /**
             * Pushed At
             * @description ISO 8601 形式の最終 push 日時
             * @default
             */
            pushed_at: string;
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
         * CheckoutSessionRequest
         * @description クレジット購入の Stripe Checkout セッション作成リクエスト（ADR-0012 Phase 2）。
         */
        CheckoutSessionRequest: {
            /** Credits */
            credits: number;
        };
        /**
         * CheckoutSessionResponse
         * @description Stripe Checkout 決済ページの URL。フロントはこの URL へリダイレクトする。
         */
        CheckoutSessionResponse: {
            /** Checkout Url */
            checkout_url: string;
        };
        /**
         * Client
         * @description ユーザ（常駐先/クライアント企業）。
         *
         *     ``is_vacation=True`` の場合は取引先ではなく在籍中の休暇（育児/介護/留学等）を表し、
         *     name / projects の代わりに ``vacation_*`` 期間と詳細を保持する。
         */
        Client: {
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
            projects?: components["schemas"]["Project"][];
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
        /**
         * CreditBalanceResponse
         * @description クレジット残高。
         */
        CreditBalanceResponse: {
            /** Balance */
            balance: number;
        };
        /**
         * CreditPackResponse
         * @description 購入可能なクレジットパック 1 種（トークン購入画面用 / ADR-0012）。
         */
        CreditPackResponse: {
            /** Credits */
            credits: number;
            /** Id */
            id: string;
            /** Name */
            name: string;
            /** Price Jpy */
            price_jpy: number;
        };
        /**
         * CreditTransactionResponse
         * @description クレジット台帳エントリ 1 件（履歴表示用）。
         */
        CreditTransactionResponse: {
            /** Amount */
            amount: number;
            /** Balance After */
            balance_after: number;
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /** Description */
            description?: string | null;
            /** Id */
            id: string;
            /** Transaction Type */
            transaction_type: string;
        };
        /** Experience */
        Experience: {
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
            clients?: components["schemas"]["Client"][];
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
        /**
         * ExperienceTarget
         * @description scope=experience のとき対象在籍企業を特定するインデックス。
         *
         *     ``extra="forbid"`` により ProjectTarget の 3 キー payload は
         *     ExperienceTarget にマッチしない（union で型を決定的に区別するため）。
         */
        ExperienceTarget: {
            /** Experience Index */
            experience_index: number;
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
            /**
             * Repos
             * @description 分析対象リポジトリのサマリ一覧（経歴書ドラフト生成の入力 / ADR-0018）
             */
            repos?: components["schemas"]["AnalyzedRepoSummary"][];
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
        /**
         * GitHubSkillItem
         * @description Layer 1: 正規化スキルと、その根拠・習熟度。
         */
        GitHubSkillItem: {
            /**
             * Canonical Name
             * @description 正規名（言語=Linguist 名 / package=package ID / infra=provider 名または raw resource type）
             */
            canonical_name: string;
            /**
             * Confirmed Display Name
             * @description 人間が確定した表示名（未確定は null / D11）
             */
            confirmed_display_name?: string | null;
            /**
             * Decision Reviewed
             * @description 人間レビュー済みか（D11）
             * @default false
             */
            decision_reviewed: boolean;
            /**
             * Decision Source
             * @description 確定の出所（agent / human。未確定は null / D11）
             */
            decision_source?: string | null;
            /**
             * Display Name
             * @description 機械（Linguist）由来の表示補正。未補正は null
             */
            display_name?: string | null;
            /**
             * Ecosystem
             * @description エコシステム（package は npm/pypi/go/cargo、infra は terraform 等）。言語では null
             */
            ecosystem?: string | null;
            /** Evidence */
            evidence?: components["schemas"]["SkillEvidence"][];
            /**
             * Group Id
             * @description 畳み込みグループ ID。同一 group_id のスキルは 1 表示へ畳む（D11）
             */
            group_id?: string | null;
            /**
             * Kind
             * @description スキル種別（language / package / infra）
             */
            kind: string;
            /**
             * Parent
             * @description 親（Linguist の group）
             */
            parent?: string | null;
            proficiency?: components["schemas"]["SkillProficiency"] | null;
        };
        /**
         * GitHubSkillsResponse
         * @description ユーザーの GitHub 連携スキル一覧（3 層）。
         */
        GitHubSkillsResponse: {
            /** Skills */
            skills?: components["schemas"]["GitHubSkillItem"][];
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
         * ModelRateEntry
         * @description モデル別の標準消費レート（回数目安の算出用 / ADR-0012）。
         *
         *     1 クレジット = ¥1。``baseline_credits_per_chat`` は標準的な 1 回の消費の概算で、
         *     フロントが残高・パックを「Sonnet 約N回」に換算するのに使う（無料モデルは 0）。
         */
        ModelRateEntry: {
            /** Baseline Credits Per Chat */
            baseline_credits_per_chat: number;
            /** Is Free */
            is_free: boolean;
            /** Model */
            model: string;
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
        Project: {
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
            experiences?: components["schemas"]["Experience"][];
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
         * ResumeDraftRequest
         * @description 経歴書ドラフト生成（ADR-0018）のリクエスト。
         *
         *     生成対象（リポジトリ集合）はサーバー側が連携キャッシュから決めるため、
         *     クライアントが指定するのは使用モデルのみ。
         */
        ResumeDraftRequest: {
            /**
             * Model
             * @default haiku
             * @enum {string}
             */
            model: "haiku" | "sonnet" | "gemini-flash" | "gemini-pro" | "gpt-mini" | "gpt";
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
            experiences?: components["schemas"]["Experience"][];
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
            experiences?: components["schemas"]["Experience"][];
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
         * SkillDisplayConfirmRequest
         * @description 表示名確定（人間）のバッチリクエスト（ADR-0016 D11）。
         */
        SkillDisplayConfirmRequest: {
            /** Decisions */
            decisions?: components["schemas"]["SkillDisplayDecisionInput"][];
        };
        /**
         * SkillDisplayDecisionInput
         * @description 人間が確定する 1 スキルの表示名（identity + 確定表示名 + グループ / D11）。
         */
        SkillDisplayDecisionInput: {
            /**
             * Canonical Name
             * @description 正規名
             */
            canonical_name: string;
            /**
             * Display Name
             * @description 確定した表示名
             */
            display_name: string;
            /**
             * Ecosystem
             * @description エコシステム（language は空文字）
             * @default
             */
            ecosystem: string;
            /**
             * Group Id
             * @description 畳み込みグループ ID（単独確定は null）
             */
            group_id?: string | null;
            /**
             * Kind
             * @description スキル種別
             */
            kind: string;
            /**
             * Source
             * @description 出所（agent / human）
             * @default human
             */
            source: string;
        };
        /**
         * SkillDisplayProposeRequest
         * @description 表示名提案（agent）のリクエスト（ADR-0016 D11）。
         *
         *     提案対象スキルはサーバーが連携結果から決めるため、クライアントは使用モデルのみ指定する。
         */
        SkillDisplayProposeRequest: {
            /**
             * Model
             * @default haiku
             * @enum {string}
             */
            model: "haiku" | "sonnet" | "gemini-flash" | "gemini-pro" | "gpt-mini" | "gpt";
        };
        /**
         * SkillDisplayProposeResponse
         * @description 表示名提案の結果（永続化されない。人間がレビュー・確定する / D11）。
         */
        SkillDisplayProposeResponse: {
            /** Groups */
            groups?: components["schemas"]["SkillDisplayProposedGroup"][];
        };
        /**
         * SkillDisplayProposedGroup
         * @description agent が提案した 1 表示スキル（表示名 + 畳むメンバー群 / D11）。
         */
        SkillDisplayProposedGroup: {
            /**
             * Display Name
             * @description 提案する表示名
             */
            display_name: string;
            /**
             * Members
             * @description このグループに畳むスキルの identity
             */
            members?: components["schemas"]["SkillIdentityRef"][];
        };
        /**
         * SkillDisplayResetRequest
         * @description 表示名確定の解除（リセット）リクエスト（ADR-0016 D11 / #496）。
         *
         *     指定 identity の確定行（Layer 3）を削除し、機械デフォルト（機械 display_name /
         *     canonical）へ完全に戻す。同一グループの全メンバー identity を渡せば畳み込みも解ける。
         */
        SkillDisplayResetRequest: {
            /** Identities */
            identities?: components["schemas"]["SkillIdentityRef"][];
        };
        /**
         * SkillEvidence
         * @description Layer 2: 技術×リポの根拠。
         */
        SkillEvidence: {
            /**
             * Confidence
             * @description 信頼度（0.0–1.0）
             */
            confidence: number;
            /**
             * Dependency Kind
             * @description 依存の種類（direct/dev/indirect/peer/build。言語では null）
             */
            dependency_kind?: string | null;
            /**
             * Language Bytes
             * @description 言語シグナルのバイト数（package では null）
             */
            language_bytes?: number | null;
            /**
             * Manifest Path
             * @description 根拠ファイルの相対パス（package の manifest / infra の .tf。例 backend/requirements.txt・infra/main.tf。言語では null）
             */
            manifest_path?: string | null;
            /**
             * Partial Scan
             * @description 網羅でない部分スキャン由来か（証跡の過信防止。言語では常に false）
             * @default false
             */
            partial_scan: boolean;
            /**
             * Repo Full Name
             * @description 根拠リポジトリ（owner/name）
             */
            repo_full_name: string;
            /**
             * Repo Url
             * @description リポジトリ URL（経歴書の証跡用）
             */
            repo_url: string;
            /**
             * Signal Source
             * @description 根拠の出所（language_bytes / manifest_declared / actual_import / infra_declared）
             */
            signal_source: string;
        };
        /**
         * SkillIdentityRef
         * @description スキルの安定 identity（github_skills と一致 / D11）。
         */
        SkillIdentityRef: {
            /**
             * Canonical Name
             * @description 正規名（package ID / 言語名 / raw resource type）
             */
            canonical_name: string;
            /**
             * Ecosystem
             * @description エコシステム（language は空文字）
             * @default
             */
            ecosystem: string;
            /**
             * Kind
             * @description スキル種別（language / package / infra）
             */
            kind: string;
        };
        /**
         * SkillProficiency
         * @description Layer 3: 習熟度・文脈（人間/agent が後追いで埋める。本フェーズは未投入）。
         */
        SkillProficiency: {
            /**
             * Duration Months
             * @description 従事期間（月）
             */
            duration_months?: number | null;
            /**
             * Narrative
             * @description 文脈の説明文
             */
            narrative?: string | null;
            /**
             * Reviewed
             * @description 人間レビュー済みか
             * @default false
             */
            reviewed: boolean;
            /**
             * Scale
             * @description 規模
             */
            scale?: string | null;
            /**
             * Self Assessed Level
             * @description 自己評価レベル
             */
            self_assessed_level?: string | null;
            /**
             * Source
             * @description 出所（agent / human）
             */
            source?: string | null;
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
         *     github_link など複数の router で共通利用される。
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
    download_resume_draft_pdf_api_agent_resume_draft_pdf_get: {
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
                    "application/json": unknown;
                };
            };
        };
    };
    start_resume_draft_api_agent_resume_draft_run_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ResumeDraftRequest"];
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
    get_resume_draft_status_api_agent_resume_draft_status_get: {
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
    admin_grant_credits_api_billing_admin_grant_post: {
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
                "application/json": components["schemas"]["AdminCreditGrantRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CreditBalanceResponse"];
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
    get_credit_balance_api_billing_balance_get: {
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
                    "application/json": components["schemas"]["CreditBalanceResponse"];
                };
            };
        };
    };
    create_checkout_api_billing_checkout_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["CheckoutSessionRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CheckoutSessionResponse"];
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
    list_model_rates_api_billing_model_rates_get: {
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
                    "application/json": components["schemas"]["ModelRateEntry"][];
                };
            };
        };
    };
    list_credit_packs_api_billing_packs_get: {
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
                    "application/json": components["schemas"]["CreditPackResponse"][];
                };
            };
        };
    };
    list_credit_transactions_api_billing_transactions_get: {
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
                    "application/json": components["schemas"]["CreditTransactionResponse"][];
                };
            };
        };
    };
    get_usage_summary_api_billing_usage_summary_get: {
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
                    "application/json": components["schemas"]["AgentUsageSummaryEntry"][];
                };
            };
        };
    };
    stripe_webhook_api_billing_webhook_post: {
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
                        [key: string]: boolean;
                    };
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
    get_skills_api_github_link_skills_get: {
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
                    "application/json": components["schemas"]["GitHubSkillsResponse"];
                };
            };
        };
    };
    confirm_skill_display_decisions_api_github_link_skills_display_decisions_put: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["SkillDisplayConfirmRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["GitHubSkillsResponse"];
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
    reset_skill_display_decisions_api_github_link_skills_display_decisions_delete: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["SkillDisplayResetRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["GitHubSkillsResponse"];
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
    propose_skill_display_names_endpoint_api_github_link_skills_display_names_propose_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["SkillDisplayProposeRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SkillDisplayProposeResponse"];
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
                    "application/json": {
                        [key: string]: unknown;
                    };
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
