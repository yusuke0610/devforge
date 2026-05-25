"""AI キャリアパス分析 LLM プロンプト構築ロジック。

build_user_prompt を提供する。システムプロンプトは
backend/prompts/career_analysis.md から都度読み込む。
LLM 呼び出し自体は builder.py が担う。

企業名・顧客名・案件名・自由記述は LLM へ渡す前にサニタイザー経由でマスキングする。
氏名等の C 分類フィールドはプロンプトに含めない。
"""

from ...models import BlogSummaryCache, GitHubAnalysisCache, Resume
from ..llm.sanitizer import SanitizeContext, sanitize_project_name, sanitize_text


def _build_sanitize_context(resume: Resume | None) -> SanitizeContext:
    """Resume から登場するエンティティをコンテキストに事前登録して返す。

    事前登録することで自由記述テキスト内の同一名称を sanitize_text() で置換できる。
    """
    context = SanitizeContext()
    if not resume:
        return context
    for exp in resume.experiences:
        context.register_company(exp.company)
        for client in exp.clients:
            context.register_customer(client.name)
            for proj in client.projects:
                context.register_project(proj.name)
    return context


def build_user_prompt(
    target_position: str,
    resume: Resume | None,
    analysis_cache: GitHubAnalysisCache | None,
    blog_cache: BlogSummaryCache | None,
    merged_stacks_text: str,
) -> str:
    """ユーザープロンプトを動的に組み立てる。

    氏名は LLM に渡さない。企業名・顧客名・案件名はラベルにマスキングする。
    自由記述テキスト（career_summary / 案件概要 / ブログ要約）は
    登録済みエンティティを sanitize_text() で置換する。
    """
    parts: list[str] = []
    context = _build_sanitize_context(resume)

    parts.append(f"## ターゲットポジション\n{target_position}")

    # 資格
    parts.append("\n## 資格")
    if resume and resume.qualifications:
        quals = [f"- {q.name}（{q.acquired_date}）" for q in resume.qualifications]
        parts.append("\n".join(quals))
    else:
        parts.append("なし")

    # 職務経歴
    parts.append("\n## 職務経歴（本業・IT 業界入社以降）")

    if resume:
        if resume.career_summary:
            parts.append(
                f"\n### 職務要約\n{sanitize_text(resume.career_summary, context)}"
            )

        parts.append("\n### 担当プロジェクト一覧")
        for exp in resume.experiences:
            company_label = context.companies.get(exp.company, exp.company)
            for client in exp.clients:
                client_label = (
                    context.customers.get(client.name, client.name) if client.name else ""
                )
                for proj in client.projects:
                    end = proj.end_date or "現在"
                    phases = ", ".join(proj.phases) if proj.phases else "不明"
                    stacks = ", ".join(st.name for st in proj.technology_stacks)
                    parts.append(
                        f"- 案件名: {sanitize_project_name(proj.name, context)}"
                    )
                    parts.append(f"  所属: {company_label}")
                    if client_label:
                        parts.append(f"  取引先: {client_label}")
                    parts.append(f"  期間: {proj.start_date} 〜 {end}")
                    parts.append(f"  担当フェーズ: {phases}")
                    parts.append(f"  使用技術: {stacks}")
    else:
        parts.append("（職務経歴書未入力）")

    # 技術スタック（マージ済み）
    parts.append(f"\n### 技術スタック（マージ済み・優先度付き）\n{merged_stacks_text}")

    # GitHub 分析
    if analysis_cache and analysis_cache.analysis_result:
        ar = analysis_cache.analysis_result
        parts.append("\n## GitHub 個人活動")

        scores = ar.get("position_scores", {})
        if scores:
            parts.append(
                f"ポジションスコア: backend={scores.get('backend', 0)}, "
                f"frontend={scores.get('frontend', 0)}, "
                f"sre={scores.get('sre', 0)}, "
                f"cloud={scores.get('cloud', 0)}, "
                f"fullstack={scores.get('fullstack', 0)}"
            )
            missing = scores.get("missing_skills", [])
            if missing:
                parts.append(f"差分分析（不足スキル）: {', '.join(missing)}")

        languages = ar.get("languages", {})
        if languages:
            total = sum(languages.values()) or 1
            sorted_langs = sorted(languages.items(), key=lambda x: x[1], reverse=True)[:10]
            lang_strs = [f"{name}: {b * 100 // total}%" for name, b in sorted_langs]
            parts.append(f"主要言語: {', '.join(lang_strs)}")

        # 検出フレームワーク・DevTools・インフラは設計思想・成熟度の評価根拠として別行で明示する
        def _extract_names(value: object) -> list[str]:
            """新形式（Dict[str, int]）・旧形式（List[str]）のどちらにも対応する。"""
            if isinstance(value, dict):
                return list(value.keys())
            if isinstance(value, list):
                return list(value)
            return []

        fw_names = _extract_names(ar.get("detected_frameworks"))
        if fw_names:
            parts.append(f"検出フレームワーク: {', '.join(fw_names)}")
        dt_names = _extract_names(ar.get("detected_devtools"))
        if dt_names:
            parts.append(f"DevTools: {', '.join(dt_names)}")
        inf_names = _extract_names(ar.get("detected_infras"))
        if inf_names:
            parts.append(f"インフラ: {', '.join(inf_names)}")

        all_skills: set[str] = set()
        for repo in ar.get("repositories", []):
            for s in repo.get("skills", []):
                all_skills.add(s)
        if all_skills:
            parts.append(f"検出スキル: {', '.join(sorted(all_skills))}")

    # ブログ発信力
    if blog_cache and blog_cache.summary:
        parts.append(
            f"\n## ブログ発信力\n{sanitize_text(blog_cache.summary, context)}"
        )

    parts.append(
        "\n---\n上記を踏まえて、指定の JSON スキーマでキャリアパス提案レポートを返してください。"
    )

    return "\n".join(parts)
