"""ドラフト骨格のルールベースマッピング（決定論・純関数 / ADR-0018・0026）。

GitHub 連携データ（DraftSource）から、**プロジェクト明細のリスト**を組み立てる
（ADR-0026 決定 1 で出力単位を experience から project へ縮小した）。自然文
（career_summary / self_pr / プロジェクト description）は空または repo description の
ままにし、draft_service が LLM 出力をマージする。PDF レンダリングに渡すときだけ
``build_pdf_payload`` で Resume 互換の形へ包む。

リポジトリの順位付け（``rank_repos``）とデフォルト選択判定
（``evaluate_default_selection``）もここに置く。どちらも決定論的な純関数で、
判定は候補を落とさずデフォルト選択状態と理由表示にのみ影響させる（ADR-0026 決定 2・3）。

DB・LLM・時刻に依存しない（``today`` は引数で受ける）。GitHub から得られない値
（会社・役割・担当工程・チーム規模）はここでは生成しない。
"""

import re
from dataclasses import dataclass
from datetime import date

from .context import DraftSource, RepoTechnology

# ドラフトに載せるプロジェクト（リポジトリ）数の上限。LLM 出力の有界化と
# 同期エンドポイントのレイテンシ上限（ADR-0018）のための定数
PROJECT_LIMIT = 5
# 1 プロジェクトに載せる技術スタック数の上限（経歴書としての可読性）
STACK_LIMIT_PER_PROJECT = 8
# 最終 push がこの日数以内なら「参画中」とみなす
_CURRENT_THRESHOLD_DAYS = 90

# 技術スタックの表示順（言語 → フレームワーク → IaC）
_CATEGORY_ORDER: dict[str, int] = {"language": 0, "framework": 1, "iac": 2}

# --- 選定スコアの重み（ADR-0026 決定 3。数値の正本はここ。ADR には複製しない） ---
# 実装量は「言語バイト合計」を 1 バイト = 1 点の基準にし、以下をバイト相当へ換算して加算する。
# 直接依存 1 件 = 小さめのモジュール 1 つ分、エコシステム 1 つ = 複数言語構成の証跡、
# IaC 宣言 = インフラまで手を入れた証跡、という重み付け。
DEPENDENCY_VOLUME_WEIGHT = 500
ECOSYSTEM_VOLUME_WEIGHT = 2_000
INFRA_VOLUME_WEIGHT = 5_000

# 継続期間がこの日数未満なら「デフォルト非選択」にする（候補からは落とさない）
MIN_DURATION_DAYS = 30

# デフォルト非選択の理由コード（web の理由バッジ表示に使う安定キー）
REASON_SHORT_DURATION = "short_duration"
REASON_LEARNING_TOPIC = "learning_topic"

# 学習用途を示す topics 語彙。突合は _normalize_topics が作る語トークンとの完全一致
LEARNING_TOPICS = frozenset(
    {
        "tutorial", "tutorials",
        "practice", "practices",
        "sample", "samples",
        "study", "studying",
        "learn", "learning",
        "handson",
        "exercise", "exercises",
        "training",
        "playground",
        "sandbox",
        "demo", "demos",
    }
)


@dataclass(frozen=True)
class DefaultSelection:
    """デフォルト選択状態と、非選択にした理由コード。

    ``reasons`` は空タプルなら選択（理由バッジ無し）。判定結果はデフォルト選択状態と
    理由表示にのみ影響させ、**候補一覧からは決して落とさない**（ADR-0026 決定 2）。
    """

    selected: bool
    reasons: tuple[str, ...]


def evaluate_default_selection(
    repo, *, min_duration_days: int = MIN_DURATION_DAYS
) -> DefaultSelection:
    """リポジトリをデフォルト選択にするかを判定し、非選択なら理由を返す。

    判定は「継続期間が閾値未満」「topics に学習用途語を含む」の 2 つ。理由は
    web が理由バッジに使う安定キーで返し、順序は決定論（判定順）にする。

    Args:
        repo: 候補リポジトリ（``AnalyzedRepoSummary``）。
        min_duration_days: 継続期間の閾値（テスト注入用。省略時は既定値）。
    """
    reasons: list[str] = []
    if duration_days(repo) < min_duration_days:
        reasons.append(REASON_SHORT_DURATION)
    if _normalize_topics(repo.topics) & LEARNING_TOPICS:
        reasons.append(REASON_LEARNING_TOPIC)
    return DefaultSelection(selected=not reasons, reasons=tuple(reasons))


