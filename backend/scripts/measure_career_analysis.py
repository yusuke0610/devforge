"""AI キャリア分析の並列化検証 Phase 0 計測スクリプト。

以下を測定する:
1. 現状プロンプトのトークン量（system + user / 出力）
2. 分割プロンプト（短期 / 中期 / 長期）のトークン量（共通コンテキスト x 3 のオーバーヘッドを可視化）
3. 直列実行 vs `asyncio.gather` 並列実行のレイテンシ
4. 並列リクエスト時のエラー率 / QPS 限界の初期観測

実行方法:
    cd backend
    VERTEX_PROJECT_ID=... VERTEX_LOCATION=asia-northeast1 \
    SQLITE_DB_PATH=./local.sqlite \
    .venv/bin/python scripts/measure_career_analysis.py --user-id <uuid> --target SRE --runs 3

LLM を叩かず静的にトークン量だけ見たい場合:
    .venv/bin/python scripts/measure_career_analysis.py --user-id <uuid> --target SRE --no-call

結果は標準出力 + 指定時は Markdown で
`docs/runbook/career_analysis_parallel_investigation.md` に追記する。
"""

from __future__ import annotations

import argparse
import asyncio
import os
import statistics
import sys
import time
from dataclasses import dataclass
from pathlib import Path

# backend/ をパスに追加
BACKEND_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_ROOT))

from app.db.database import SessionLocal  # noqa: E402
from app.models import BlogSummaryCache, GitHubLinkCache, Resume  # noqa: E402
from app.services.career_analysis.prompt_builder import build_user_prompt  # noqa: E402
from app.services.career_analysis.tech_stack_merger import (  # noqa: E402
    collect_github_skills,
    collect_qualification_names,
    collect_resume_tech_stacks,
    merge_tech_stacks,
)
from app.services.intelligence.llm import get_llm_client  # noqa: E402
from app.utils.prompt_loader import load_prompt  # noqa: E402

# ───────────────────────────────────────────────
# サブステップ用の分割プロンプト
# career_analysis.md の分析指針を継承し、出力を horizon 単位に絞る
# ───────────────────────────────────────────────

_HORIZON_LABELS = {
    "short": "短期（1年以内）",
    "mid": "中期（3年以内）",
    "long": "長期（5年以内）",
}

_SPLIT_OUTPUT_OVERRIDE = """

---

## 追加指示（サブステップ分割用）

このリクエストでは上記スキーマのうち **{horizon_label} のパスのみ** を返してください。
他の horizon は含めず、以下の単一オブジェクトを JSON で返すこと（コードブロック・前置き不要）：

{{
  "horizon": "{horizon}",
  "label": "{horizon_label}",
  "title": "...",
  "description": "...",
  "required_skills": [],
  "gap_skills": [],
  "fit_score": 0-100
}}

growth_summary / tech_stack / strengths / action_items は含めないこと。
「技術スタック評価の優先順位」「入力データの取り扱い」「ルール」は引き続き厳守すること。
"""


def _build_split_system_prompt(horizon: str) -> str:
    """実運用プロンプト（career_analysis.md）に出力範囲の上書きのみ追加する。

    検証で測るトークン量・品質を実装時と揃えるため、分析指針は共通のものを使う。
    """
    base = load_prompt("career_analysis.md")
    override = _SPLIT_OUTPUT_OVERRIDE.format(
        horizon=horizon, horizon_label=_HORIZON_LABELS[horizon]
    )
    return base + override


# ───────────────────────────────────────────────
# 計測ユーティリティ
# ───────────────────────────────────────────────


@dataclass
class PromptBundle:
    system_prompt: str
    user_prompt: str


@dataclass
class LatencyStats:
    label: str
    samples: list[float]

    @property
    def avg_ms(self) -> float:
        return statistics.mean(self.samples) * 1000 if self.samples else 0.0

    @property
    def p95_ms(self) -> float:
        if not self.samples:
            return 0.0
        ordered = sorted(self.samples)
        idx = min(len(ordered) - 1, int(len(ordered) * 0.95))
        return ordered[idx] * 1000

    def dump(self) -> str:
        return f"{self.label}: avg={self.avg_ms:.0f}ms p95={self.p95_ms:.0f}ms n={len(self.samples)}"


