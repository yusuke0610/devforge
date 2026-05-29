/**
 * backend/openapi.json から OpenAPI 型定義（src/api/generated.ts）を生成するスクリプト。
 *
 * ADR-0007（OpenAPI → TypeScript 型コード生成）のパイプライン。
 * 先に backend/scripts/export_openapi.py で openapi.json を出力しておくこと。
 * 通常は `make codegen-types`（Nix devshell 経由）から呼び出される。
 *
 * 生成物の冒頭に「手編集禁止」バナーを付与し、誤編集を防ぐ。
 */
import { readFileSync, writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import openapiTS, { astToString } from "openapi-typescript";

const __dirname = dirname(fileURLToPath(import.meta.url));
const OPENAPI_PATH = resolve(__dirname, "../../backend/openapi.json");
const OUTPUT_PATH = resolve(__dirname, "../src/api/generated.ts");

const BANNER = `/**
 * 自動生成ファイル — 手編集禁止。
 *
 * backend の FastAPI OpenAPI スキーマから openapi-typescript で生成される。
 * 再生成: \`make codegen-types\`（ADR-0007 参照）。
 * backend の Pydantic schema が DTO の Single Source of Truth であり、
 * このファイルはその機械的ミラー。直接編集しても次回生成で上書きされる。
 */
`;

const schema = JSON.parse(readFileSync(OPENAPI_PATH, "utf8"));
const ast = await openapiTS(schema);
const contents = BANNER + astToString(ast);
writeFileSync(OUTPUT_PATH, contents, "utf8");
console.log(`型定義を生成しました: ${OUTPUT_PATH}`);