def _normalize_topics(topics: list[str]) -> set[str]:
    """topics を突合用の語トークン集合へ正規化する。

    小文字化し、英数字以外を区切りとして分割した各語に加えて、区切りを除去した
    連結形も入れる（``hands-on`` → ``hands`` / ``on`` / ``handson``）。
    突合は**語の完全一致**で行うため、``resample`` が ``sample`` に誤爆しない。
    """
    tokens: set[str] = set()
    for topic in topics:
        words = [word for word in re.split(r"[^a-z0-9]+", topic.lower()) if word]
        tokens.update(words)
        if len(words) > 1:
            tokens.add("".join(words))
    return tokens


def duration_days(repo) -> int:
    """リポジトリの継続期間（``pushed_at`` − ``created_at``）を日数で返す。

    日付が空・不正・逆転している場合は 0 日として扱う（捏造しない）。
    """
    created = _parse_date(repo.created_at)
    pushed = _parse_date(repo.pushed_at)
    if created is None or pushed is None:
        return 0
    return max((pushed - created).days, 0)


def implementation_volume(repo) -> int:
    """リポジトリの実装量スコアを返す（言語バイト合計を基準にした加点）。

    言語バイト合計を 1 バイト = 1 点の基準にし、依存の厚み（直接依存数・
    エコシステム数）と IaC 宣言を「バイト相当」へ換算して足し込む。
    重みの正本はこのモジュールの定数（ADR には数値を複製しない / ADR-0026 決定 3）。
    """
    return (
        max(repo.language_bytes_total, 0)
        + max(repo.direct_dependency_count, 0) * DEPENDENCY_VOLUME_WEIGHT
        + max(repo.ecosystem_count, 0) * ECOSYSTEM_VOLUME_WEIGHT
        + (INFRA_VOLUME_WEIGHT if repo.has_infra else 0)
    )


def selection_score(repo) -> int:
    """選定の主キーとなるスコア「継続期間 × 実装量」を返す（ADR-0026 決定 3）。

    チュートリアル・写経は数日で終わり、実プロジェクトは数ヶ月〜数年継続するため、
    継続期間は単一シグナルとしての判別力が最も高い。実装量を掛け合わせることで
    「長く放置されているだけの空リポ」が上位に来ないようにする。

    両項に 1 の下駄を履かせるのは、片方が 0 でももう一方で比較できるようにするため
    （継続 0 日の中では実装量の多い方が、実装量 0 の中では長く続いた方が上に来る）。
    **整数演算のみで計算する**。float の丸めで同点判定がブレると完全順序が崩れるため。
    """
    return (duration_days(repo) + 1) * (implementation_volume(repo) + 1)


def rank_repos(source: DraftSource) -> list:
    """候補リポジトリを決定論的に順位付けする（件数は減らさない / ADR-0026 決定 2）。

    第 1 キー: 選定スコア（継続期間 × 実装量）の降順
    タイブレーク 1: 最終 push 日時の降順（直近性は主キーから降格）
    タイブレーク 2: full_name の辞書順昇順（完全順序の担保）

    同一入力からは常に同一の並びを返す（入力順に依存しない）。
    """
    # 安定ソートを重ねて「タイブレーク昇順 → 主キー群降順」を実現する
    repos = sorted(source.repos, key=lambda r: r.full_name)
    return sorted(repos, key=lambda r: (selection_score(r), r.pushed_at), reverse=True)


def select_repos(source: DraftSource, limit: int = PROJECT_LIMIT) -> list:
    """ドラフトに載せるリポジトリを順位上位から上限件数まで選ぶ。"""
    return rank_repos(source)[:limit]


