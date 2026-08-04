"""ドラフト骨格のルールベースマッピング（決定論・純関数 / ADR-0018）。

GitHub 連携データ（DraftSource）から、``build_resume_pdf(dict)`` が受け取れる
経歴書 payload の骨格を組み立てる。自然文（career_summary / self_pr /
プロジェクト description）は空または repo description のままにし、
draft_service が LLM 出力をマージする。

DB・LLM・時刻に依存しない（``today`` は引数で受ける）。捏造につながる値
（担当工程・チーム規模の水増し等）はここでは生成しない。
"""

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

# 個人開発プレースホルダ（GitHub からは職歴が得られないため / ADR-0018）
PLACEHOLDER_COMPANY = "個人開発"
PLACEHOLDER_BUSINESS_DESCRIPTION = "GitHub 上での個人開発活動"
PLACEHOLDER_ROLE = "開発（個人開発）"

# 技術スタックの表示順（言語 → フレームワーク → IaC）
_CATEGORY_ORDER: dict[str, int] = {"language": 0, "framework": 1, "iac": 2}


NOISE_REASON_SHORT_LIVED = "継続期間が短い"
NOISE_REASON_LEARNING_TOPIC = "学習用途の topics"

# これ未満の継続期間はデフォルト非選択にする。チュートリアル・写経は数日〜数週で
# 終わるため、1 ヶ月継続を「作り込んだ」の下限とする（ADR-0026 決定 3）
_SHORT_LIVED_THRESHOLD_DAYS = 30

# 学習用途を示す topics（正規化後の完全一致で判定する）
_LEARNING_TOPICS = frozenset(
    {
        "tutorial", "practice", "sample", "study", "learning", "handson",
        "example", "demo", "playground", "boilerplate",
    }
)


@dataclass(frozen=True)
class NoiseVerdict:
    """デフォルト選択状態と、非選択にした理由（ADR-0026 決定 2）。

    **機械は候補を落とさない**。本判定は UI のデフォルト選択状態と理由表示にのみ
    影響させ、``select_repos`` の結果からは除外しない。価値判断は人間が行う。
    """

    selected_by_default: bool
    # frozen の不変性を実際に担保するため tuple にする（list だと要素を書き換えられる）
    reasons: tuple[str, ...]


def _normalize_topic(topic: str) -> str:
    """topics を比較用に正規化する（小文字化 + 区切り除去）。

    ``hands-on`` / ``Hands_On`` / ``HANDSON`` を同一視する。部分一致は採らない
    （``sample-api-server`` のような本命を誤判定するため）。
    """
    return topic.lower().replace("-", "").replace("_", "")


def evaluate_noise(repo, *, threshold_days: int = _SHORT_LIVED_THRESHOLD_DAYS) -> NoiseVerdict:
    """デフォルト非選択にすべきリポジトリかを判定する（ADR-0026 決定 2・3）。

    ``threshold_days`` はテストからの注入用（``build_skeleton(today=...)`` と同じ流儀）。
    理由は判定順に積むため、同じ入力からは常に同じ並びで返る。
    """
    reasons: list[str] = []
    if _active_days(repo) < threshold_days:
        reasons.append(NOISE_REASON_SHORT_LIVED)
    if any(_normalize_topic(topic) in _LEARNING_TOPICS for topic in repo.topics):
        reasons.append(NOISE_REASON_LEARNING_TOPIC)
    return NoiseVerdict(selected_by_default=not reasons, reasons=tuple(reasons))


def _active_days(repo) -> int:
    """継続期間（created_at → pushed_at の日数）。不正・空の日付は 0 とする。

    チュートリアル・写経は数日で終わり、実プロジェクトは数ヶ月〜数年継続するため、
    単一シグナルとしての判別力が最も高い（ADR-0026 決定 3）。
    """
    try:
        created = date.fromisoformat(repo.created_at[:10])
        pushed = date.fromisoformat(repo.pushed_at[:10])
    except ValueError:
        return 0
    return max((pushed - created).days, 0)


def select_repos(source: DraftSource, limit: int = PROJECT_LIMIT) -> list:
    """ドラフトに載せるリポジトリを決定論的に選定する（ADR-0026 決定 3）。

    第 1 キー: 継続期間の降順（作り込んで続けたリポを優先）
    第 2 キー: 言語バイト合計の降順（実装量の多いリポを優先）
    第 3 キー: 最終 push 日時の降順（直近性はタイブレークへ降格）
    最終タイブレーク: full_name の辞書順（決定論の担保）

    継続期間と実装量は重み付けせず段階比較する。積や重み付き和は係数の恣意性が
    入り、「継続 1000 日 × 1KB」と「10 日 × 100KB」が並んでしまう。
    """
    # 安定ソートを重ねて「タイブレーク昇順 → 主キー群降順」を実現する
    repos = sorted(source.repos, key=lambda r: r.full_name)
    repos = sorted(
        repos,
        key=lambda r: (_active_days(r), r.language_bytes_total, r.pushed_at),
        reverse=True,
    )
    return repos[:limit]


def build_skeleton(
    source: DraftSource, selected: list, *, today: date | None = None
) -> dict:
    """選定リポジトリから経歴書 payload の骨格を組み立てる。

    ``today`` は「参画中」判定の基準日。テストからの注入用で、省略時は当日。
    """
    reference_date = today or date.today()

    projects = [
        _build_project(repo, source.repo_technologies.get(repo.full_name, []), reference_date)
        for repo in selected
    ]

    start_months = [
        _year_month(repo.created_at) for repo in selected if _year_month(repo.created_at)
    ]
    experience = {
        "company": PLACEHOLDER_COMPANY,
        "business_description": PLACEHOLDER_BUSINESS_DESCRIPTION,
        "is_it_company": True,
        "start_date": min(start_months) if start_months else "",
        "end_date": "",
        "is_current": True,
        "clients": [{"name": "", "is_vacation": False, "projects": projects}],
    }

    return {
        "full_name": source.username,
        "email": source.email,
        "github_url": f"https://github.com/{source.username}",
        "career_summary": "",
        "self_pr": "",
        "experiences": [experience],
        "qualifications": [],
    }


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
        "role": PLACEHOLDER_ROLE,
        "description": repo.description,
        "periods": periods,
        "team": {"total": "1", "members": [{"role": "開発", "count": 1}]},
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
    try:
        pushed = date.fromisoformat(pushed_at[:10])
    except ValueError:
        return False
    return (reference_date - pushed).days <= _CURRENT_THRESHOLD_DAYS
