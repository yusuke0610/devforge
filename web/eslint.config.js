import js from "@eslint/js";
import tseslint from "typescript-eslint";
import reactHooks from "eslint-plugin-react-hooks";
import reactRefresh from "eslint-plugin-react-refresh";
import eslintConfigPrettier from "eslint-config-prettier";

export default tseslint.config(
  // src/api/generated.ts は openapi-typescript の自動生成物（手編集禁止）。
  // lint 対象に含めると生成スタイルと衝突するため除外する（ADR-0007）。
  { ignores: ["dist", "src/api/generated.ts"] },
  {
    files: ["src/**/*.{ts,tsx}"],
    extends: [
      js.configs.recommended,
      ...tseslint.configs.recommended,
      eslintConfigPrettier,
    ],
    plugins: {
      "react-hooks": reactHooks,
      "react-refresh": reactRefresh,
    },
    rules: {
      ...reactHooks.configs.recommended.rules,
      // eslint-plugin-react-hooks v7 で recommended に追加された React Compiler 系の新ルール。
      // 既存の正当なパターン（マウント時の fetch によるマウント後 setState 等）を多数 error 扱いするため、
      // toolchain メジャーアップグレード（eslint 10 / react-hooks 7.1）では一旦 off にしてスコープを保つ。
      // 個別の解消は専用リファクタで対応する。
      "react-hooks/set-state-in-effect": "off",
      "react-hooks/refs": "off",
      "react-hooks/immutability": "off",
      "react-refresh/only-export-components": ["warn", { allowConstantExport: true }],
      // console 直書きを禁止し、ログ出力は utils/logger.ts 経由に統一する。
      // logger 自身は下の override で例外にしている。
      "no-console": "error",
      // ts/tsx に日本語リテラルのエラーメッセージを直接書かない。
      // frontend/src/constants/messages.ts の定数を参照すること。
      // 詳細: .claude/rules/frontend/messages.md
      "no-restricted-syntax": [
        "error",
        {
          selector:
            "ThrowStatement > NewExpression[callee.name='Error'] > Literal[value=/[\\u3040-\\u309F\\u30A0-\\u30FF\\u4E00-\\u9FAF]/]",
          message:
            "throw new Error にリテラル日本語を直接書かない。frontend/src/constants/messages.ts の定数を参照すること。",
        },
        {
          selector:
            "ThrowStatement > NewExpression[callee.name='Error'] > TemplateLiteral:has(TemplateElement[value.raw=/[\\u3040-\\u309F\\u30A0-\\u30FF\\u4E00-\\u9FAF]/])",
          message:
            "throw new Error にテンプレートリテラルで日本語を直接書かない。frontend/src/constants/messages.ts の関数（downloadFailureMessage など）を使うこと。",
        },
      ],
    },
  },
  // utils/logger.ts は console を呼ぶ唯一のモジュール（ログ出力の SSoT）なので例外にする。
  {
    files: ["src/utils/logger.ts"],
    rules: {
      "no-console": "off",
    },
  },
  // テストファイルはフィクスチャ用の throw でリテラルを書くケースがあるため、
  // メッセージハードコード検知ルールを除外する。テスト内のデバッグ console も許容する。
  {
    files: ["src/**/*.test.ts", "src/**/*.test.tsx", "src/**/*.spec.ts", "src/test/**/*.{ts,tsx}"],
    rules: {
      "no-restricted-syntax": "off",
      "no-console": "off",
    },
  },
);
