import js from "@eslint/js";
import tseslint from "typescript-eslint";
import reactHooks from "eslint-plugin-react-hooks";
import reactRefresh from "eslint-plugin-react-refresh";
import eslintConfigPrettier from "eslint-config-prettier";

export default tseslint.config(
  { ignores: ["dist"] },
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
      "react-refresh/only-export-components": ["warn", { allowConstantExport: true }],
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
  // テストファイルはフィクスチャ用の throw でリテラルを書くケースがあるため、
  // メッセージハードコード検知ルールを除外する。
  {
    files: ["src/**/*.test.ts", "src/**/*.test.tsx", "src/**/*.spec.ts", "src/test/**/*.{ts,tsx}"],
    rules: {
      "no-restricted-syntax": "off",
    },
  },
);