def build_skeleton(
    source: DraftSource, selected: list, *, today: date | None = None
) -> dict:
    """採用リポジトリからドラフト payload の骨格を組み立てる（ADR-0026 決定 1）。

    出力単位は**プロジェクト明細のリスト**。会社・事業内容・在籍期間・顧客
    （experience の情報）は GitHub に存在しないため生成しない。
    ``career_summary`` / ``self_pr`` は projects から独立した候補として持ち、
    draft_service が LLM 出力をマージする。

    ``today`` は「参画中」判定の基準日。テストからの注入用で、省略時は当日。
    """
    reference_date = today or date.today()

    return {
        "full_name": source.username,
        "email": source.email,
        "github_url": f"https://github.com/{source.username}",
        "career_summary": "",
        "self_pr": "",
        "projects": [
            _build_project(repo, source.repo_technologies.get(repo.full_name, []), reference_date)
            for repo in selected
        ],
    }


def build_pdf_payload(draft: dict) -> dict:
    """ドラフトを ``build_resume_pdf`` が受け取れる Resume 互換 payload へ包む。

    PDF は「プロジェクト明細のプレビュー」なので、projects を**空の**
    experience / client 1 件で包むだけにする。会社名・事業内容・顧客名は
    プレースホルダを入れず空のままにする（ADR-0026 決定 1 の徹底）。
    projects が 0 件なら空箱すら作らない。

    元の ``draft`` は書き換えない（同じ payload を PDF と JSON 注入の双方が使うため）。
    """
    projects = draft.get("projects") or []
    experiences = (
        [
            {
                "company": "",
                "business_description": "",
                "is_it_company": True,
                "start_date": "",
                "end_date": "",
                "is_current": False,
                "clients": [{"name": "", "is_vacation": False, "projects": projects}],
            }
        ]
        if projects
        else []
    )
    payload = {key: value for key, value in draft.items() if key != "projects"}
    payload["experiences"] = experiences
    payload["qualifications"] = []
    return payload


def _build_project(repo, technologies: list[RepoTechnology], reference_date: date) -> dict:
    """リポジトリ 1 件をプロジェクト 1 件に写す。

    description は LLM 出力で置換される前提のフォールバックとして repo description を
    先に入れておく（LLM 側の欠落 degrade / ADR-0018）。
    """
    is_current = _is_recently_pushed(repo.pushed_at, reference_date)
    periods = []
    start = _year_month(repo.created_at)
    if start:
        periods.append(
            {
                "start_date": start,
                # 参画中は end を "" で渡す契約（schemas/resume.py と同じ）
                "end_date": "" if is_current else _year_month(repo.pushed_at),
                "is_current": is_current,
            }
        )
    return {
        "name": repo.full_name.split("/", 1)[-1],
        # role / phases / team は GitHub から得られないため生成しない（人間が埋める）
        "role": "",
        "description": repo.description,
        "periods": periods,
        "team": {"total": "", "members": []},
        "phases": [],
        "technology_stacks": [
            {"category": tech.category, "name": tech.name}
            for tech in _select_stacks(technologies)
        ],
    }


def _select_stacks(technologies: list[RepoTechnology]) -> list[RepoTechnology]:
    """技術スタックを表示順に並べ、上限件数に絞る。

    カテゴリ順（言語 → FW → IaC）→ 量的シグナル（バイト数・confidence）降順 →
    名前昇順の決定論ソート。
    """
    ordered = sorted(technologies, key=lambda t: t.name)
    ordered = sorted(ordered, key=lambda t: (t.language_bytes, t.confidence), reverse=True)
    ordered = sorted(ordered, key=lambda t: _CATEGORY_ORDER.get(t.category, len(_CATEGORY_ORDER)))
    return ordered[:STACK_LIMIT_PER_PROJECT]


def _year_month(iso_datetime: str) -> str:
    """ISO 8601 日時文字列から YYYY-MM を取り出す（不正・空は空文字）。"""
    return iso_datetime[:7] if len(iso_datetime) >= 7 else ""


def _is_recently_pushed(pushed_at: str, reference_date: date) -> bool:
    """最終 push が基準日から閾値日数以内かどうか。"""
    pushed = _parse_date(pushed_at)
    if pushed is None:
        return False
    return (reference_date - pushed).days <= _CURRENT_THRESHOLD_DAYS


def _parse_date(iso_datetime: str) -> date | None:
    """ISO 8601 日時文字列の日付部分を取り出す（空・不正は None）。"""
    try:
        return date.fromisoformat(iso_datetime[:10])
    except ValueError:
        return None
