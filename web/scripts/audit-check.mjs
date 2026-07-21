#!/usr/bin/env node
// npm audit のラッパー。`--audit-level=high` 相当のゲートを維持しつつ、
// 明示的に allowlist した advisory (GHSA) だけを「許容済み」として除外する。
//
// 背景:
//   素の `npm audit --audit-level=high` は「lockfile に脆弱バージョンが存在するか」だけを
//   見ており、実際に攻撃面へ到達可能かは区別しない。下記 2 件はいずれも esbuild の
//   dev 専用 advisory で、本番バンドルにも CI(Linux) ランタイムにも到達しない。
//   かつ修正版 (esbuild 0.28.1) は vite 6 のビルドを壊し、回避には vite 8 (Rolldown 移行)
//   が必要 / wrangler には修正版が存在しない、という事情がある。
//   そのため allowlist で時限的に許容し、恒久対応 (vite 8 移行) は別 PR で追う。
//
// 注意:
//   ここに無い High / Critical advisory が新たに出た場合は従来どおり CI を落とす。
//   allowlist は「個別の GHSA を理由付きで明示許容する」ためだけに使う。
//   `--force` での一括無視はしない（.claude/rules/security.md）。
//   reviewBy は "YYYY-MM-DD (説明)" 形式で必須。**期限は機械的に強制**され、
//   期限切れ・不正日付のエントリは fail-closed（CI を落とす）。見直し忘れによる
//   恒久的な握り潰しを防ぐため、期限を延ばすか脆弱パッケージ更新で対応する。

import { execFileSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";

const frontendDir = resolve(dirname(fileURLToPath(import.meta.url)), "..");

// 許容する advisory。GHSA ID をキーに、理由と見直し期限を残す。
// 恒久対応 (vite 8 / Rolldown 移行) 完了時にエントリを削除すること。
const ALLOWLIST = {
  "GHSA-52cp-r559-cp3m": {
    reason:
      "js-yaml の YAML merge-key チェーンによる二次的 CPU 消費 (DoS)。" +
      "openapi-typescript(dev 依存) → @redocly/openapi-core 経由の推移的依存で、" +
      "自前 backend の OpenAPI スキーマ (信頼済み) を codegen する時だけ使用。" +
      "本番バンドル非到達・攻撃者制御の YAML を parse しない。@redocly/openapi-core は" +
      "全バージョンが脆弱な js-yaml に依存し npm audit fix でも解消不可のため時限的に許容。",
    reviewBy: "2026-09-30 (openapi-typescript / @redocly の js-yaml>4.2.0 対応を待つ)",
  },
  "GHSA-gv7w-rqvm-qjhr": {
    reason:
      "esbuild の Deno モジュール install-time RCE (NPM_CONFIG_REGISTRY 経由)。" +
      "DevForge は npm(Linux) で導入し Deno 不使用のため到達不能。dev 依存。",
    reviewBy: "2026-09-30 (vite 8 / Rolldown 移行で esbuild 0.28.1 化を目指す)",
  },
  "GHSA-g7r4-m6w7-qqqr": {
    reason:
      "esbuild 自身の dev サーバーを Windows で起動した際の任意ファイル読み取り。" +
      "dev サーバーは Vite(Linux)、esbuild serve は未使用のため到達不能。dev 依存。",
    reviewBy: "2026-09-30 (vite 8 / Rolldown 移行で esbuild 0.28.1 化を目指す)",
  },
};

const BLOCKING_SEVERITIES = new Set(["high", "critical"]);

// `npm audit --json` は脆弱性検出時に exit code !=0 を返すため、例外から stdout を回収する。
// registry/auth/lockfile 等の実行失敗時も JSON を stdout に書き出し、その中に error を含める。
function runAudit() {
  try {
    return execFileSync("npm", ["audit", "--json"], {
      cwd: frontendDir,
      encoding: "utf8",
      maxBuffer: 64 * 1024 * 1024,
    });
  } catch (err) {
    // JSON が stdout に出ていれば（脆弱性検出 or audit 失敗）回収する。
    // stdout が空＝JSON すら出ない致命的クラッシュは本物のエラーとして投げる。
    if (typeof err.stdout === "string" && err.stdout.length > 0) return err.stdout;
    throw err;
  }
}

function ghsaIdFromUrl(url) {
  // 例: https://github.com/advisories/GHSA-gv7w-rqvm-qjhr
  const m = /\/(GHSA-[\w-]+)\b/.exec(url ?? "");
  return m ? m[1] : null;
}

const audit = JSON.parse(runAudit());

// npm audit 自体が registry/auth/lockfile 等で失敗した場合は JSON に error が乗る。
// これを成功扱い（脆弱性ゼロ）にすると fail-open になるため、必ず CI を落とす。
if (audit.error) {
  console.error(
    "npm audit の実行に失敗しました:",
    audit.error.summary ?? audit.error.code ?? audit.error.message ?? audit.error,
  );
  process.exit(1);
}

// 各パッケージの via から「advisory 本体オブジェクト」を集約し、GHSA 単位で重複排除する。
const advisories = new Map(); // ghsaId -> { id, title, severity, url }
for (const vuln of Object.values(audit.vulnerabilities ?? {})) {
  for (const via of vuln.via ?? []) {
    if (typeof via !== "object") continue; // 文字列 via は別パッケージへの参照なのでスキップ
    const id = ghsaIdFromUrl(via.url);
    if (!id) continue;
    if (!advisories.has(id)) {
      advisories.set(id, {
        id,
        title: via.title ?? "(no title)",
        severity: via.severity ?? "unknown",
        url: via.url ?? "",
      });
    }
  }
}

// reviewBy 文字列（"YYYY-MM-DD (説明)" 形式）の先頭から UTC 日付を取り出す。
// 先頭が YYYY-MM-DD で始まらない、または暦上あり得ない日付なら null を返す。
function parseReviewByDate(reviewBy) {
  const m = /^(\d{4})-(\d{2})-(\d{2})\b/.exec((reviewBy ?? "").trim());
  if (!m) return null;
  const [, y, mo, d] = m.map(Number);
  const date = new Date(Date.UTC(y, mo - 1, d));
  // ロールオーバー（例: 2026-13-40）を弾く。構築後に同じ y/m/d へ戻るかで妥当性を判定。
  if (
    date.getUTCFullYear() !== y ||
    date.getUTCMonth() !== mo - 1 ||
    date.getUTCDate() !== d
  ) {
    return null;
  }
  return date;
}

// 実行時刻の UTC 日付（0 時）。reviewBy 期限との比較に使う。
const todayUtc = new Date();
todayUtc.setUTCHours(0, 0, 0, 0);

const blocking = [];
const allowed = [];
const expired = []; // allowlist にあるが reviewBy 期限切れ・不正で fail-closed するもの
for (const adv of advisories.values()) {
  if (!BLOCKING_SEVERITIES.has(adv.severity)) continue; // high/critical のみゲート対象
  const meta = ALLOWLIST[adv.id];
  if (!meta) {
    blocking.push(adv);
    continue;
  }
  // allowlist は reviewBy 期限内のみ有効。期限切れ・不正日付は「見直し忘れ」による
  // 恒久的な握り潰しを防ぐため fail-closed（ブロック扱い）にする。
  const reviewByDate = parseReviewByDate(meta.reviewBy);
  if (reviewByDate === null) {
    expired.push({ adv, reason: `reviewBy が不正（YYYY-MM-DD で始まらない）: ${meta.reviewBy}` });
  } else if (reviewByDate < todayUtc) {
    expired.push({ adv, reason: `reviewBy (${meta.reviewBy}) の期限を過ぎている` });
  } else {
    allowed.push(adv);
  }
}

if (allowed.length > 0) {
  console.log("許容済み advisory (allowlist):");
  for (const adv of allowed) {
    const meta = ALLOWLIST[adv.id];
    console.log(`  - ${adv.id} [${adv.severity}] ${adv.title}`);
    console.log(`    理由: ${meta.reason}`);
    console.log(`    見直し: ${meta.reviewBy}`);
  }
}

if (expired.length > 0) {
  console.error("\nallowlist の期限切れ/不正エントリを検出しました（fail-closed）:");
  for (const { adv, reason } of expired) {
    console.error(`  - ${adv.id} [${adv.severity}] ${adv.title}`);
    console.error(`    ${reason}。エントリを見直す（期限延長 or 削除）か脆弱パッケージを更新してください。`);
  }
}

if (blocking.length > 0) {
  console.error("\n未許容の High/Critical advisory を検出しました:");
  for (const adv of blocking) {
    console.error(`  - ${adv.id} [${adv.severity}] ${adv.title}`);
    console.error(`    ${adv.url}`);
  }
  console.error(
    "\nallowlist で無視せず、脆弱なパッケージを更新してください (.claude/rules/security.md)。",
  );
}

if (blocking.length > 0 || expired.length > 0) {
  process.exit(1);
}

console.log("\nHigh/Critical の未許容 advisory はありません。");
