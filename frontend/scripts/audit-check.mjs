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

import { execFileSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";

const frontendDir = resolve(dirname(fileURLToPath(import.meta.url)), "..");

// 許容する advisory。GHSA ID をキーに、理由と見直し期限を残す。
// 恒久対応 (vite 8 / Rolldown 移行) 完了時にエントリを削除すること。
const ALLOWLIST = {
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
function runAudit() {
  try {
    return execFileSync("npm", ["audit", "--json"], {
      cwd: frontendDir,
      encoding: "utf8",
      maxBuffer: 64 * 1024 * 1024,
    });
  } catch (err) {
    if (err.stdout) return err.stdout;
    throw err;
  }
}

function ghsaIdFromUrl(url) {
  // 例: https://github.com/advisories/GHSA-gv7w-rqvm-qjhr
  const m = /\/(GHSA-[\w-]+)\b/.exec(url ?? "");
  return m ? m[1] : null;
}

const audit = JSON.parse(runAudit());

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

const blocking = [];
const allowed = [];
for (const adv of advisories.values()) {
  if (!BLOCKING_SEVERITIES.has(adv.severity)) continue; // high/critical のみゲート対象
  if (ALLOWLIST[adv.id]) allowed.push(adv);
  else blocking.push(adv);
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

if (blocking.length > 0) {
  console.error("\n未許容の High/Critical advisory を検出しました:");
  for (const adv of blocking) {
    console.error(`  - ${adv.id} [${adv.severity}] ${adv.title}`);
    console.error(`    ${adv.url}`);
  }
  console.error(
    "\nallowlist で無視せず、脆弱なパッケージを更新してください (.claude/rules/security.md)。",
  );
  process.exit(1);
}

console.log("\nHigh/Critical の未許容 advisory はありません。");
