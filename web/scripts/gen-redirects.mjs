/**
 * CLOUD_RUN_URL 環境変数を読み取り、Cloudflare Pages 用の public/_redirects を生成するスクリプト。
 * Vite ビルド前に実行すること（npm run build に組み込み済み）。
 *
 * Cloudflare Pages の _redirects は環境変数を直接展開できないため、
 * ビルド時にこのスクリプトで実際の URL を埋め込む。
 *
 * CLOUD_RUN_URL が未設定の場合は SPA フォールバックのみを生成する
 * （ローカル開発では wrangler pages dev --proxy でバックエンドをプロキシするため問題ない）。
 */
import { writeFileSync, mkdirSync } from "node:fs";
import { resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const publicDir = resolve(__dirname, "../public");
mkdirSync(publicDir, { recursive: true });

const cloudRunUrl = process.env.CLOUD_RUN_URL?.replace(/\/$/, "");

if (!cloudRunUrl) {
  console.warn(
    "[gen-redirects] CLOUD_RUN_URL 未設定: プロキシルールなしで _redirects を生成"
  );
  writeFileSync(
    `${publicDir}/_redirects`,
    "# CLOUD_RUN_URL 未設定のためプロキシルールなし（ローカル開発用）\n/* /index.html 200\n"
  );
  process.exit(0);
}

// Cloudflare Pages の _redirects ルールを生成する。
// メモ:
//   - /health も Cloud Run へプロキシする
//   - index.html の Cache-Control ヘッダーは _redirects では設定不可。
//     wrangler.toml の [[headers]] または Cloudflare ダッシュボードで別途設定が必要。
const rules = [
  "# Cloud Run へのプロキシ",
  `/auth/* ${cloudRunUrl}/auth/:splat 200`,
  `/api/* ${cloudRunUrl}/api/:splat 200`,
  `/health ${cloudRunUrl}/health 200`,
  "",
  "# SPA フォールバック",
  "/* /index.html 200",
  "",
];

writeFileSync(`${publicDir}/_redirects`, rules.join("\n"));
console.log(
  `[gen-redirects] public/_redirects 生成完了 (CLOUD_RUN_URL=${cloudRunUrl})`
);