def _approx_tokens(text: str) -> int:
    """ローカルで使える簡易トークン概算。

    日本語混在テキスト向けに char/2 を採用（Gemini/Claude の経験則）。
    厳密な値は Vertex の ``count_tokens`` を使うので、ここはオフライン確認用の
    大枠のあたりをつけるためだけに使う。
    """
    return max(1, len(text) // 2)


async def _count_tokens_remote(client, contents: str, system: str) -> int | None:
    """google-genai の count_tokens で正確なトークン数を取得する。

    Vertex 以外（Ollama）では None を返す。
    """
    try:
        inner = getattr(client, "_get_client", None)
        if inner is None:
            return None
        real = inner()
        resp = await real.aio.models.count_tokens(
            model=getattr(client, "model_name", "gemini-2.5-flash-lite"),
            contents=f"{system}\n\n{contents}",
        )
        return int(getattr(resp, "total_tokens", 0))
    except Exception as exc:  # 計測失敗は致命ではない
        print(f"[warn] count_tokens 失敗: {exc}", file=sys.stderr)
        return None


# ───────────────────────────────────────────────
# プロンプト構築
# ───────────────────────────────────────────────


def build_prompts_for_user(user_id: str, target_position: str) -> tuple[PromptBundle, dict[str, PromptBundle]]:
    """現状の単発プロンプトと、サブステップ分割プロンプト 3 本を作って返す。"""
    db = SessionLocal()
    try:
        resume = db.query(Resume).filter_by(user_id=user_id).first()
        analysis_cache = db.query(GitHubLinkCache).filter_by(user_id=user_id).first()
        blog_cache = db.query(BlogSummaryCache).filter_by(user_id=user_id).first()

        resume_techs = collect_resume_tech_stacks(resume) if resume else set()
        github_skills = collect_github_skills(analysis_cache)
        qualification_names = collect_qualification_names(resume)
        merged_stacks_text = merge_tech_stacks(resume_techs, github_skills, qualification_names)

        user_prompt = build_user_prompt(
            target_position, resume, analysis_cache, blog_cache, merged_stacks_text,
        )
    finally:
        db.close()

    current = PromptBundle(
        system_prompt=load_prompt("career_analysis.md"),
        user_prompt=user_prompt,
    )
    split = {
        h: PromptBundle(
            system_prompt=_build_split_system_prompt(h),
            user_prompt=user_prompt,
        )
        for h in ("short", "mid", "long")
    }
    return current, split


# ───────────────────────────────────────────────
# LLM 呼び出し
# ───────────────────────────────────────────────


async def _single_call(client, bundle: PromptBundle) -> tuple[float, str]:
    start = time.monotonic()
    out = await client.generate(bundle.system_prompt, bundle.user_prompt)
    elapsed = time.monotonic() - start
    return elapsed, out


async def measure_serial(client, bundles: list[PromptBundle]) -> LatencyStats:
    times: list[float] = []
    start = time.monotonic()
    for b in bundles:
        t, _ = await _single_call(client, b)
        times.append(t)
    total = time.monotonic() - start
    return LatencyStats(label=f"serial x{len(bundles)}", samples=[total, *times])


def _error_key(exc: Exception) -> str:
    """例外を `種別名(HTTPステータス)` の形に要約する。QPS 限界の切り分けに使う。"""
    name = type(exc).__name__
    status = getattr(exc, "code", None)
    if not isinstance(status, int):
        status = getattr(exc, "status_code", None)
    return f"{name}({status})" if isinstance(status, int) else name


async def measure_parallel(
    client, bundles: list[PromptBundle]
) -> tuple[LatencyStats, dict[str, int]]:
    """並列実行の合計レイテンシと、エラー種別別カウントを返す。"""
    start = time.monotonic()
    results = await asyncio.gather(
        *[_single_call(client, b) for b in bundles], return_exceptions=True,
    )
    total = time.monotonic() - start
    per_call: list[float] = []
    error_counts: dict[str, int] = {}
    error_samples: dict[str, str] = {}
    for r in results:
        if isinstance(r, Exception):
            key = _error_key(r)
            error_counts[key] = error_counts.get(key, 0) + 1
            error_samples.setdefault(key, str(r)[:200])
        else:
            t, _ = r
            per_call.append(t)
    for key, count in error_counts.items():
        print(f"[warn] parallel error {key} x{count}: {error_samples[key]}", file=sys.stderr)
    return (
        LatencyStats(label=f"parallel x{len(bundles)}", samples=[total, *per_call]),
        error_counts,
    )


# ───────────────────────────────────────────────
# メイン
# ───────────────────────────────────────────────


async def main_async(args) -> None:
    current, split = build_prompts_for_user(args.user_id, args.target)

    print("=" * 72)
    print("Phase 0 計測 — AI キャリア分析サブステップ分割")
    print("=" * 72)

    # 1. トークン量
    print("\n## 1. プロンプトサイズ（文字数 / 概算トークン）")
    print(f"  [current] system={len(current.system_prompt)}c user={len(current.user_prompt)}c "
          f"≈{_approx_tokens(current.system_prompt) + _approx_tokens(current.user_prompt)} tok")
    split_total = 0
    for h, b in split.items():
        approx = _approx_tokens(b.system_prompt) + _approx_tokens(b.user_prompt)
        split_total += approx
        print(f"  [split:{h}] system={len(b.system_prompt)}c user={len(b.user_prompt)}c ≈{approx} tok")
    current_approx = _approx_tokens(current.system_prompt) + _approx_tokens(current.user_prompt)
    overhead_pct = (split_total / current_approx - 1) * 100 if current_approx else 0
    print(f"  [split:total] ≈{split_total} tok   vs current: +{overhead_pct:.1f}%")

    if args.no_call:
        print("\n(--no-call 指定のため LLM 呼び出しをスキップ)")
        return

    client = get_llm_client()
    if not await client.check_available():
        print("\n[error] LLM クライアントが利用不可（VERTEX_PROJECT_ID 等を確認）", file=sys.stderr)
        sys.exit(1)

    # 2. Vertex 正確トークン
    print("\n## 2. Vertex count_tokens（正確値）")
    current_tokens = await _count_tokens_remote(client, current.user_prompt, current.system_prompt)
    if current_tokens is not None:
        print(f"  [current] total={current_tokens} tok")
    per_split_tokens: dict[str, int | None] = {}
    for h, b in split.items():
        per_split_tokens[h] = await _count_tokens_remote(client, b.user_prompt, b.system_prompt)
        print(f"  [split:{h}] total={per_split_tokens[h]} tok")
    split_sum = sum(v for v in per_split_tokens.values() if v is not None)
    if current_tokens and split_sum:
        print(f"  [split:total] {split_sum} tok   vs current: +{(split_sum / current_tokens - 1) * 100:.1f}%")

    # 3. レイテンシ計測
    print(f"\n## 3. レイテンシ計測（runs={args.runs}）")
    all_serial: list[float] = []
    all_parallel: list[float] = []
    total_requests = 0
    aggregated_errors: dict[str, int] = {}
    for i in range(args.runs):
        print(f"  run {i + 1}/{args.runs}...")
        s = await measure_serial(client, list(split.values()))
        all_serial.append(s.samples[0])
        print(f"    {s.dump()}")
        p, errors = await measure_parallel(client, list(split.values()))
        all_parallel.append(p.samples[0])
        total_requests += len(split)
        for key, count in errors.items():
            aggregated_errors[key] = aggregated_errors.get(key, 0) + count
        print(f"    {p.dump()}")

    print("\n## 4. 集約")
    print(f"  serial   avg={statistics.mean(all_serial)*1000:.0f}ms (total of 3 sub-tasks)")
    print(f"  parallel avg={statistics.mean(all_parallel)*1000:.0f}ms (asyncio.gather)")
    speedup = statistics.mean(all_serial) / statistics.mean(all_parallel) if all_parallel else 0
    print(f"  speedup  x{speedup:.2f}")

    total_errors = sum(aggregated_errors.values())
    error_rate = (total_errors / total_requests * 100) if total_requests else 0
    print(
        f"  parallel errors: {total_errors}/{total_requests} ({error_rate:.1f}%)"
    )
    for key, count in sorted(aggregated_errors.items(), key=lambda kv: -kv[1]):
        print(f"    - {key}: {count}")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="AI キャリア分析 Phase 0 計測")
    p.add_argument("--user-id", required=True, help="計測対象ユーザーの user_id")
    p.add_argument("--target", required=True, help="ターゲットポジション（例: SRE）")
    p.add_argument("--runs", type=int, default=3, help="レイテンシ計測の試行回数")
    p.add_argument("--no-call", action="store_true", help="LLM を呼ばずプロンプトサイズだけ確認")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    # SessionLocal が SQLITE_DB_PATH を見るため念のためエクスポート確認
    if not os.environ.get("SQLITE_DB_PATH"):
        print("[warn] SQLITE_DB_PATH 未設定（local.sqlite を見にいきます）", file=sys.stderr)
    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
