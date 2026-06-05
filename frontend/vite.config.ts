/// <reference types="vitest/config" />
import { createReadStream } from "node:fs";
import { join, normalize } from "node:path";
import { defineConfig, type Plugin } from "vite";
import react from "@vitejs/plugin-react";

/**
 * kuromoji（校正 worker の形態素解析）辞書を dev サーバーで「生の gzip バイト列」として配信する。
 *
 * 既定の静的配信は `.gz` 拡張子を見て `Content-Encoding: gzip` を付けるため、ブラウザが
 * 自動展開してしまい、kuromoji 側の再 gunzip が「invalid file signature」で失敗する。
 * ここでは Content-Encoding を付けず application/octet-stream で素のまま返し、
 * kuromoji が自前で gunzip できるようにする（本番 Cloudflare Pages 用は public/_headers で同等指定）。
 */
function kuromojiDictRaw(): Plugin {
  const publicDir = join(process.cwd(), "public");
  return {
    name: "kuromoji-dict-raw",
    configureServer(server) {
      server.middlewares.use((req, res, next) => {
        const url = req.url?.split("?")[0] ?? "";
        if (!url.startsWith("/kuromoji-dict/") || !url.endsWith(".dat.gz")) {
          next();
          return;
        }
        // パストラバーサル防止のため normalize 後に publicDir 配下であることを担保する。
        const filePath = normalize(join(publicDir, url));
        if (!filePath.startsWith(publicDir)) {
          res.statusCode = 403;
          res.end();
          return;
        }
        res.setHeader("Content-Type", "application/octet-stream");
        res.setHeader("Cache-Control", "no-cache");
        createReadStream(filePath)
          .on("error", () => next())
          .pipe(res);
      });
    },
  };
}

export default defineConfig({
  plugins: [react(), kuromojiDictRaw()],
  base: "/",
  resolve: {
    alias: {
      // 校正 worker が使う textlint / kuromoji 依存が参照する node 組み込みのうち、
      // 実行時に実際に呼ばれる path / os / assert はブラウザ実装へ差し替える。
      // fs は本機能で経路を踏まない（YAML は ?raw 文字列で渡す）ため、
      // Vite 既定の空モジュール externalize に任せる（別途エイリアスしない）。
      path: "path-browserify",
      "node:path": "path-browserify",
      os: "os-browserify/browser",
      "node:os": "os-browserify/browser",
      assert: "assert",
      "node:assert": "assert",
    },
  },
  // worker は動的 import でルールを分割ロードする（コード分割）。
  // iife/umd は code-splitting 非対応なので ES モジュール形式で出力する。
  worker: {
    format: "es",
  },
  server: {
    host: "0.0.0.0",
    port: 5173,
    proxy: {
      "/auth": "http://localhost:8000",
      "/api": "http://localhost:8000",
      "/health": "http://localhost:8000",
    },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/test-setup.ts"],
    /** vitestが拾うテストファイルを src 配下の .test.ts に限定する */
    include: ["src/**/*.test.ts", "src/**/*.test.tsx"],
    coverage: {
      provider: "v8",
      reporter: ["text", "lcov"],
      exclude: ["src/test/**", "src/**/*.d.ts", "src/main.tsx"],
    },
  },
});
